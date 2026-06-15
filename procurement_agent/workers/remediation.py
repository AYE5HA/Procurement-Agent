import asyncio
import logging

from procurement_agent.analysis import AnalysisEngine
from procurement_agent.config import Settings
from procurement_agent.event_bus import EventBus
from procurement_agent.schemas import (
    ContractRemediated,
    EvaluationSynthesized,
    RiskLevel,
    contract_hash,
    utc_now,
)

logger = logging.getLogger(__name__)

RISK_WEIGHT = {
    RiskLevel.CRITICAL: 100,
    RiskLevel.HIGH: 75,
    RiskLevel.MEDIUM: 45,
    RiskLevel.LOW: 20,
}


class RemediationWorker:
    topic = "evaluation.synthesized"

    def __init__(self, bus: EventBus, engine: AnalysisEngine, settings: Settings) -> None:
        self.bus = bus
        self.engine = engine
        self.settings = settings

    async def run(self, ready: asyncio.Event) -> None:
        async with self.bus.subscribe(self.topic) as queue:
            ready.set()
            while True:
                event = await queue.get()
                if isinstance(event, EvaluationSynthesized):
                    await self._remediate(event)

    async def _remediate(self, event: EvaluationSynthesized) -> None:
        started_at = utc_now()
        drift = (started_at - event.submitted_at).total_seconds()
        if event.baseline_hash != contract_hash(event.contract_text):
            logger.error("Rejected remediation because baseline integrity failed")
            return
        if drift > self.settings.max_processing_drift_seconds:
            logger.error("Rejected remediation because processing drift exceeded threshold")
            return

        payload = await self.engine.remediate(
            event.contract_text,
            event.liability.findings,
            event.indemnity.findings,
        )
        all_findings = (*event.liability.findings, *event.indemnity.findings)
        completed_at = utc_now()
        await self.bus.publish(
            ContractRemediated(
                contract_id=event.contract_id,
                baseline_hash=event.baseline_hash,
                corrected_text=payload.corrected_text,
                liability_findings=event.liability.findings,
                indemnity_findings=event.indemnity.findings,
                changes_applied=payload.changes_applied,
                legal_review_notes=payload.legal_review_notes,
                overall_risk_score=max(
                    (RISK_WEIGHT[item.risk_level] for item in all_findings),
                    default=0,
                ),
                submitted_at=event.submitted_at,
                remediation_started_at=started_at,
                completed_at=completed_at,
                processing_drift_seconds=(completed_at - event.submitted_at).total_seconds(),
                baseline_integrity_verified=True,
            )
        )
