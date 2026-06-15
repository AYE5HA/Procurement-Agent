from datetime import timedelta

import pytest

from procurement_agent.analysis import AnalysisEngine
from procurement_agent.config import Settings
from procurement_agent.event_bus import EventBus
from procurement_agent.schemas import (
    ContractSubmitted,
    EvaluationSynthesized,
    IndemnityEvaluated,
    LiabilityEvaluated,
    utc_now,
)
from procurement_agent.workers.remediation import RemediationWorker


async def test_remediation_rejects_stale_contract():
    settings = Settings(
        max_processing_drift_seconds=0.001,
        analysis_provider="deterministic",
    )
    bus = EventBus()
    worker = RemediationWorker(bus, AnalysisEngine(settings), settings)
    submission = ContractSubmitted.from_text("A" * 100)
    old_time = utc_now() - timedelta(seconds=1)
    event = EvaluationSynthesized(
        contract_id=submission.contract_id,
        baseline_hash=submission.baseline_hash,
        contract_text=submission.contract_text,
        submitted_at=old_time,
        liability=LiabilityEvaluated(
            contract_id=submission.contract_id,
            baseline_hash=submission.baseline_hash,
            evaluation_started_at=old_time,
            findings=(),
        ),
        indemnity=IndemnityEvaluated(
            contract_id=submission.contract_id,
            baseline_hash=submission.baseline_hash,
            evaluation_started_at=old_time,
            findings=(),
        ),
    )
    async with bus.subscribe("contract.remediated") as queue:
        await worker._remediate(event)
        with pytest.raises(TimeoutError):
            await __import__("asyncio").wait_for(queue.get(), 0.05)
