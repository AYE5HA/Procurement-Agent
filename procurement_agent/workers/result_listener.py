import asyncio

from procurement_agent.event_bus import EventBus
from procurement_agent.results import ResultBroker
from procurement_agent.schemas import ContractRemediated


class ResultListener:
    topic = "contract.remediated"

    def __init__(self, bus: EventBus, broker: ResultBroker) -> None:
        self.bus = bus
        self.broker = broker

    async def run(self, ready: asyncio.Event) -> None:
        async with self.bus.subscribe(self.topic) as queue:
            ready.set()
            while True:
                event = await queue.get()
                if isinstance(event, ContractRemediated):
                    await self.broker.resolve(event)
