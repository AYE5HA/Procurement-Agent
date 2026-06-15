import asyncio
from uuid import UUID

from procurement_agent.schemas import ContractRemediated


class ResultBroker:
    def __init__(self) -> None:
        self._waiters: dict[UUID, asyncio.Future[ContractRemediated]] = {}
        self._lock = asyncio.Lock()

    async def register(self, contract_id: UUID) -> asyncio.Future[ContractRemediated]:
        future = asyncio.get_running_loop().create_future()
        async with self._lock:
            self._waiters[contract_id] = future
        return future

    async def resolve(self, event: ContractRemediated) -> None:
        async with self._lock:
            future = self._waiters.pop(event.contract_id, None)
        if future and not future.done():
            future.set_result(event)

    async def discard(self, contract_id: UUID) -> None:
        async with self._lock:
            future = self._waiters.pop(contract_id, None)
        if future and not future.done():
            future.cancel()
