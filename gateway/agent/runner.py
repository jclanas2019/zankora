from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from gateway.agent.engine import AgentEngine
from gateway.agent.llm import LLMAdapter, MockLLM
from gateway.bus import EventBus
from gateway.domain.models import AgentRun, Event, EventType, RunStatus
from gateway.observability import metrics
from gateway.observability.logging import bind_run_id, get_logger
from gateway.security.policy_engine import PolicyEngine
from gateway.tools.registry import ToolRegistry

log = get_logger("agent")


@dataclass
class PendingApproval:
    run_id: str
    tool_name: str
    tool_args: dict[str, Any]
    requested_at: datetime


class AgentRunner(AgentEngine):
    """Simple agent engine - original MVP implementation."""

    def __init__(
        self,
        bus: EventBus,
        tools: ToolRegistry,
        policy_engine: PolicyEngine,
        llm: LLMAdapter | None = None,
        max_steps: int = 6,
        timeout_s: int = 45,
        retry: int = 1,
    ):
        self.bus = bus
        self.tools = tools
        self.policy = policy_engine
        self.llm = llm or MockLLM()
        self.max_steps = max_steps
        self.timeout_s = timeout_s
        self.retry = retry
        self._pending: dict[str, PendingApproval] = {}
        self._approval_events: dict[str, asyncio.Event] = {}

    def pending(self, run_id: str) -> PendingApproval | None:
        return self._pending.get(run_id)

    def grant_approval(self, run_id: str) -> bool:
        ev = self._approval_events.get(run_id)
        if not ev:
            return False
        ev.set()
        return True

    async def _emit(self, run_id: str | None, etype: EventType, payload: dict[str, Any]) -> None:
        seq = await self.bus.next_seq()
        evt = Event(run_id=run_id, seq=seq, type=etype, payload=payload, ts=datetime.utcnow())
        await self.bus.publish(evt)

    async def run(self, run: AgentRun, context_messages: list[dict[str, str]]) -> AgentRun:
        start = datetime.utcnow()
        run.started_at = start
        run.status = RunStatus.running
        bind_run_id(run.run_id)

        await self._emit(run.run_id, EventType.run_progress, {"status": "started", "at": start.isoformat()})

        tools_specs = [t.model_dump() for t in self.tools.list_specs()]

        output_chunks: list[str] = []

        try:
            # ✅ prometheus_client Histogram.time() is a SYNC context manager
            with metrics.agent_run_latency.time():
                for step in range(1, self.max_steps + 1):
                    await self._emit(run.run_id, EventType.run_progress, {"step": step, "status": "planning"})

                    # plan with timeout
                    plan = await asyncio.wait_for(
                        self.llm.plan(context_messages, tools_specs),
                        timeout=self.timeout_s,
                    )

                    if plan.tool_calls:
                        for call in plan.tool_calls:
                            tool_name = call.get("name", "") or ""
                            tool_args = call.get("args", {}) or {}

                            tool = self.tools.get(tool_name)
                            if not tool:
                                metrics.blocked_actions.labels(reason="tool_missing").inc()
                                await self._emit(
                                    run.run_id,
                                    EventType.security_blocked,
                                    {"reason": "tool_missing", "tool": tool_name},
                                )
                                continue

                            allowed, reason, needs_approval = self.policy.allow_tool(tool.spec)
                            if not allowed:
                                metrics.blocked_actions.labels(reason=reason).inc()
                                await self._emit(
                                    run.run_id,
                                    EventType.security_blocked,
                                    {"reason": reason, "tool": tool_name},
                                )
                                continue

                            if needs_approval:
                                # Park and wait
                                run.status = RunStatus.approval_pending  # ✅ enum value exists
                                pending = PendingApproval(
                                    run_id=run.run_id,
                                    tool_name=tool_name,
                                    tool_args=tool_args,
                                    requested_at=datetime.utcnow(),
                                )
                                self._pending[run.run_id] = pending
                                ev = asyncio.Event()
                                self._approval_events[run.run_id] = ev

                                await self._emit(
                                    run.run_id,
                                    EventType.run_tool_call,
                                    {"tool": tool_name, "args": tool_args, "approval_required": True},
                                )
                                await self._emit(run.run_id, EventType.run_progress, {"status": "waiting_approval"})

                                # Wait bounded
                                try:
                                    await asyncio.wait_for(ev.wait(), timeout=self.timeout_s)
                                except asyncio.TimeoutError:
                                    metrics.blocked_actions.labels(reason="approval_timeout").inc()
                                    await self._emit(
                                        run.run_id,
                                        EventType.security_blocked,
                                        {"reason": "approval_timeout", "tool": tool_name},
                                    )
                                    run.status = RunStatus.failed
                                    run.summary = "Approval timeout"
                                    return run
                                finally:
                                    self._pending.pop(run.run_id, None)
                                    self._approval_events.pop(run.run_id, None)

                                # resume running
                                run.status = RunStatus.running

                            await self._emit(
                                run.run_id,
                                EventType.run_tool_call,
                                {"tool": tool_name, "args": tool_args, "approval_required": False},
                            )

                            # execute tool with timeout
                            tool_res = await asyncio.wait_for(tool.handler(tool_args), timeout=self.timeout_s)

                            await self._emit(
                                run.run_id,
                                EventType.run_progress,
                                {"status": "tool_result", "tool": tool_name},
                            )

                            # Feed back as tool message
                            context_messages.append({"role": "tool", "content": f"{tool_name} -> {tool_res}"})

                            # Track tool usage
                            run.tools_called.append(tool_name)

                        # after tools, continue loop (re-plan)
                        continue

                    # no tool calls => output
                    content = plan.content or ""
                    output_chunks.append(content)
                    await self._emit(run.run_id, EventType.run_output, {"text": content})

                    # finalize after first answer in MVP
                    run.output_text = "\n".join([c for c in output_chunks if c]).strip()
                    run.summary = "Completed"
                    run.status = RunStatus.completed
                    return run

                # max steps reached
                run.output_text = "\n".join([c for c in output_chunks if c]).strip()
                run.summary = "Max steps reached"
                run.status = RunStatus.completed
                return run

        except asyncio.TimeoutError:
            run.status = RunStatus.failed
            run.summary = "Timeout"
            return run

        except Exception as e:
            log.exception("run_failed", run_id=run.run_id, err=str(e))
            run.status = RunStatus.failed
            run.summary = f"Failed: {type(e).__name__}"
            run.error = str(e)
            return run

        finally:
            end = datetime.utcnow()
            run.finished_at = end
            # optional semantic alias
            if run.status == RunStatus.completed and run.completed_at is None:
                run.completed_at = end

            # metrics & completion event
            try:
                if run.status == RunStatus.completed:
                    metrics.agent_runs.labels(status="completed").inc()
                else:
                    metrics.agent_runs.labels(status="failed").inc()

                await self._emit(
                    run.run_id,
                    EventType.run_completed,
                    {"status": run.status.value, "summary": run.summary, "output_text": run.output_text},
                )
            except Exception:
                # never crash in finally
                log.exception("emit_completed_failed", run_id=run.run_id)

            bind_run_id(None)
