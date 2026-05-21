"""Typed events emitted by the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolUseStart:
    tool_name: str
    tool_use_id: str
    input: dict[str, Any]


@dataclass
class ToolUseResult:
    tool_name: str
    tool_use_id: str
    output: dict[str, Any]
    duration_ms: int
    is_error: bool = False


@dataclass
class Done:
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class Error:
    message: str


Event = TextDelta | ToolUseStart | ToolUseResult | Done | Error


def event_to_sse(event: Event) -> tuple[str, dict[str, Any]]:
    """Return an ``(event_name, payload)`` pair suitable for SSE serialisation."""
    if isinstance(event, TextDelta):
        return "text_delta", {"text": event.text}
    if isinstance(event, ToolUseStart):
        return "tool_use", {
            "tool_name": event.tool_name,
            "tool_use_id": event.tool_use_id,
            "input": event.input,
        }
    if isinstance(event, ToolUseResult):
        return "tool_result", {
            "tool_name": event.tool_name,
            "tool_use_id": event.tool_use_id,
            "output": event.output,
            "duration_ms": event.duration_ms,
            "is_error": event.is_error,
        }
    if isinstance(event, Done):
        return "done", {"stop_reason": event.stop_reason, "usage": event.usage}
    if isinstance(event, Error):
        return "error", {"message": event.message}
    raise TypeError(f"Unknown event type: {type(event).__name__}")
