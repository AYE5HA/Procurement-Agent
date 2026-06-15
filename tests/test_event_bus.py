import asyncio

from procurement_agent.event_bus import EventBus
from procurement_agent.schemas import ContractSubmitted


async def test_event_bus_fans_out_to_every_subscriber():
    bus = EventBus()
    event = ContractSubmitted.from_text("A" * 100)

    async with (
        bus.subscribe("contract.submitted") as first,
        bus.subscribe("contract.submitted") as second,
    ):
        await bus.publish(event)
        assert await asyncio.wait_for(first.get(), 1) == event
        assert await asyncio.wait_for(second.get(), 1) == event
