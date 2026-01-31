#!/usr/bin/env python3
"""
Zancora LangGraph example using REAL OpenAI LLM (FULLY patched)

Dependencies:
  pip install openai python-dotenv
  pip install -e .[agentic]

Reads .env:
  AGW_OPENAI_API_KEY=...
  AGW_OPENAI_MODEL=gpt-4o-mini
  optional: AGW_OPENAI_BASE_URL=...

Última corrección principal:
- Reconstrucción del historial de mensajes para evitar error 400 de OpenAI
  cuando hay mensajes role='tool' sin tool_calls previo
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Optional


# =============================
# Load .env robustly
# =============================
def _load_env() -> None:
    try:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv(usecwd=True), override=False)
        return
    except ImportError:
        pass

    here = os.path.abspath(os.getcwd())
    for _ in range(8):
        candidate = os.path.join(here, ".env")
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if " #" in line:
                            line = line.split(" #", 1)[0].strip()
                        if "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        os.environ.setdefault(k, v)
            except Exception:
                pass
            return
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent


_load_env()


# =============================
# Zancora imports
# =============================
import gateway.agent.langgraph_engine as lge
from gateway.agent.langgraph_engine import LangGraphEngine, LANGGRAPH_AVAILABLE
from gateway.agent.llm import LLMAdapter, LLMResult
from gateway.bus import EventBus
from gateway.domain.models import (
    AgentRun,
    RunStatus,
    ToolSpec,
    ToolPermission,
    Policy,
    EventType,
)
from gateway.security.policy_engine import PolicyEngine
from gateway.security.rate_limit import RateLimiter
from gateway.tools.registry import ToolRegistry


# =============================
# Runtime patch 1: langchain.debug / verbose
# =============================
def patch_langchain_globals() -> None:
    try:
        import langchain
    except ImportError:
        return

    if not hasattr(langchain, "debug"):
        setattr(langchain, "debug", False)
    if not hasattr(langchain, "verbose"):
        setattr(langchain, "verbose", False)


# =============================
# Runtime patch 2: Timer sync used with `async with`
# =============================
class _AsyncCM:
    def __init__(self, cm: Any):
        self._cm = cm

    async def __aenter__(self):
        return self._cm.__enter__()

    async def __aexit__(self, exc_type, exc, tb):
        return self._cm.__exit__(exc_type, exc, tb)


def patch_metrics_timer_for_async_with() -> None:
    metrics = getattr(lge, "metrics", None)
    if metrics is None:
        return

    timer_metric = getattr(metrics, "agent_run_latency", None)
    if timer_metric is None or not hasattr(timer_metric, "time"):
        return

    original_time: Callable[[], Any] = timer_metric.time

    if getattr(timer_metric.time, "_zancora_async_patched", False):
        return

    def time_async_compatible():
        cm = original_time()
        if hasattr(cm, "__aenter__") and hasattr(cm, "__aexit__"):
            return cm
        return _AsyncCM(cm)

    time_async_compatible._zancora_async_patched = True
    timer_metric.time = time_async_compatible


# =============================
# Compatible Policy
# =============================
class CompatiblePolicy(Policy):
    """Policy con método is_tool_allowed compatible con PolicyEngine"""

    def is_tool_allowed(
        self,
        tool_name: str,
        required_perm: Optional[ToolPermission] = None
    ) -> bool:
        allowed_perm = self.tool_allow.get(tool_name)
        if allowed_perm is None:
            return False

        if required_perm is None:
            return True

        rank = {ToolPermission.read: 1, ToolPermission.write: 2}
        allowed_rank = rank.get(allowed_perm, 0)
        required_rank = rank.get(required_perm, 1)

        return allowed_rank >= required_rank


# =============================
# Tool name mapping for OpenAI
# =============================
def to_openai_tool_name(internal_name: str) -> str:
    return internal_name.replace(".", "_")


def build_tool_name_maps(tool_specs: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    internal_to_openai: dict[str, str] = {}
    openai_to_internal: dict[str, str] = {}
    for t in tool_specs:
        internal = t.get("name")
        if not internal:
            continue
        oai = to_openai_tool_name(internal)
        internal_to_openai[internal] = oai
        openai_to_internal[oai] = internal
    return internal_to_openai, openai_to_internal


def to_openai_tools(tool_specs: list[dict[str, Any]], internal_to_openai: dict[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tool_specs:
        internal = t.get("name")
        if not internal:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": internal_to_openai.get(internal, to_openai_tool_name(internal)),
                    "description": t.get("description", "") or "",
                    "parameters": t.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


# =============================
# OpenAI LLM adapter (con fix para historial con role='tool')
# =============================
class OpenAIPlanner(LLMAdapter):
    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def plan(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> LLMResult:
        internal_to_openai, openai_to_internal = build_tool_name_maps(tools)
        openai_tools = to_openai_tools(tools, internal_to_openai)

        # ──────────────────────────────────────────────
        # FIX PRINCIPAL: reconstruir historial válido para OpenAI
        # Los mensajes role='tool' no pueden ir sueltos
        # ──────────────────────────────────────────────
        cleaned_messages = []
        for msg in messages:
            if msg.get("role") == "tool":
                # Adjuntamos el resultado como parte del assistant anterior
                # o creamos un assistant nuevo si no hay
                content = f"Resultado de herramienta: {msg.get('content', '')}"
                if cleaned_messages and cleaned_messages[-1].get("role") == "assistant":
                    prev = cleaned_messages[-1]["content"] or ""
                    cleaned_messages[-1]["content"] = prev + "\n\n" + content
                else:
                    cleaned_messages.append({
                        "role": "assistant",
                        "content": content
                    })
            else:
                cleaned_messages.append(msg.copy())

        sys_msg = {
            "role": "system",
            "content": (
                "Eres un agente Zancora. "
                "Si existe una herramienta adecuada, úsala. "
                "Para clima usa weather.get. Para notificaciones usa notification.send. "
                "Luego responde en español y breve."
            ),
        }

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[sys_msg] + cleaned_messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto",
            temperature=0.2,
        )

        msg = resp.choices[0].message
        content = msg.content or ""

        tool_calls_out: list[dict[str, Any]] = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                openai_name = tc.function.name
                internal_name = openai_to_internal.get(openai_name, openai_name)

                raw_args = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {"_raw": raw_args}

                tool_calls_out.append({"name": internal_name, "args": args})

        return LLMResult(content=content if content else "tool_call", tool_calls=tool_calls_out or None)


def build_real_llm_from_env() -> OpenAIPlanner:
    api_key = os.getenv("AGW_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("AGW_OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    base_url = os.getenv("AGW_OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL")

    if not api_key:
        raise RuntimeError(
            "No OpenAI API key found. Put AGW_OPENAI_API_KEY in .env or export it."
        )
    return OpenAIPlanner(api_key=api_key, model=model, base_url=base_url)


# =============================
# Tool registry
# =============================
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


# =============================
# Event monitors
# =============================
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

            if event.type == EventType.run_tool_call:
                payload = event.payload
                print(f"   Tool: {payload.get('tool')}")
                print(f"   Args: {payload.get('args')}")
                print(f"   Approval Required: {payload.get('approval_required', False)}")

            elif event.type == EventType.run_output:
                text = event.payload.get("text", "")
                print(f"   Output: {text[:200]}...")

            elif event.type == EventType.security_blocked:
                print(f"   Reason: {event.payload.get('reason')}")

            if event.type == EventType.run_completed:
                print("\n" + "=" * 60)
                break
    finally:
        bus.unsubscribe(sub)


# =============================
# Engine builder
# =============================
def build_engine_and_policy(bus: EventBus, require_write_approvals: bool) -> LangGraphEngine:
    tools = create_sample_tools()

    policy = CompatiblePolicy()
    policy.tool_allow = {
        "weather.get": ToolPermission.read,
        "notification.send": ToolPermission.write,
    }

    policy_engine = PolicyEngine(
        policy,
        RateLimiter(rate=10, burst=20),
        require_approvals_for_write_tools=require_write_approvals,
    )

    llm = build_real_llm_from_env()

    return LangGraphEngine(
        bus=bus,
        tools=tools,
        policy_engine=policy_engine,
        llm=llm,
        max_steps=10,
        timeout_s=60,
    )


# =============================
# Examples
# =============================
async def example_simple_query():
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Simple Query (REAL LLM)")
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

    context = [{"role": "user", "content": "Hola. Respóndeme en una frase corta, por favor."}]

    mon = asyncio.create_task(monitor_events(bus, run.run_id))
    try:
        result = await engine.run(run, context)
    finally:
        if not mon.done():
            mon.cancel()

    print("\n📊 RESULTS:")
    print("   Status:", result.status.value)
    print("   Summary:", result.summary)
    print("   Output:", result.output_text)


async def example_with_read_tool():
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Read Tool (weather.get SHOULD be called)")
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

    context = [{"role": "user", "content": "Dime el clima en London ahora. Usa la herramienta weather.get."}]

    mon = asyncio.create_task(monitor_events(bus, run.run_id))
    try:
        result = await engine.run(run, context)
    finally:
        if not mon.done():
            mon.cancel()

    print("\n📊 RESULTS:")
    print("   Status:", result.status.value)
    print("   Summary:", result.summary)
    print("   Output:", result.output_text)


async def example_with_approval():
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Write Tool + approval (notification.send)")
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

    context = [
        {
            "role": "user",
            "content": "Envía una notificación a Alice con mensaje 'Meeting at 3pm' usando notification.send.",
        }
    ]

    async def monitor_and_approve():
        sub = bus.subscribe()
        try:
            async for event in bus.iter(sub):
                if event.run_id != run.run_id:
                    continue
                if event.type == EventType.run_tool_call:
                    payload = event.payload
                    if payload.get("approval_required"):
                        print("\n✅ APPROVAL REQUIRED -> auto-approving (demo)")
                        await asyncio.sleep(0.2)
                        engine.grant_approval(run.run_id)
                if event.type == EventType.run_completed:
                    break
        finally:
            bus.unsubscribe(sub)

    approve_task = asyncio.create_task(monitor_and_approve())
    try:
        result = await engine.run(run, context)
    finally:
        if not approve_task.done():
            approve_task.cancel()

    print("\n📊 RESULTS:")
    print("   Status:", result.status.value)
    print("   Summary:", result.summary)
    print("   Output:", result.output_text)


async def main():
    print("\n" + "=" * 60)
    print("LangGraph Engine Examples (REAL OpenAI LLM)")
    print("=" * 60)

    if not LANGGRAPH_AVAILABLE:
        print("\n❌ LangGraph not installed. Run: pip install -e .[agentic]")
        return

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