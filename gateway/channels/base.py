from __future__ import annotations
import abc
from dataclasses import dataclass
from typing import Any, Optional
from gateway.domain.models import Channel, Message

@dataclass
class InboundEnvelope:
    channel_id: str
    chat_id: str
    sender_id: str
    text: str
    is_dm: bool = True
    is_group: bool = False
    attachments: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None

class ChannelAdapter(abc.ABC):
    """Channel adapter interface.

    Channel adapters are owned by Gateway and must be pure async.
    They can call back into Gateway via the provided 'ingest' callback.
    """
    def __init__(self, channel: Channel):
        self.channel = channel

    @abc.abstractmethod
    async def start(self, ingest_cb) -> None:
        ...

    @abc.abstractmethod
    async def stop(self) -> None:
        ...

    @abc.abstractmethod
    async def send_message(self, chat_id: str, text: str) -> None:
        ...
