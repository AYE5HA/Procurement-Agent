import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from procurement_agent.event_bus import EventBus
from procurement_agent.schemas import (
    ContractSubmitted,
    EvaluationSynthesized,
    IndemnityEvaluated,
    LiabilityEvaluated,
)

logger = logging.getLogger(__name__)


@dataclass
class ContractState:
    submission: ContractSubmitted | None = None
    liability: LiabilityEvaluated | None = None
    indemnity: IndemnityEvaluated | None = None


class SynthesisWorker:
    topics = ("contract.submitted", "liability.evaluated", "indemnity.evaluated")

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._states: dict[UUID, ContractState] = {}
        self._lock = asyncio.Lock()

    async def run(self, ready: asyncio.Event) -> None:
        async with (
            self.bus.subscribe(self.topics[0]) as submissions,
            self.bus.subscribe(self.topics[1]) as liabilities,
            self.bus.subscribe(self.topics[2]) as indemnities,
        ):
            ready.set()
            await asyncio.gather(
                self._consume(submissions),
                self._consume(liabilities),
                self._consume(indemnities),
            )

    async def _consume(self, queue: asyncio.Queue) -> None:
        while True:
            await self._record(await queue.get())

    async def _record(self, event) -> None:
        async with self._lock:
            state = self._states.setdefault(event.contract_id, ContractState())
            if isinstance(event, ContractSubmitted):
                state.submission = event
            elif isinstance(event, LiabilityEvaluated):
                state.liability = event
            elif isinstance(event, IndemnityEvaluated):
                state.indemnity = event
            if not (state.submission and state.liability and state.indemnity):
                return
            submission = state.submission
            liability = state.liability
            indemnity = state.indemnity
            self._states.pop(event.contract_id, None)

        if len({submission.baseline_hash, liability.baseline_hash, indemnity.baseline_hash}) != 1:
            logger.error("Rejected synthesis because baseline hashes differ")
            return
        await self.bus.publish(
            EvaluationSynthesized(
                contract_id=submission.contract_id,
                baseline_hash=submission.baseline_hash,
                contract_text=submission.contract_text,
                submitted_at=submission.submitted_at,
                liability=liability,
                indemnity=indemnity,
            )
        )
