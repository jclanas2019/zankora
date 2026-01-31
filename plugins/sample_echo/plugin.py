from __future__ import annotations
from gateway.domain.models import ToolSpec, ToolPermission
from gateway.plugins.registry import PluginRegistry

def register(registry: PluginRegistry) -> None:
    async def upper(args: dict):
        text = (args.get("text") or "")
        return {"upper": text.upper()}

    registry.tools.register(
        ToolSpec(
            name="sample.upper",
            permission=ToolPermission.read,
            description="Uppercase a string.",
            args_schema={"type":"object","properties":{"text":{"type":"string"}},"required":["text"]},
        ),
        upper,
    )
