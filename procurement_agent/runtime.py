import asyncio

from procurement_agent.analysis import AnalysisEngine
from procurement_agent.config import Settings
from procurement_agent.event_bus import EventBus
from procurement_agent.results import ResultBroker
from procurement_agent.workers.indemnity import IndemnityWorker
from procurement_agent.workers.liability import LiabilityWorker
from procurement_agent.workers.remediation import RemediationWorker
from procurement_agent.workers.result_listener import ResultListener
from procurement_agent.workers.synthesis import SynthesisWorker


class PipelineRuntime:
    def __init__(self, settings: Settings) -> None:
        self.bus = EventBus()
        self.broker = ResultBroker()
        engine = AnalysisEngine(settings)
        self.workers = (
            LiabilityWorker(self.bus, engine),
            IndemnityWorker(self.bus, engine),
            SynthesisWorker(self.bus),
            RemediationWorker(self.bus, engine, settings),
            ResultListener(self.bus, self.broker),
        )
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        readiness = [asyncio.Event() for _ in self.workers]
        self.tasks = [
            asyncio.create_task(worker.run(ready), name=worker.__class__.__name__)
            for worker, ready in zip(self.workers, readiness, strict=True)
        ]
        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in readiness)),
            timeout=5,
        )

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
