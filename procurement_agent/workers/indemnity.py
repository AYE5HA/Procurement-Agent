import asyncio
import logging

from procurement_agent.analysis import AnalysisEngine
from procurement_agent.event_bus import EventBus
from procurement_agent.schemas import ContractSubmitted, IndemnityEvaluated, utc_now

logger = logging.getLogger(__name__)


class IndemnityWorker:
    topic = "contract.submitted"

    def __init__(self, bus: EventBus, engine: AnalysisEngine) -> None:
        self.bus = bus
        self.engine = engine

    async def run(self, ready: asyncio.Event) -> None:
        async with self.bus.subscribe(self.topic) as queue:
            ready.set()
            while True:
                event = await queue.get()
                if not isinstance(event, ContractSubmitted):
                    continue
                started_at = utc_now()
                try:
                    findings = await self.engine.evaluate_indemnity(event.contract_text)
                    await self.bus.publish(
                        IndemnityEvaluated(
                            contract_id=event.contract_id,
                            baseline_hash=event.baseline_hash,
                            evaluation_started_at=started_at,
                            findings=findings,
                        )
                    )
                except Exception:
                    logger.exception("Indemnity evaluation failed")
