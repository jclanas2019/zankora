"""OpenAI LLM adapter for Zankora Gateway.

Implements the LLMAdapter protocol using the OpenAI Chat Completions API
with tool/function calling support.

Model: gpt-4.1-mini
"""
from __future__ import annotations

import json
from typing import Any

from gateway.agent.llm import LLMAdapter, LLMResult
from gateway.observability.logging import get_logger

log = get_logger("openai_llm")

# Tool spec from ToolRegistry uses these keys — we map them to OpenAI function schema
_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}

OPENAI_MODEL = "gpt-4.1-mini"


def _build_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Zankora ToolSpec dicts to OpenAI function-calling format.

    ToolSpec fields (from domain/models.py or tools/registry.py):
        name, description, parameters (JSON Schema), read_only
    """
    openai_tools: list[dict[str, Any]] = []
    for t in tools:
        params = t.get("parameters") or {}
        # Ensure it's a valid JSON Schema object
        if not isinstance(params, dict):
            params = {}
        if "type" not in params:
            params = {"type": "object", "properties": params, "required": []}

        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": params,
                },
            }
        )
    return openai_tools


def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Normalize Zankora message format to OpenAI message format.

    Zankora uses role values: system | user | assistant | tool
    OpenAI accepts:          system | user | assistant | tool
    Tool messages need a 'tool_call_id' — we use a placeholder since Zankora
    doesn't track call IDs natively.
    """
    normalized: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "tool":
            # OpenAI requires tool_call_id; use a stable placeholder
            normalized.append(
                {
                    "role": "tool",
                    "tool_call_id": "zankora_tool_result",
                    "content": content,
                }
            )
        else:
            normalized.append({"role": role, "content": content})

    return normalized


class OpenAILLM:
    """OpenAI Chat Completions adapter.

    Uses ``gpt-4.1-mini`` and the native function/tool calling API.
    Requires the ``openai`` Python package and an OPENAI_API_KEY (set via
    AGW_OPENAI_API_KEY env var or the .env file).

    Usage — set in .env or environment:
        AGW_LLM_ADAPTER=openai
        AGW_OPENAI_API_KEY=sk-...

    Optional overrides:
        AGW_OPENAI_MODEL=gpt-4.1-mini       # default
        AGW_OPENAI_TEMPERATURE=0.2          # default
        AGW_OPENAI_MAX_TOKENS=1024          # default
    """

    def __init__(
        self,
        api_key: str,
        model: str = OPENAI_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        system_prompt: str | None = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAILLM. "
                "Install with: pip install openai"
            ) from exc

        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or (
            "You are a helpful assistant integrated into a secure agent gateway. "
            "Use the available tools when needed to complete the user's request. "
            "Be concise and accurate."
        )

        log.info("openai_llm_initialized", model=self.model)

    async def plan(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResult:
        """Call OpenAI and return a structured LLMResult.

        If the model decides to call one or more tools, ``tool_calls`` is
        populated and ``content`` will be empty/partial.
        If it produces a plain text answer, ``tool_calls`` is None.
        """
        # Prepend system prompt if not already present
        openai_messages: list[dict[str, Any]] = []
        if not messages or messages[0].get("role") != "system":
            openai_messages.append({"role": "system", "content": self.system_prompt})
        openai_messages.extend(_normalize_messages(messages))

        openai_tools = _build_openai_tools(tools) if tools else []

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"

        try:
            log.debug(
                "openai_request",
                model=self.model,
                messages_count=len(openai_messages),
                tools_count=len(openai_tools),
            )
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            log.exception("openai_api_error", error=str(exc))
            raise

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        message = choice.message

        log.debug(
            "openai_response",
            finish_reason=finish_reason,
            has_tool_calls=bool(message.tool_calls),
        )

        # --- Tool calls ---
        if message.tool_calls:
            parsed_calls: list[dict[str, Any]] = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    log.warning(
                        "openai_tool_args_parse_error",
                        tool=tc.function.name,
                        raw=tc.function.arguments,
                    )
                    args = {}

                parsed_calls.append(
                    {
                        "name": tc.function.name,
                        "args": args,
                    }
                )
                log.debug("openai_tool_call", tool=tc.function.name, args=args)

            return LLMResult(
                content=message.content or "",
                tool_calls=parsed_calls,
            )

        # --- Plain text answer ---
        content = message.content or ""
        return LLMResult(content=content, tool_calls=None)
