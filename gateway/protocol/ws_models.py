from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

WSMsgType = str

class WSBase(BaseModel):
    type: WSMsgType
    id: str
    ts: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

class WSRequest(WSBase):
    type: Literal[
        "req:hello",
        "req:channels.list",
        "req:chat.list",
        "req:chat.messages",
        "req:agent.run",
        "req:runs.tail",
        "req:config.get",
        "req:config.set",
        "req:doctor.audit",
        "req:approval.grant",
    ]

class WSResponse(WSBase):
    type: str  # res:*
    ok: bool = True
    err: Optional[dict[str, Any]] = None

class WSEvent(WSBase):
    type: str  # evt:*
