from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from gateway.domain.models import Policy, ToolPermission, ToolSpec
from gateway.security.rate_limit import RateLimiter

@dataclass
class Principal:
    kind: str  # "client" or "channel_sender"
    id: str
    channel_id: str | None = None
    chat_meta: dict | None = None  # used for dm/group gating

class PolicyEngine:
    def __init__(self, policy: Policy, rate_limiter: RateLimiter, require_approvals_for_write_tools: bool = True):
        self.policy = policy
        self.rate = rate_limiter
        self.require_approvals_for_write_tools = require_approvals_for_write_tools

    def allow_sender(self, channel_id: str, sender_id: str, is_dm: bool, is_group: bool) -> tuple[bool, str]:
        # deny by default
        if not self.policy.is_allowed_sender(channel_id, sender_id):
            return False, "sender_not_allowlisted"
        if is_dm and self.policy.dm_policy != "allow":
            return False, "dm_blocked"
        if is_group and self.policy.group_policy != "allow":
            return False, "group_blocked"
        if not self.rate.allow(f"sender:{channel_id}:{sender_id}", cost=1.0):
            return False, "rate_limited"
        return True, "ok"

    def allow_tool(self, tool: ToolSpec) -> tuple[bool, str, bool]:
        """Return (allowed, reason, needs_approval).

        Tools are deny-by-default and must be explicitly allowed by policy.
        Writes may additionally require explicit human approval.
        """
        if not self.policy.is_tool_allowed(tool.name):
            return False, "tool_not_allowed", False
        if tool.permission == ToolPermission.write and self.require_approvals_for_write_tools:
            return True, "ok", True
        return True, "ok", False
