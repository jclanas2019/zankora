from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional
from gateway.domain.models import ToolSpec, ToolPermission

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

@dataclass
class Tool:
    spec: ToolSpec
    handler: ToolHandler

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = Tool(spec=spec, handler=handler)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

def builtins_registry() -> ToolRegistry:
    reg = ToolRegistry()

    async def echo(args: dict[str, Any]) -> dict[str, Any]:
        return {"echo": args}

    reg.register(
        ToolSpec(
            name="core.echo",
            permission=ToolPermission.read,
            description="Echo args (debug).",
            args_schema={"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},
        ),
        echo,
    )
    return reg
