import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from procurement_agent import __version__
from procurement_agent.config import Settings, get_settings
from procurement_agent.logging import configure_logging
from procurement_agent.middleware import RateLimiter, SecurityHeadersMiddleware, verify_access_key
from procurement_agent.runtime import PipelineRuntime
from procurement_agent.schemas import AnalysisRequest, AnalysisResponse, ContractSubmitted
from procurement_agent.store import AnalysisStore


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    configure_logging(configured.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = PipelineRuntime(configured)
        store = AnalysisStore(configured.database_path)
        await store.initialize()
        await runtime.start()
        app.state.settings = configured
        app.state.runtime = runtime
        app.state.store = store
        app.state.rate_limiter = RateLimiter(configured)
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="Procurement Contract Intelligence API",
        version=__version__,
        description="Schema-validated contract risk evaluation and remediation.",
        lifespan=lifespan,
        docs_url="/docs" if configured.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def protected(request: Request) -> None:
        verify_access_key(request, configured)

    @app.get("/health")
    async def health(request: Request) -> dict:
        database_ok = await request.app.state.store.health()
        return {
            "status": "healthy" if database_ok else "degraded",
            "version": __version__,
            "database": "available" if database_ok else "unavailable",
            "analysis_provider": configured.analysis_provider,
            "model": configured.foundry_model_name,
            "foundry_configured": bool(
                configured.azure_ai_foundry_endpoint
                and configured.azure_ai_foundry_api_key
            ),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.post(
        "/api/v1/analyses",
        response_model=AnalysisResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(protected)],
    )
    async def analyze(payload: AnalysisRequest, request: Request) -> AnalysisResponse:
        settings: Settings = request.app.state.settings
        if len(payload.contract_text) > settings.max_contract_characters:
            raise HTTPException(status_code=413, detail="Contract exceeds maximum supported size.")
        await request.app.state.rate_limiter.enforce(request)

        submission = ContractSubmitted.from_text(payload.contract_text)
        future = await request.app.state.runtime.broker.register(submission.contract_id)
        await request.app.state.store.create(submission)
        await request.app.state.runtime.bus.publish(submission)
        try:
            remediated = await asyncio.wait_for(future, settings.analysis_timeout_seconds)
        except TimeoutError as exc:
            await request.app.state.runtime.broker.discard(submission.contract_id)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Contract analysis exceeded the processing deadline.",
            ) from exc

        response = AnalysisResponse(
            contract_id=remediated.contract_id,
            liability_findings=remediated.liability_findings,
            indemnity_findings=remediated.indemnity_findings,
            corrected_text=remediated.corrected_text,
            changes_applied=remediated.changes_applied,
            legal_review_notes=remediated.legal_review_notes,
            overall_risk_score=remediated.overall_risk_score,
            baseline_integrity_verified=remediated.baseline_integrity_verified,
            processing_drift_seconds=remediated.processing_drift_seconds,
            submitted_at=remediated.submitted_at,
            completed_at=remediated.completed_at,
        )
        await request.app.state.store.complete(response)
        return response

    @app.get(
        "/api/v1/analyses/{contract_id}",
        response_model=AnalysisResponse,
        dependencies=[Depends(protected)],
    )
    async def get_analysis(contract_id: UUID, request: Request) -> AnalysisResponse:
        result = await request.app.state.store.get(contract_id)
        if not result:
            raise HTTPException(status_code=404, detail="Completed analysis not found.")
        return result

    return app
