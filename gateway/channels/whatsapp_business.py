from __future__ import annotations
import asyncio
from datetime import datetime
from gateway.channels.base import ChannelAdapter
from gateway.domain.models import Channel, ChannelStatus

class WhatsAppBusinessChannel(ChannelAdapter):
    """Skeleton adapter for WhatsApp Business Cloud API (official Meta API).

    Inbound: via HTTPS webhook -> map to InboundEnvelope -> Gateway.ingest_inbound
    Outbound: call /messages send endpoint.

    We keep this as a skeleton to avoid embedding credentials and to remain API-agnostic.
    """
    def __init__(self, channel: Channel):
        super().__init__(channel)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self, ingest_cb) -> None:
        self.channel.status = ChannelStatus.ready
        self.channel.last_seen = datetime.utcnow()

        async def _loop():
            while not self._stop.is_set():
                await asyncio.sleep(30)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()

    async def send_message(self, chat_id: str, text: str) -> None:
        # POST to Meta Graph API messages endpoint. Not implemented.
        return
