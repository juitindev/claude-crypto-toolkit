"""Tests for the orchestrator loop using a scripted fake Anthropic client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from crypto_toolkit.orchestrator import MaxToolRoundsExceeded, run_conversation
from crypto_toolkit.streaming import (
    Done,
    Event,
    TextDelta,
    ToolUseResult,
    ToolUseStart,
)


def _text_turn(text: str, *, usage: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "blocks": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "text_chunks": [text],
        "usage": usage or {"input_tokens": 100, "output_tokens": 20},
    }


def _tool_turn(name: str, inputs: dict[str, Any], tool_id: str = "toolu_1") -> dict[str, Any]:
    return {
        "blocks": [
            {"type": "text", "text": "Looking up data..."},
            {"type": "tool_use", "id": tool_id, "name": name, "input": inputs},
        ],
        "stop_reason": "tool_use",
        "text_chunks": ["Looking up data..."],
        "usage": {"input_tokens": 200, "output_tokens": 30},
    }


def test_simple_text_turn(fake_anthropic_client: Any) -> None:
    fake_anthropic_client.messages.script(_text_turn("Hello world."))
    events: list[Event] = []
    history = run_conversation(
        user_message="hi",
        on_event=events.append,
        client=fake_anthropic_client,
    )
    assert any(isinstance(e, TextDelta) for e in events)
    done = [e for e in events if isinstance(e, Done)]
    assert done and done[0].stop_reason == "end_turn"
    assert history[-1]["role"] == "assistant"


def test_tool_call_round_trip(
    fake_anthropic_client: Any,
    mock_binance: respx.MockRouter,
) -> None:
    mock_binance.get("/api/v3/ticker/price", params={"symbol": "BTCUSDT"}).mock(
        return_value=httpx.Response(200, json={"symbol": "BTCUSDT", "price": "67000.00"})
    )
    fake_anthropic_client.messages.script(
        _tool_turn("get_price", {"symbol": "BTCUSDT"}),
        _text_turn("BTC is at $67,000."),
    )

    events: list[Event] = []
    history = run_conversation(
        user_message="What's BTC at?",
        on_event=events.append,
        client=fake_anthropic_client,
    )
    starts = [e for e in events if isinstance(e, ToolUseStart)]
    results = [e for e in events if isinstance(e, ToolUseResult)]
    assert starts and results
    assert starts[0].tool_name == "get_price"
    assert results[0].is_error is False
    assert any(msg["role"] == "user" and isinstance(msg["content"], list) for msg in history)


def test_tool_error_is_reported(fake_anthropic_client: Any) -> None:
    fake_anthropic_client.messages.script(
        _tool_turn("get_price", {}),  # missing symbol -> ToolError
        _text_turn("Sorry, that failed."),
    )
    events: list[Event] = []
    run_conversation(
        user_message="What's BTC at?",
        on_event=events.append,
        client=fake_anthropic_client,
    )
    results = [e for e in events if isinstance(e, ToolUseResult)]
    assert results and results[0].is_error is True
    assert "error" in results[0].output


def test_unknown_tool_returns_error_result(fake_anthropic_client: Any) -> None:
    fake_anthropic_client.messages.script(
        _tool_turn("does_not_exist", {}),
        _text_turn("ok"),
    )
    events: list[Event] = []
    run_conversation(
        user_message="hi",
        on_event=events.append,
        client=fake_anthropic_client,
    )
    results = [e for e in events if isinstance(e, ToolUseResult)]
    assert results and results[0].is_error is True


def test_max_rounds_enforced(fake_anthropic_client: Any) -> None:
    # Always return another tool_use; we cap rounds at 2 so loop must raise.
    fake_anthropic_client.messages.script(
        *[_tool_turn("get_market_overview", {}, tool_id=f"toolu_{i}") for i in range(10)]
    )
    with pytest.raises(MaxToolRoundsExceeded):
        run_conversation(
            user_message="loop",
            client=fake_anthropic_client,
            max_rounds=2,
        )


def test_history_preserved_across_turns(fake_anthropic_client: Any) -> None:
    fake_anthropic_client.messages.script(_text_turn("first"))
    h1 = run_conversation(user_message="one", client=fake_anthropic_client)
    fake_anthropic_client.messages.script(_text_turn("second"))
    h2 = run_conversation(user_message="two", history=h1, client=fake_anthropic_client)
    user_msgs = [m for m in h2 if m["role"] == "user"]
    assert len(user_msgs) >= 2
    assert user_msgs[0]["content"] == "one"
    assert user_msgs[1]["content"] == "two"
