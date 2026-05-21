"""Tests for streaming event helpers."""

from __future__ import annotations

import json

import pytest

from crypto_toolkit.streaming import (
    Done,
    Error,
    TextDelta,
    ToolUseResult,
    ToolUseStart,
    event_to_sse,
)


def test_text_delta_event() -> None:
    name, payload = event_to_sse(TextDelta(text="hello"))
    assert name == "text_delta"
    assert payload == {"text": "hello"}


def test_tool_use_start_event() -> None:
    name, payload = event_to_sse(
        ToolUseStart(tool_name="get_price", tool_use_id="u1", input={"symbol": "BTC"})
    )
    assert name == "tool_use"
    assert payload["tool_name"] == "get_price"
    assert payload["input"]["symbol"] == "BTC"


def test_tool_use_result_event() -> None:
    name, payload = event_to_sse(
        ToolUseResult(
            tool_name="get_price",
            tool_use_id="u1",
            output={"symbol": "BTC", "price": 67000.0},
            duration_ms=42,
        )
    )
    assert name == "tool_result"
    assert payload["duration_ms"] == 42
    assert payload["is_error"] is False


def test_done_event_includes_usage() -> None:
    name, payload = event_to_sse(Done(stop_reason="end_turn", usage={"input_tokens": 5}))
    assert name == "done"
    assert payload["usage"] == {"input_tokens": 5}


def test_error_event() -> None:
    name, payload = event_to_sse(Error(message="boom"))
    assert name == "error"
    assert payload["message"] == "boom"


def test_unknown_event_type_raises() -> None:
    with pytest.raises(TypeError):
        event_to_sse(object())  # type: ignore[arg-type]


def test_sse_payload_is_json_serialisable() -> None:
    name, payload = event_to_sse(
        ToolUseResult(
            tool_name="make_chart",
            tool_use_id="u1",
            output={"image_base64": "X" * 32, "candles": 3},
            duration_ms=10,
        )
    )
    json.dumps(payload)  # raises if not serialisable
    assert name == "tool_result"
