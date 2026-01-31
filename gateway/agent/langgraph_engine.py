"""LangGraph-based agent engine with structured state graph."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from gateway.agent.engine import AgentEngine
from gateway.agent.llm import LLMAdapter, MockLLM
from gateway.bus import EventBus
from gateway.domain.models import AgentRun, Event, EventType, RunStatus
from gateway.observability.logging import get_logger, bind_run_id
from gateway.observability import metrics
from gateway.security.policy_engine import PolicyEngine
from gateway.tools.registry import ToolRegistry

log = get_logger("langgraph_engine")

# Check if LangGraph is available
try:
    from langgraph.graph import StateGraph, END
    from typing import TypedDict
    LANGGRAPH_AVAILABLE = True
except ImportError:
    log.warning("LangGraph not installed. Install with: pip install -e .[agentic]")
    LANGGRAPH_AVAILABLE = False
    # Dummy classes for type checking
    StateGraph = None  # type: ignore
    END = "END"  # type: ignore
    class TypedDict:  # type: ignore
        pass


@dataclass
class PendingApproval:
    """Pending tool approval."""
    run_id: str
    tool_name: str
    tool_args: dict[str, Any]
    requested_at: datetime


# State for LangGraph
if LANGGRAPH_AVAILABLE:
    class GraphState(TypedDict):
        """State for the agent graph."""
        run_id: str
        chat_id: str
        channel_id: str
        requested_by: str
        messages: list[dict[str, str]]
        step: int
        plan: str | None
        tool_request: dict[str, Any] | None  # {name, args}
        tool_result: dict[str, Any] | None
        output_chunks: list[str]
        needs_approval: bool
        blocked_reason: str | None
        done: bool
        max_steps: int
        timeout_s: int
else:
    # Placeholder for when LangGraph is not installed
    GraphState = dict  # type: ignore


class LangGraphEngine(AgentEngine):
    """
    LangGraph-based agent execution engine.
    
    This engine uses LangGraph to orchestrate agent runs with a structured state graph.
    All tools are executed via ToolRegistry + PolicyEngine respecting the single-authority principle.
    """

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
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph is not installed. Install with: pip install -e .[agentic]"
            )

        self.bus = bus
        self.tools = tools
        self.policy = policy_engine
        self.llm = llm or MockLLM()
        self.max_steps = max_steps
        self.timeout_s = timeout_s
        self.retry = retry

        # Approval mechanism
        self._pending: dict[str, PendingApproval] = {}
        self._approval_events: dict[str, asyncio.Event] = {}

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph state graph."""
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("build_context", self._build_context)
        workflow.add_node("plan", self._plan)
        workflow.add_node("policy_check", self._policy_check)
        workflow.add_node("wait_approval", self._wait_approval)
        workflow.add_node("execute_tool", self._execute_tool)
        workflow.add_node("decide_next", self._decide_next)
        workflow.add_node("ask_clarification", self._ask_clarification)
        workflow.add_node("finalize", self._finalize)

        # Set entry point
        workflow.set_entry_point("build_context")

        # Add edges
        workflow.add_edge("build_context", "plan")
        
        # From plan, check if we have a tool request
        workflow.add_conditional_edges(
            "plan",
            lambda state: "policy_check" if state.get("tool_request") else "decide_next",
        )

        # From policy_check, either wait for approval, execute, or decide next
        workflow.add_conditional_edges(
            "policy_check",
            lambda state: (
                "wait_approval" if state.get("needs_approval") else
                "decide_next" if state.get("blocked_reason") else
                "execute_tool"
            ),
        )

        workflow.add_edge("wait_approval", "execute_tool")
        workflow.add_edge("execute_tool", "decide_next")

        # From decide_next, either finalize, plan again, or ask clarification
        workflow.add_conditional_edges(
            "decide_next",
            lambda state: (
                "finalize" if state.get("done") else
                "ask_clarification" if state.get("blocked_reason") and not state.get("output_chunks") else
                "plan"
            ),
        )

        workflow.add_edge("ask_clarification", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def _emit(self, run_id: str | None, etype: EventType, payload: dict[str, Any]) -> None:
        """Emit event to the bus."""
        seq = await self.bus.next_seq()
        evt = Event(run_id=run_id, seq=seq, type=etype, payload=payload, ts=datetime.utcnow())
        await self.bus.publish(evt)

    async def _build_context(self, state: GraphState) -> GraphState:
        """Build context node."""
        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "build_context", "phase": "start", "step": state["step"]},
        )

        # Context is already built, just log
        log.debug("build_context", run_id=state["run_id"], messages_count=len(state["messages"]))

        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "build_context", "phase": "end", "step": state["step"]},
        )

        return state

    async def _plan(self, state: GraphState) -> GraphState:
        """Planning node - call LLM to decide next action."""
        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "plan", "phase": "start", "step": state["step"]},
        )

        tools_specs = [t.model_dump() for t in self.tools.list_specs()]

        try:
            plan = await asyncio.wait_for(
                self.llm.plan(state["messages"], tools_specs),
                timeout=state["timeout_s"],
            )

            if plan.tool_calls:
                # Take first tool call (MVP)
                call = plan.tool_calls[0]
                state["tool_request"] = {
                    "name": call.get("name", ""),
                    "args": call.get("args", {}) or {},
                }
                state["plan"] = f"Tool requested: {call.get('name')}"
                log.debug("plan_tool", run_id=state["run_id"], tool=call.get("name"))
            else:
                # LLM returned content
                state["tool_request"] = None
                state["plan"] = plan.content
                if plan.content:
                    state["output_chunks"].append(plan.content)
                log.debug("plan_output", run_id=state["run_id"], output_length=len(plan.content))

        except asyncio.TimeoutError:
            log.error("plan_timeout", run_id=state["run_id"])
            state["tool_request"] = None
            state["blocked_reason"] = "planning_timeout"

        except Exception as e:
            log.exception("plan_error", run_id=state["run_id"], error=str(e))
            state["tool_request"] = None
            state["blocked_reason"] = f"planning_error: {type(e).__name__}"

        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "plan", "phase": "end", "step": state["step"], "plan": state.get("plan")},
        )

        return state

    async def _policy_check(self, state: GraphState) -> GraphState:
        """Policy check node - validate tool execution permissions."""
        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "policy_check", "phase": "start", "step": state["step"]},
        )

        tool_request = state.get("tool_request")
        if not tool_request:
            return state

        tool_name = tool_request["name"]
        tool_args = tool_request["args"]

        # Check if tool exists
        tool = self.tools.get(tool_name)
        if not tool:
            log.warning("policy_tool_missing", run_id=state["run_id"], tool=tool_name)
            await self._emit(
                state["run_id"],
                EventType.security_blocked,
                {"reason": "tool_missing", "tool": tool_name},
            )
            metrics.blocked_actions.labels(reason="tool_missing").inc()
            state["blocked_reason"] = "tool_missing"
            state["tool_request"] = None
            return state

        # Check policy
        allowed, reason, needs_approval = self.policy.allow_tool(tool.spec)

        if not allowed:
            log.warning("policy_denied", run_id=state["run_id"], tool=tool_name, reason=reason)
            await self._emit(
                state["run_id"],
                EventType.security_blocked,
                {"reason": reason, "tool": tool_name},
            )
            metrics.blocked_actions.labels(reason=reason).inc()
            state["blocked_reason"] = reason
            state["tool_request"] = None
            return state

        if needs_approval:
            log.info("policy_approval_required", run_id=state["run_id"], tool=tool_name)
            state["needs_approval"] = True
        else:
            state["needs_approval"] = False

        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {
                "node": "policy_check",
                "phase": "end",
                "step": state["step"],
                "allowed": allowed,
                "needs_approval": needs_approval,
            },
        )

        return state

    async def _wait_approval(self, state: GraphState) -> GraphState:
        """Wait for human approval."""
        tool_request = state.get("tool_request")
        if not tool_request:
            return state

        tool_name = tool_request["name"]
        tool_args = tool_request["args"]
        run_id = state["run_id"]

        log.info("waiting_approval", run_id=run_id, tool=tool_name)

        # Create pending approval
        pending = PendingApproval(
            run_id=run_id,
            tool_name=tool_name,
            tool_args=tool_args,
            requested_at=datetime.utcnow(),
        )
        self._pending[run_id] = pending

        # Create event
        ev = asyncio.Event()
        self._approval_events[run_id] = ev

        # Emit approval required event
        await self._emit(
            run_id,
            EventType.run_tool_call,
            {"tool": tool_name, "args": tool_args, "approval_required": True},
        )

        await self._emit(
            run_id,
            EventType.run_progress,
            {"node": "wait_approval", "phase": "waiting", "step": state["step"]},
        )

        # Wait for approval with timeout
        try:
            await asyncio.wait_for(ev.wait(), timeout=state["timeout_s"])
            log.info("approval_granted", run_id=run_id, tool=tool_name)
            state["needs_approval"] = False
        except asyncio.TimeoutError:
            log.error("approval_timeout", run_id=run_id, tool=tool_name)
            metrics.blocked_actions.labels(reason="approval_timeout").inc()
            await self._emit(
                run_id,
                EventType.security_blocked,
                {"reason": "approval_timeout", "tool": tool_name},
            )
            state["blocked_reason"] = "approval_timeout"
            state["tool_request"] = None
            state["done"] = True
        finally:
            self._pending.pop(run_id, None)
            self._approval_events.pop(run_id, None)

        return state

    async def _execute_tool(self, state: GraphState) -> GraphState:
        """Execute tool node."""
        tool_request = state.get("tool_request")
        if not tool_request:
            return state

        tool_name = tool_request["name"]
        tool_args = tool_request["args"]
        run_id = state["run_id"]

        await self._emit(
            run_id,
            EventType.run_progress,
            {"node": "execute_tool", "phase": "start", "step": state["step"]},
        )

        # Emit tool call event (non-approval)
        await self._emit(
            run_id,
            EventType.run_tool_call,
            {"tool": tool_name, "args": tool_args, "approval_required": False},
        )

        tool = self.tools.get(tool_name)
        if not tool:
            log.error("execute_tool_missing", run_id=run_id, tool=tool_name)
            state["blocked_reason"] = "tool_missing"
            state["tool_request"] = None
            return state

        try:
            # Execute tool with timeout
            tool_result = await asyncio.wait_for(
                tool.handler(tool_args), timeout=state["timeout_s"]
            )
            log.debug("tool_executed", run_id=run_id, tool=tool_name, result=str(tool_result)[:100])

            # Store result
            state["tool_result"] = {"tool": tool_name, "result": tool_result}

            # Add to messages as tool response
            state["messages"].append({
                "role": "tool",
                "content": f"{tool_name} -> {tool_result}",
            })

            await self._emit(
                run_id,
                EventType.run_progress,
                {"node": "execute_tool", "phase": "result", "step": state["step"], "tool": tool_name},
            )

        except asyncio.TimeoutError:
            log.error("tool_timeout", run_id=run_id, tool=tool_name)
            state["blocked_reason"] = "tool_timeout"

        except Exception as e:
            log.exception("tool_error", run_id=run_id, tool=tool_name, error=str(e))
            state["blocked_reason"] = f"tool_error: {type(e).__name__}"

        # Clear tool request
        state["tool_request"] = None

        return state

    async def _decide_next(self, state: GraphState) -> GraphState:
        """Decide next action node."""
        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "decide_next", "phase": "start", "step": state["step"]},
        )

        # Check if we have output
        if state.get("output_chunks"):
            log.debug("decide_has_output", run_id=state["run_id"])
            state["done"] = True
            await self._emit(
                state["run_id"],
                EventType.run_output,
                {"text": "\n".join(state["output_chunks"])},
            )
            return state

        # Check if blocked without output
        if state.get("blocked_reason") and not state.get("output_chunks"):
            log.warning("decide_blocked_no_output", run_id=state["run_id"], reason=state["blocked_reason"])
            # Will trigger ask_clarification
            return state

        # Check max steps
        if state["step"] >= state["max_steps"]:
            log.info("decide_max_steps", run_id=state["run_id"], step=state["step"])
            state["done"] = True
            if not state.get("output_chunks"):
                state["output_chunks"].append("I've reached the maximum number of steps without completing the task.")
            return state

        # Continue with next step
        state["step"] += 1
        log.debug("decide_continue", run_id=state["run_id"], next_step=state["step"])

        return state

    async def _ask_clarification(self, state: GraphState) -> GraphState:
        """Fallback node to ask for clarification."""
        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "ask_clarification", "phase": "start", "step": state["step"]},
        )

        reason = state.get("blocked_reason", "unknown")
        clarification = f"I encountered an issue ({reason}) and couldn't complete the task. Could you provide more information or rephrase your request?"

        state["output_chunks"].append(clarification)
        state["done"] = True

        log.info("ask_clarification", run_id=state["run_id"], reason=reason)

        await self._emit(
            state["run_id"],
            EventType.run_output,
            {"text": clarification},
        )

        return state

    async def _finalize(self, state: GraphState) -> GraphState:
        """Finalize the run."""
        await self._emit(
            state["run_id"],
            EventType.run_progress,
            {"node": "finalize", "phase": "start", "step": state["step"]},
        )

        # This is just for logging, actual run update happens in run() method
        log.info("finalize", run_id=state["run_id"], output_chunks=len(state["output_chunks"]))

        return state

    async def run(self, run: AgentRun, context_messages: list[dict[str, str]]) -> AgentRun:
        """Execute agent run using LangGraph."""
        start = datetime.utcnow()
        run.started_at = start
        run.status = RunStatus.running
        bind_run_id(run.run_id)

        await self._emit(
            run.run_id,
            EventType.run_progress,
            {"status": "started", "at": start.isoformat(), "engine": "langgraph"},
        )

        # Initialize state
        initial_state: GraphState = {
            "run_id": run.run_id,
            "chat_id": run.chat_id,
            "channel_id": run.channel_id,
            "requested_by": run.requested_by,
            "messages": context_messages.copy(),
            "step": 1,
            "plan": None,
            "tool_request": None,
            "tool_result": None,
            "output_chunks": [],
            "needs_approval": False,
            "blocked_reason": None,
            "done": False,
            "max_steps": self.max_steps,
            "timeout_s": self.timeout_s,
        }

        try:
            async with metrics.agent_run_latency.time():
                # Run the graph
                final_state = await self.graph.ainvoke(initial_state)

                # Extract results
                output_chunks = final_state.get("output_chunks", [])
                run.output_text = "\n".join(output_chunks) if output_chunks else ""

                if final_state.get("blocked_reason") == "approval_timeout":
                    run.status = RunStatus.failed
                    run.summary = "Approval timeout"
                elif final_state.get("blocked_reason"):
                    run.status = RunStatus.completed
                    run.summary = f"Completed with issues: {final_state['blocked_reason']}"
                else:
                    run.status = RunStatus.completed
                    run.summary = "Completed successfully"

                log.info(
                    "run_completed",
                    run_id=run.run_id,
                    status=run.status.value,
                    steps=final_state.get("step", 0),
                )

                return run

        except asyncio.TimeoutError:
            run.status = RunStatus.failed
            run.summary = "Timeout"
            metrics.agent_runs.labels(status="failed").inc()
            await self._emit(
                run.run_id,
                EventType.run_completed,
                {"status": "failed", "reason": "timeout"},
            )
            log.error("run_timeout", run_id=run.run_id)
            return run

        except Exception as e:
            log.exception("run_failed", run_id=run.run_id, error=str(e))
            run.status = RunStatus.failed
            run.summary = f"Failed: {type(e).__name__}"
            metrics.agent_runs.labels(status="failed").inc()
            await self._emit(
                run.run_id,
                EventType.run_completed,
                {"status": "failed", "reason": str(e)},
            )
            return run

        finally:
            end = datetime.utcnow()
            run.finished_at = end
            bind_run_id(None)

    def grant_approval(self, run_id: str) -> bool:
        """Grant approval for a pending tool execution."""
        ev = self._approval_events.get(run_id)
        if not ev:
            return False
        ev.set()
        return True
