import asyncio
from time import perf_counter

from procurement_agent.analysis import AnalysisEngine
from procurement_agent.config import Settings
from procurement_agent.runtime import PipelineRuntime
from procurement_agent.schemas import ContractSubmitted

CONTRACT = """
PROCUREMENT SERVICES AGREEMENT
Supplier will provide managed services. Supplier's liability shall be unlimited for any breach.
Buyer will pay invoices within thirty days. Supplier owns its pre-existing intellectual property.
The agreement is silent on third-party claims, defense obligations, insurance,
and infringement remedies.
"""


class TimedEngine(AnalysisEngine):
    async def evaluate_liability(self, text):
        await asyncio.sleep(0.12)
        return await super().evaluate_liability(text)

    async def evaluate_indemnity(self, text):
        await asyncio.sleep(0.12)
        return await super().evaluate_indemnity(text)


async def test_autonomous_pipeline_returns_self_contained_remediation(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        analysis_provider="deterministic",
    )
    runtime = PipelineRuntime(settings)
    await runtime.start()
    try:
        submission = ContractSubmitted.from_text(CONTRACT)
        future = await runtime.broker.register(submission.contract_id)
        await runtime.bus.publish(submission)
        result = await asyncio.wait_for(future, 2)
    finally:
        await runtime.stop()

    assert result.contract_id == submission.contract_id
    assert result.baseline_hash == submission.baseline_hash
    assert result.baseline_integrity_verified is True
    assert result.liability_findings
    assert result.indemnity_findings
    assert "RISK ALLOCATION AMENDMENT" in result.corrected_text
    assert result.changes_applied


async def test_evaluations_execute_concurrently(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        analysis_provider="deterministic",
    )
    runtime = PipelineRuntime(settings)
    engine = TimedEngine(settings)
    runtime.workers[0].engine = engine
    runtime.workers[1].engine = engine
    runtime.workers[3].engine = engine
    await runtime.start()
    started = perf_counter()
    try:
        submission = ContractSubmitted.from_text(CONTRACT)
        future = await runtime.broker.register(submission.contract_id)
        await runtime.bus.publish(submission)
        await asyncio.wait_for(future, 2)
    finally:
        await runtime.stop()
    elapsed = perf_counter() - started
    assert elapsed < 0.22


def test_evaluation_workers_are_domain_independent():
    from procurement_agent.workers import indemnity, liability

    assert "indemnity" not in liability.__dict__
    assert "liability" not in indemnity.__dict__
