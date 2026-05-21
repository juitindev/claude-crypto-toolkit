"""Tool-use orchestration loop with streaming and prompt caching."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic

from crypto_toolkit.caching import cached_system_blocks, cached_tools, extract_usage
from crypto_toolkit.client_factory import get_client
from crypto_toolkit.prompts import SYSTEM_PROMPT
from crypto_toolkit.settings import get_settings
from crypto_toolkit.streaming import (
    Done,
    Error,
    Event,
    TextDelta,
    ToolUseResult,
    ToolUseStart,
)
from crypto_toolkit.tools import ToolError, get_tool, get_tool_definitions


class MaxToolRoundsExceeded(RuntimeError):
    """Raised when the conversation exceeds the configured tool-round ceiling."""


def run_conversation(
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    on_event: Callable[[Event], None] | None = None,
    *,
    client: Anthropic | None = None,
    model: str | None = None,
    max_rounds: int | None = None,
) -> list[dict[str, Any]]:
    """Run the Tool Use + streaming loop until the model emits ``end_turn``.

    Returns the updated message history (including assistant + tool turns)
    so a caller can keep state for multi-turn chats. Per-event hooks fire via
    ``on_event`` if provided; ``Done`` includes the final turn's usage block.
    """
    settings = get_settings()
    client = client or get_client()
    model = model or settings.model
    max_rounds = max_rounds or settings.max_tool_rounds
    emit: Callable[[Event], None] = on_event or (lambda _e: None)

    messages: list[dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": user_message})

    tools = cached_tools(get_tool_definitions())
    system = cached_system_blocks(SYSTEM_PROMPT)

    for _ in range(max_rounds):
        assistant_blocks, stop_reason, usage = _stream_one_turn(
            client=client,
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            emit=emit,
        )
        messages.append({"role": "assistant", "content": assistant_blocks})

        if stop_reason != "tool_use":
            emit(Done(stop_reason=stop_reason or "end_turn", usage=usage))
            return messages

        tool_results = _run_tool_calls(assistant_blocks, emit)
        messages.append({"role": "user", "content": tool_results})

    raise MaxToolRoundsExceeded(f"Exceeded {max_rounds} tool rounds without end_turn")


def _stream_one_turn(
    *,
    client: Anthropic,
    model: str,
    system: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    emit: Callable[[Event], None],
) -> tuple[list[dict[str, Any]], str, dict[str, int]]:
    """Stream one model turn, forward deltas, and return the final assistant blocks."""
    settings = get_settings()
    with client.messages.stream(
        model=model,
        max_tokens=settings.max_tokens,
        system=system,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        messages=messages,  # type: ignore[arg-type]
    ) as stream:
        for text in stream.text_stream:
            if text:
                emit(TextDelta(text=text))
        final = stream.get_final_message()

    blocks: list[dict[str, Any]] = []
    for block in final.content:
        kind = getattr(block, "type", None)
        if kind == "text":
            blocks.append({"type": "text", "text": getattr(block, "text", "")})
        elif kind == "tool_use":
            blocks.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", {}),
                }
            )
    return blocks, final.stop_reason or "end_turn", extract_usage(final.usage)


def _run_tool_calls(
    assistant_blocks: list[dict[str, Any]],
    emit: Callable[[Event], None],
) -> list[dict[str, Any]]:
    """Execute every tool_use block in ``assistant_blocks`` and return tool_result blocks."""
    results: list[dict[str, Any]] = []
    for block in assistant_blocks:
        if block.get("type") != "tool_use":
            continue
        tool_name = str(block.get("name"))
        tool_use_id = str(block.get("id"))
        tool_input = dict(block.get("input") or {})
        emit(ToolUseStart(tool_name=tool_name, tool_use_id=tool_use_id, input=tool_input))
        started = time.perf_counter()
        is_error = False
        try:
            tool = get_tool(tool_name)
            output = tool.execute(tool_input)
        except (ToolError, KeyError) as exc:
            is_error = True
            output = {"error": str(exc)}
            emit(Error(message=f"{tool_name} failed: {exc}"))
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit(
            ToolUseResult(
                tool_name=tool_name,
                tool_use_id=tool_use_id,
                output=output,
                duration_ms=duration_ms,
                is_error=is_error,
            )
        )
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": _serialise_tool_output(output),
                "is_error": is_error,
            }
        )
    return results


def _serialise_tool_output(output: dict[str, Any]) -> str:
    """Serialise tool output for the assistant. Charts include only metadata."""
    import json

    redacted = dict(output)
    if "image_base64" in redacted:
        redacted["image_base64"] = f"<{len(redacted['image_base64'])} bytes of PNG omitted>"
    return json.dumps(redacted, default=str)
