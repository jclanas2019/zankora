from __future__ import annotations
import asyncio, os, uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from gateway.bus import EventBus
from gateway.config import Settings
from gateway.domain.models import Channel, ChannelStatus, ChannelType, Chat, Message, AgentRun, EventType, Event, Policy, RunStatus
from gateway.observability.logging import get_logger, bind_run_id
from gateway.observability import metrics
from gateway.persistence.repo import Repo
from gateway.security.policy_engine import PolicyEngine
from gateway.security.sanitize import sanitize_text
from gateway.channels.base import InboundEnvelope, ChannelAdapter
from gateway.channels.webchat import WebChatChannel
from gateway.channels.telegram import TelegramChannel
from gateway.channels.whatsapp_business import WhatsAppBusinessChannel
from gateway.tools.registry import ToolRegistry, builtins_registry
from gateway.agent.runner import AgentRunner
from gateway.agent.engine import AgentEngine
from gateway.plugins.registry import PluginRegistry
from gateway.plugins.loader import load_plugins
from gateway.security.rate_limit import RateLimiter

log = get_logger("gateway")

def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def _create_agent_engine(
    settings: Settings,
    bus: EventBus,
    tools: ToolRegistry,
    policy_engine: PolicyEngine,
) -> AgentEngine:
    """Create the appropriate agent engine based on settings."""
    if settings.agent_engine == "langgraph":
        try:
            from gateway.agent.langgraph_engine import LangGraphEngine
            log.info("agent_engine_selected", engine="langgraph")
            return LangGraphEngine(
                bus=bus,
                tools=tools,
                policy_engine=policy_engine,
                max_steps=settings.run_max_steps,
                timeout_s=settings.run_timeout_s,
                retry=settings.run_retry,
            )
        except ImportError as e:
            log.error(
                "langgraph_not_available",
                error=str(e),
                hint="Install with: pip install -e .[agentic]",
            )
            raise RuntimeError(
                f"LangGraph engine requested but not available. Install with: pip install -e .[agentic]"
            ) from e
    else:
        # Default to simple engine (AgentRunner)
        log.info("agent_engine_selected", engine="simple")
        return AgentRunner(
            bus=bus,
            tools=tools,
            policy_engine=policy_engine,
            max_steps=settings.run_max_steps,
            timeout_s=settings.run_timeout_s,
            retry=settings.run_retry,
        )

class Gateway:
    """Single authority: owns channels, policies, state, runs and emits events.

    External access: WS control-plane.
    """
    def __init__(self, settings: Settings, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.engine = engine
        self.session_factory = session_factory

        self.bus = EventBus()
        self.channels: dict[str, ChannelAdapter] = {}
        self.channel_meta: dict[str, Channel] = {}
        self.policy = Policy()  # loaded from config persistence (MVP: static; can be updated via WS)
        self.rate_limiter = RateLimiter(rate=settings.rate_limit_rps, burst=settings.rate_limit_burst)
        self.policy_engine = PolicyEngine(self.policy, self.rate_limiter, require_approvals_for_write_tools=settings.require_approvals_for_write_tools)

        self.tools: ToolRegistry = builtins_registry()
        self.plugin_registry = PluginRegistry(tools=self.tools)
        self.loaded_plugins = []

        self.runner = _create_agent_engine(
            settings=settings,
            bus=self.bus,
            tools=self.tools,
            policy_engine=self.policy_engine,
        )

        self._run_tasks: dict[str, asyncio.Task] = {}
        self._lock_file: str | None = None

    async def start(self) -> None:
        os.makedirs(self.settings.data_dir, exist_ok=True)
        self._lock_file = os.path.join(self.settings.data_dir, "gateway.lock")
        self._acquire_lock()

        # load plugins
        self.loaded_plugins = load_plugins(self.settings.plugin_dir, self.plugin_registry)

        # channels (minimum set; plugin channels could be added later)
        await self._ensure_channel("webchat-1", ChannelType.webchat, adapter_cls=WebChatChannel)
        await self._ensure_channel("telegram-1", ChannelType.telegram, adapter_cls=TelegramChannel)
        await self._ensure_channel("whatsapp-1", ChannelType.whatsapp_business, adapter_cls=WhatsAppBusinessChannel)

        # start adapters
        for cid, adapter in self.channels.items():
            await adapter.start(self.ingest_inbound)

    async def stop(self) -> None:
        for a in self.channels.values():
            await a.stop()
        self._release_lock()

    def _acquire_lock(self) -> None:
        # naive lockfile; in production use OS locks or DB advisory locks.
        if not self._lock_file:
            return
        if os.path.exists(self._lock_file):
            raise RuntimeError(f"Instance lock exists at {self._lock_file}. Another gateway may be running.")
        with open(self._lock_file, "w", encoding="utf-8") as f:
            f.write(self.settings.instance_id)

    def _release_lock(self) -> None:
        if self._lock_file and os.path.exists(self._lock_file):
            try:
                os.remove(self._lock_file)
            except Exception:
                pass

    async def _ensure_channel(self, channel_id: str, ctype: ChannelType, adapter_cls: type[ChannelAdapter]) -> None:
        ch = Channel(id=channel_id, type=ctype, status=ChannelStatus.offline, config={})
        self.channel_meta[channel_id] = ch
        self.channels[channel_id] = adapter_cls(ch)
        async with self.session_factory() as s:
            repo = Repo(s)
            await repo.upsert_channel(ch)
            await s.commit()

    async def list_channels(self) -> list[Channel]:
        async with self.session_factory() as s:
            repo = Repo(s)
            return await repo.list_channels()

    async def list_chats(self, channel_id: str | None) -> list[Chat]:
        async with self.session_factory() as s:
            repo = Repo(s)
            return await repo.list_chats(channel_id=channel_id)

    async def list_messages(self, chat_id: str, limit: int = 50) -> list[Message]:
        async with self.session_factory() as s:
            repo = Repo(s)
            return await repo.list_messages(chat_id=chat_id, limit=limit)

    async def tail_events(self, run_id: str | None, after_seq: int | None) -> list[Event]:
        async with self.session_factory() as s:
            repo = Repo(s)
            return await repo.tail_events(run_id=run_id, after_seq=after_seq, limit=200)

    async def ingest_inbound(self, env: InboundEnvelope) -> None:
        # sanitize
        cleaned, issues = sanitize_text(env.text)
        # policy check
        ok, reason = self.policy_engine.allow_sender(env.channel_id, env.sender_id, env.is_dm, env.is_group)
        if not ok:
            metrics.blocked_actions.labels(reason=reason).inc()
            await self._emit(None, EventType.security_blocked, {"reason":reason, "channel_id":env.channel_id, "sender_id":env.sender_id})
            return

        msg = Message(
            msg_id=gen_id("msg"),
            chat_id=env.chat_id,
            channel_id=env.channel_id,
            sender_id=env.sender_id,
            text=cleaned,
            timestamp=datetime.utcnow(),
            attachments=[],
            metadata={"sanitize_issues": issues, **(env.metadata or {})},
        )
        metrics.inbound_messages.labels(channel_type=self.channel_meta.get(env.channel_id).type.value if env.channel_id in self.channel_meta else "unknown").inc()

        async with self.session_factory() as s:
            repo = Repo(s)
            # ensure chat exists
            chat = Chat(chat_id=env.chat_id, channel_id=env.channel_id, participants=[env.sender_id], metadata=env.metadata or {})
            await repo.upsert_chat(chat)
            await repo.add_message(msg)
            await s.commit()

        await self._emit(None, EventType.message_inbound, {"message": msg.model_dump(mode="json")})

    async def start_run(self, chat_id: str, channel_id: str, requested_by: str, prompt: str) -> AgentRun:
        run = AgentRun(
            run_id=gen_id("run"),
            chat_id=chat_id,
            channel_id=channel_id,
            requested_by=requested_by,
            status=RunStatus.queued,
        )
        async with self.session_factory() as s:
            repo = Repo(s)
            await repo.upsert_run(run)
            await s.commit()

        # Build context: last N messages + the explicit prompt
        msgs = await self.list_messages(chat_id, limit=self.settings.max_context_messages)
        context = [{"role":"user", "content": m.text} for m in msgs]
        context.append({"role":"user", "content": prompt})

        task = asyncio.create_task(self._run_task(run, context))
        self._run_tasks[run.run_id] = task
        return run

    async def _run_task(self, run: AgentRun, context: list[dict[str, str]]) -> None:
        bind_run_id(run.run_id)
        async with self.session_factory() as s:
            repo = Repo(s)
            run = await self.runner.run(run, context)
            await repo.upsert_run(run)
            await s.commit()
        # final event
        await self._emit(run.run_id, EventType.run_completed, {"status": run.status.value, "summary": run.summary, "output_text": run.output_text})
        metrics.agent_runs.labels(status=run.status.value).inc()
        bind_run_id(None)

    async def grant_approval(self, run_id: str) -> bool:
        return self.runner.grant_approval(run_id)

    async def _emit(self, run_id: str | None, etype: EventType, payload: dict[str, Any]) -> None:
        seq = await self.bus.next_seq()
        evt = Event(run_id=run_id, seq=seq, type=etype, payload=payload, ts=datetime.utcnow())
        # persist for tailing
        async with self.session_factory() as s:
            repo = Repo(s)
            await repo.add_event(evt)
            await s.commit()
        await self.bus.publish(evt)
