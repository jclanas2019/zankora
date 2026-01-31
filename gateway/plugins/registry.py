from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from gateway.channels.base import ChannelAdapter
from gateway.domain.models import ToolSpec
from gateway.tools.registry import ToolRegistry

Hook = Callable[..., Awaitable[None]]


@dataclass
class PluginRegistry:
    tools: ToolRegistry
    channels: dict[str, type[ChannelAdapter]] = field(default_factory=dict)
    commands: dict[str, Callable[..., Awaitable[dict]]] = field(default_factory=dict)
    hooks_pre_message: list[Hook] = field(default_factory=list)
    hooks_post_run: list[Hook] = field(default_factory=list)

    # ----------------------------------------------------------------------
    # Channels / Commands / Hooks (native API)
    # ----------------------------------------------------------------------

    def register_channel(self, name: str, cls: type[ChannelAdapter]) -> None:
        self.channels[name] = cls

    def register_command(self, name: str, handler: Callable[..., Awaitable[dict]]) -> None:
        self.commands[name] = handler

    def hook_pre_message(self, hook: Hook) -> None:
        self.hooks_pre_message.append(hook)

    def hook_post_run(self, hook: Hook) -> None:
        self.hooks_post_run.append(hook)

    # ----------------------------------------------------------------------
    # Tools (compatibility API)
    # ----------------------------------------------------------------------
    # Support BOTH plugin styles:
    #   1) registry.register_tool(spec, handler)
    #   2) registry.register_tool(spec)   # handler is spec.func
    #
    # New plugins should prefer: registry.tools.register(spec, handler)

    def register_tool(
        self,
        spec: ToolSpec,
        handler: Optional[Callable[..., Awaitable[dict[str, Any]]]] = None,
    ) -> None:
        if handler is None:
            # fallback to ToolSpec.func
            if spec.func is None:
                raise TypeError(
                    "register_tool(spec) requires spec.func to be set when handler is not provided"
                )
            # tool functions might not be async; assume plugin provided async, but allow sync by wrapping
            fn = spec.func

            async def _wrapped(args: dict[str, Any]) -> dict[str, Any]:
                res = fn(args)  # type: ignore[misc]
                return res  # expected dict

            handler = _wrapped

        self.tools.register(spec, handler)

    def register_tools(
        self,
        tools: list[tuple[ToolSpec, Callable[..., Awaitable[dict[str, Any]]]]],
    ) -> None:
        for spec, handler in tools:
            self.tools.register(spec, handler)
