import pytest
from gateway.domain.models import Policy, ToolSpec, ToolPermission
from gateway.security.rate_limit import RateLimiter
from gateway.security.policy_engine import PolicyEngine

def test_sender_allowlist_deny_by_default():
    pol = Policy(allowlist={})
    pe = PolicyEngine(pol, RateLimiter(10, 10))
    ok, reason = pe.allow_sender("ch1","u1", is_dm=True, is_group=False)
    assert not ok and reason == "sender_not_allowlisted"

def test_sender_allowlist_ok():
    pol = Policy(allowlist={"ch1":["u1"]}, dm_policy="allow", group_policy="deny")
    pe = PolicyEngine(pol, RateLimiter(10, 10))
    ok, reason = pe.allow_sender("ch1","u1", is_dm=True, is_group=False)
    assert ok

def test_tool_policy_deny_by_default():
    pol = Policy(tool_allow={})
    pe = PolicyEngine(pol, RateLimiter(10,10))
    spec = ToolSpec(name="t1", permission=ToolPermission.read)
    ok, reason, needs = pe.allow_tool(spec)
    assert not ok and reason == "tool_not_allowed" and not needs

def test_tool_write_needs_approval():
    pol = Policy(tool_allow={"t1": True})
    pe = PolicyEngine(pol, RateLimiter(10,10), require_approvals_for_write_tools=True)
    spec = ToolSpec(name="t1", permission=ToolPermission.write)
    ok, reason, needs = pe.allow_tool(spec)
    assert ok and needs
