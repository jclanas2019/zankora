"""Domain models for the gateway."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class ChannelType(str, Enum):
    """Supported channel types."""

    webchat = "webchat"
    telegram = "telegram"
    whatsapp_business = "whatsapp_business"
    slack = "slack"
    discord = "discord"


class ChannelStatus(str, Enum):
    """Channel operational status."""

    offline = "offline"
    ready = "ready"
    error = "error"
    rate_limited = "rate_limited"


class RunStatus(str, Enum):
    """Agent run status."""

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    timeout = "timeout"
    cancelled = "cancelled"
    approval_pending = "approval_pending"


class EventType(str, Enum):
    """Event types for the event bus."""

    channel_status = "channel.status"
    message_inbound = "message.inbound"
    run_progress = "run.progress"
    run_tool_call = "run.tool_call"
    run_output = "run.output"
    run_completed = "run.completed"
    security_blocked = "security.blocked"
    approval_required = "approval.required"
    approval_granted = "approval.granted"
    approval_denied = "approval.denied"
    approval_timeout = "approval.timeout"
    error = "error"


class ToolPermission(str, Enum):
    """Tool permission levels."""

    read = "read"  # Read-only operations, no approval needed
    write = "write"  # Write operations, requires approval in strict mode


class DMPolicy(str, Enum):
    """Direct message handling policy."""

    allow = "allow"
    deny = "deny"
    allowlist_only = "allowlist_only"


class GroupPolicy(str, Enum):
    """Group message handling policy."""

    allow = "allow"
    deny = "deny"
    allowlist_only = "allowlist_only"


# ============================================================================
# Attachment Models (needed by persistence layer)
# ============================================================================


class AttachmentMeta(BaseModel):
    """Attachment metadata for messages.

    Persistence layer expects this model to exist.
    """

    kind: str = Field(description="mime-like type or semantic kind", default="unknown")
    url: Optional[str] = Field(default=None, description="Optional URL reference")
    name: Optional[str] = Field(default=None, description="Original filename")
    size_bytes: Optional[int] = Field(default=None, description="Size in bytes")
    sha256: Optional[str] = Field(default=None, description="Content hash if available")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional attachment metadata")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Core Models
# ============================================================================


class Channel(BaseModel):
    """Channel configuration and metadata."""

    id: str = Field(description="Unique channel identifier")
    type: ChannelType = Field(description="Channel type")
    status: ChannelStatus = Field(default=ChannelStatus.offline, description="Current status")
    config: dict[str, Any] = Field(default_factory=dict, description="Channel-specific configuration")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Required by persistence layer and gateway core
    last_seen: Optional[datetime] = Field(
        default=None,
        description="Last time the channel was seen alive / heartbeat timestamp",
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Chat(BaseModel):
    """Chat/conversation context."""

    chat_id: str = Field(description="Unique chat identifier")
    channel_id: str = Field(description="Channel this chat belongs to")
    participants: list[str] = Field(default_factory=list, description="List of participant IDs")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chat metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Message(BaseModel):
    """Message in a chat."""

    msg_id: str = Field(description="Unique message identifier")
    chat_id: str = Field(description="Chat this message belongs to")
    channel_id: str = Field(description="Channel this message came from")
    sender_id: str = Field(description="Sender identifier")
    text: str = Field(description="Message text content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # ✅ Was list[dict]; persistence expects AttachmentMeta. This keeps structure consistent.
    attachments: list[AttachmentMeta] = Field(default_factory=list, description="Message attachments")

    metadata: dict[str, Any] = Field(default_factory=dict, description="Message metadata")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentRun(BaseModel):
    """Agent execution run."""

    run_id: str = Field(description="Unique run identifier")
    chat_id: str = Field(description="Chat context for this run")
    channel_id: str = Field(description="Channel this run is associated with")
    requested_by: str = Field(description="User who requested the run")
    status: RunStatus = Field(default=RunStatus.queued)

    started_at: datetime | None = None

    # ✅ Required by persistence/repo (DB column is finished_at)
    finished_at: datetime | None = None

    # Optional higher-level alias (keep if other parts of code refer to completed_at)
    completed_at: datetime | None = None

    steps_executed: int = Field(default=0)
    tools_called: list[str] = Field(default_factory=list)
    output_text: str | None = None
    summary: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class Event(BaseModel):
    """Event published to the event bus."""

    run_id: str | None = Field(default=None, description="Associated run ID if applicable")
    seq: int = Field(description="Sequence number for ordering")
    type: EventType = Field(description="Event type")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    ts: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Tool Models
# ============================================================================


class ToolSpec(BaseModel):
    """Tool specification and metadata."""

    name: str = Field(description="Tool name (plugin.tool_name format)")
    description: str = Field(description="Tool description for LLM")
    permission: ToolPermission = Field(default=ToolPermission.read)
    func: Callable[..., Any] | None = Field(default=None, exclude=True, description="Tool function")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Parameter schema")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# Policy Models
# ============================================================================


class Policy(BaseModel):
    """Security and access control policy."""

    allowlist: dict[str, list[str]] = Field(default_factory=dict)

    dm_policy: DMPolicy = Field(default=DMPolicy.allowlist_only)
    group_policy: GroupPolicy = Field(default=GroupPolicy.deny)

    tool_allow: dict[str, ToolPermission] = Field(default_factory=dict)

    rate_limits: dict[str, float] = Field(default_factory=dict)

    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Approval Models
# ============================================================================


class ApprovalRequest(BaseModel):
    """Request for human approval."""

    approval_id: str = Field(description="Unique approval identifier")
    run_id: str = Field(description="Associated run ID")
    tool_name: str = Field(description="Tool requiring approval")
    tool_args: dict[str, Any] = Field(description="Tool arguments")
    reason: str = Field(description="Reason for approval requirement")
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    status: Literal["pending", "granted", "denied", "expired"] = Field(default="pending")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# ============================================================================
# Health Check Models
# ============================================================================


class HealthStatus(str, Enum):
    """Health check status."""

    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"


class HealthCheck(BaseModel):
    """System health check result."""

    status: HealthStatus
    version: str
    uptime_seconds: float
    checks: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
