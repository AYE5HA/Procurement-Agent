import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from procurement_agent.schemas import PipelineEvent

T = TypeVar("T")
EVENT_ADAPTER = TypeAdapter(PipelineEvent)


@dataclass(frozen=True)
class Subscription:
    id: UUID
    topic: str
    queue: asyncio.Queue[PipelineEvent]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, dict[UUID, asyncio.Queue[PipelineEvent]]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def publish(self, event: PipelineEvent) -> None:
        validated = EVENT_ADAPTER.validate_python(event)
        async with self._lock:
            queues = tuple(self._subscribers[validated.event_type].values())
        await asyncio.gather(*(queue.put(validated) for queue in queues))

    @asynccontextmanager
    async def subscribe(self, topic: str) -> AsyncIterator[asyncio.Queue[PipelineEvent]]:
        subscription = Subscription(uuid4(), topic, asyncio.Queue())
        async with self._lock:
            self._subscribers[topic][subscription.id] = subscription.queue
        try:
            yield subscription.queue
        finally:
            async with self._lock:
                self._subscribers[topic].pop(subscription.id, None)

    async def subscriber_count(self, topic: str) -> int:
        async with self._lock:
            return len(self._subscribers[topic])
