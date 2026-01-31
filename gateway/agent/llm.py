from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class LLMResult:
    content: str
    tool_calls: list[dict[str, Any]] | None = None  # [{"name": "...", "args": {...}}]

class LLMAdapter(Protocol):
    async def plan(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> LLMResult: ...

class MockLLM:
    """Deterministic mock planner.
    - If user message contains 'tool:' triggers tool call: tool:<name> <jsonargs?>
    - Else replies with a simple transformation.
    """
    async def plan(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> LLMResult:
        last = (messages[-1]["content"] if messages else "").strip()
        if last.lower().startswith("tool:"):
            # Format: tool:core.echo {"text":"hi"}
            parts = last.split(" ", 2)
            name = parts[0].split(":",1)[1]
            args = {}
            if len(parts) >= 2:
                import json
                try:
                    args = json.loads(parts[1] if len(parts)==2 else parts[1] + " " + parts[2])
                except Exception:
                    args = {"text": "invalid_json_args"}
            return LLMResult(content="calling tool", tool_calls=[{"name": name, "args": args}])
        # otherwise
        return LLMResult(content=f"MockLLM: recibí: {last}")
