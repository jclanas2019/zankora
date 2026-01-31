from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator

from gateway.domain.models import Event


@dataclass(eq=False)
class Subscription:
    """
    Subscription must be hashable because EventBus keeps them in a set.

    - eq=False ensures identity-based semantics (each instance is unique)
    - __hash__ provided so it can live in a set even though it's mutable
    """
    queue: asyncio.Queue[Event]
    closed: bool = False
    _id: int = field(default_factory=lambda: id(object()), repr=False)

    def __hash__(self) -> int:
        # Stable hash for the life of this subscription instance
        return self._id


class EventBus:
    """In-process pub/sub bus.
    - Gateway is single authority that emits events.
    - WS clients and channels can subscribe.
    """

    def __init__(self, max_queue_size: int = 1000):
        self._subs: set[Subscription] = set()
        self._seq = 0
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size

    async def next_seq(self) -> int:
        async with self._lock:
            self._seq += 1
            return self._seq

    def subscribe(self) -> Subscription:
        sub = Subscription(queue=asyncio.Queue(maxsize=self._max_queue_size))
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        sub.closed = True
        self._subs.discard(sub)

    async def publish(self, evt: Event) -> None:
        # Best-effort broadcast; slow consumers drop events rather than backpressure core.
        dead: list[Subscription] = []
        for sub in list(self._subs):
            if sub.closed:
                dead.append(sub)
                continue
            try:
                sub.queue.put_nowait(evt)
            except asyncio.QueueFull:
                # drop oldest by draining one, then try again; else drop the new
                try:
                    _ = sub.queue.get_nowait()
                    sub.queue.put_nowait(evt)
                except Exception:
                    pass
        for d in dead:
            self._subs.discard(d)

    async def iter(self, sub: Subscription) -> AsyncIterator[Event]:
        while not sub.closed:
            evt = await sub.queue.get()
            yield evt
