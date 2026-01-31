#!/usr/bin/env python3
"""
Example: Using LangGraph Engine (Zancora coherent + runtime patches)

Runtime patches:
A) Timer metrics is sync but engine uses `async with` -> wrap as async CM
B) langchain_core expects `langchain.debug` (legacy) but your `langchain` lacks it -> define it
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable

import gateway.agent.langgraph_engine as lge
from gateway.agent.langgraph_engine import LangGraphEngine, LANGGRAPH_AVAILABLE
from gateway.agent.llm import MockLLM
from gateway.bus import EventBus
from gateway.domain.models import AgentRun, RunStatus, ToolSpec, ToolPermission, Policy, EventType
from gateway.security.policy_engine import PolicyEngine
from gateway.security.rate_limit import RateLimiter
from gateway.tools.registry import ToolRegistry


# -----------------------------
# Runtime patch #1: langchain.debug / langchain.verbose
# -----------------------------
def patch_langchain_globals() -> None:
    """
    langchain_core still reads `langchain.debug` / `langchain.verbose` for backward compat.
    Some newer `langchain` builds don't define these attributes -> AttributeError.
    """
    try:
        import langchain  # type: ignore
    except Exception:
        return

    # Provide missing legacy globals expected by langchain_core
    if not hasattr(langchain, "debug"):
        setattr(langchain, "debug", False)
    if not hasattr(langchain, "verbose"):
        setattr(langchain, "verbose", False)


# -----------------------------
# Runtime patch #2: Timer -> async context manager
# -----------------------------
class _AsyncCM:
    """Wrap a sync context manager into an async context manager."""
    def __init__(self, cm: Any):
        self._cm = cm

    async def __aenter__(self):
        return self._cm.__enter__()

    async def __aexit__(self, exc_type, exc, tb):
        return self._cm.__exit__(exc_type, exc, tb)


def patch_metrics_timer_for_async_with() -> None:
    """
    LangGraphEngine.run() uses:
        async with metrics.agent_run_latency.time():
    But .time() returns a sync Timer. We wrap it so async-with works.
    """
    metrics = getattr(lge, "metrics", None)
    if metrics is None:
        return

    timer_metric = getattr(metrics, "agent_run_latency", None)
    if timer_metric is None or not hasattr(timer_metric, "time"):
        return

    original_time: Callable[[], Any] = timer_metric.time

    # Avoid double patch
    if getattr(timer_metric.time, "_zancora_async_patched", False):
        return

    def time_async_compatible():
        cm = original_time()
        if hasattr(cm, "__aenter__") and hasattr(cm, "__aexit__"):
            return cm
        return _AsyncCM(cm)

    time_async_compatible._zancora_async_patched = True  # type: ignore[attr-defined]
    timer_metric.time = time_async_compatible  # type: ignore[assignment]


# -----------------------------
# Tools (ToolRegistry.register(spec, handler))
# -----------------------------
def create_sample_tools() -> ToolRegistry:
    registry = ToolRegistry()

    async def weather_get(args: dict[str, Any]) -> dict[str, Any]:
        city = args.get("city") or ""
        return {"city": city, "temperature": "22°C", "condition": "Sunny"}

    registry.register(
        ToolSpec(
            name="weather.get",
            description="Get current weather for a city",
            permission=ToolPermission.read,
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string", "description": "City name"}},
                "required": ["city"],
            },
        ),
        weather_get,
    )

    async def notification_send(args: dict[str, Any]) -> dict[str, Any]:
        message = args.get("message") or ""
        recipient = args.get("recipient") or ""
        print(f"📱 NOTIFICATION to {recipient}: {message}")
        return {"sent": True, "recipient": recipient, "timestamp": datetime.utcnow().isoformat()}

    registry.register(
        ToolSpec(
            name="notification.send",
            description="Send a notification to a user",
            permission=ToolPermission.write,
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Notification message"},
                    "recipient": {"type": "string", "description": "Recipient identifier"},
                },
                "required": ["message", "recipient"],
            },
        ),
        notification_send,
    )

    return registry


# -----------------------------
# Event monitor
# -----------------------------
async def monitor_events(bus: EventBus, run_id: str):
    print("\n📡 EVENT STREAM:")
    print("=" * 60)

    sub = bus.subscribe()
    try:
        async for event in bus.iter(sub):
            if event.run_id != run_id:
                continue

            print(f"\n🔔 Event: {event.type.value}")
            print(f"   Seq: {event.seq}")

            if event.type == EventType.run_progress:
                payload = event.payload
                if "node" in payload:
                    print(f"   Node: {payload['node']}")
                if "phase" in payload:
                    print(f"   Phase: {payload['phase']}")
                if "step" in payload:
                    print(f"   Step: {payload['step']}")

            elif event.type == EventType.run_tool_call:
                payload = event.payload
                print(f"   Tool: {payload.get('tool')}")
                print(f"   Approval Required: {payload.get('approval_required', False)}")

            elif event.type == EventType.run_output:
                text = event.payload.get("text", "")
                print(f"   Output: {text[:100]}...")

            elif event.type == EventType.security_blocked:
                print(f"   Reason: {event.payload.get('reason')}")

            if event.type == EventType.run_completed:
                print("\n" + "=" * 60)
                break
    finally:
        bus.unsubscribe(sub)


# -----------------------------
# Engine builder
# -----------------------------
def build_engine_and_policy(bus: EventBus, require_write_approvals: bool):
    tools = create_sample_tools()

    policy = Policy()
    policy.tool_allow = {
        "weather.get": ToolPermission.read,
        "notification.send": ToolPermission.write,
    }

    policy_engine = PolicyEngine(
        policy,
        RateLimiter(rate=100, burst=200),
        require_approvals_for_write_tools=require_write_approvals,
    )

    return LangGraphEngine(
        bus=bus,
        tools=tools,
        policy_engine=policy_engine,
        llm=MockLLM(),
        max_steps=6,
        timeout_s=30,
    )


# -----------------------------
# Examples
# -----------------------------
async def example_simple_query():
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Simple Query (No Tools)")
    print("=" * 60)

    bus = EventBus()
    engine = build_engine_and_policy(bus, require_write_approvals=False)

    run = AgentRun(
        run_id=str(uuid.uuid4()),
        chat_id="chat_demo",
        channel_id="webchat-1",
        requested_by="user_demo",
        status=RunStatus.queued,
    )

    context = [{"role": "user", "content": "Hello! How are you today?"}]

    monitor_task = asyncio.create_task(monitor_events(bus, run.run_id))
    print("\n💬 User: Hello! How are you today?")

    try:
        result = await engine.run(run, context)
    finally:
        if not monitor_task.done():
            try:
                await asyncio.wait_for(monitor_task, timeout=3)
            except asyncio.TimeoutError:
                monitor_task.cancel()

    print("\n📊 RESULTS:")
    print(f"   Status: {result.status.value}")
    print(f"   Summary: {result.summary}")
    print(f"   Output: {result.output_text}")


async def example_with_read_tool():
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Query with Read Tool")
    print("=" * 60)

    bus = EventBus()
    engine = build_engine_and_policy(bus, require_write_approvals=False)

    run = AgentRun(
        run_id=str(uuid.uuid4()),
        chat_id="chat_demo",
        channel_id="webchat-1",
        requested_by="user_demo",
        status=RunStatus.queued,
    )

    context = [{"role": "user", "content": "What's the weather in London? Use weather.get tool."}]

    monitor_task = asyncio.create_task(monitor_events(bus, run.run_id))
    print("\n💬 User: What's the weather in London? Use weather.get tool.")

    try:
        result = await engine.run(run, context)
    finally:
        if not monitor_task.done():
            try:
                await asyncio.wait_for(monitor_task, timeout=3)
            except asyncio.TimeoutError:
                monitor_task.cancel()

    print("\n📊 RESULTS:")
    print(f"   Status: {result.status.value}")
    print(f"   Summary: {result.summary}")
    print(f"   Output: {result.output_text}")


async def example_with_approval():
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Query with Write Tool (Requires Approval)")
    print("=" * 60)

    bus = EventBus()
    engine = build_engine_and_policy(bus, require_write_approvals=True)

    run = AgentRun(
        run_id=str(uuid.uuid4()),
        chat_id="chat_demo",
        channel_id="webchat-1",
        requested_by="user_demo",
        status=RunStatus.queued,
    )

    context = [{"role": "user", "content": "Send notification 'Meeting at 3pm' to Alice using notification.send"}]

    async def monitor_and_approve():
        sub = bus.subscribe()
        try:
            async for event in bus.iter(sub):
                if event.run_id != run.run_id:
                    continue

                print(f"\n🔔 Event: {event.type.value}")

                if event.type == EventType.run_tool_call:
                    payload = event.payload
                    if payload.get("approval_required"):
                        print(f"   ⏳ Approval required for: {payload.get('tool')}")
                        print("   ✅ AUTO-GRANTING approval...")
                        await asyncio.sleep(0.2)
                        engine.grant_approval(run.run_id)

                if event.type == EventType.run_completed:
                    break
        finally:
            bus.unsubscribe(sub)

    monitor_task = asyncio.create_task(monitor_and_approve())
    print("\n💬 User: Send notification 'Meeting at 3pm' to Alice using notification.send")

    try:
        result = await engine.run(run, context)
    finally:
        if not monitor_task.done():
            try:
                await asyncio.wait_for(monitor_task, timeout=3)
            except asyncio.TimeoutError:
                monitor_task.cancel()

    print("\n📊 RESULTS:")
    print(f"   Status: {result.status.value}")
    print(f"   Summary: {result.summary}")
    print(f"   Output: {result.output_text}")


async def main():
    print("\n" + "=" * 60)
    print("LangGraph Engine Examples (Zancora coherent + runtime patches)")
    print("=" * 60)

    if not LANGGRAPH_AVAILABLE:
        print("\n❌ LangGraph is not installed!")
        print("Install with: pip install -e .[agentic]")
        return

    # Apply runtime patches BEFORE running the graph
    patch_langchain_globals()
    patch_metrics_timer_for_async_with()

    await example_simple_query()
    await asyncio.sleep(1)

    await example_with_read_tool()
    await asyncio.sleep(1)

    await example_with_approval()

    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
