from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Any, Callable, Awaitable
from gateway.channels.base import ChannelAdapter, InboundEnvelope
from gateway.domain.models import Channel, ChannelStatus

class WebChatChannel(ChannelAdapter):
    """Minimal in-process channel.
    WebChat UI sends inbound messages through Gateway control-plane RPC.
    Outbound messages are delivered as events (evt:run.output or evt:message.inbound echo).
    So this adapter is mostly a placeholder for parity with other channels.
    """
    def __init__(self, channel: Channel):
        super().__init__(channel)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._ingest_cb: Callable[[InboundEnvelope], Awaitable[None]] | None = None

    async def start(self, ingest_cb) -> None:
        self._ingest_cb = ingest_cb
        # self.channel.status = ChannelStatus.online
        self.channel.status = ChannelStatus.ready
        self.channel.last_seen = datetime.utcnow()
        self._stop.clear()

        async def _loop():
            # No polling. Just keep alive.
            while not self._stop.is_set():
                await asyncio.sleep(5)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()

    async def send_message(self, chat_id: str, text: str) -> None:
        # WebChat outbound is emitted by Gateway as events; no-op here.
        return
