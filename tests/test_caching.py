"""Tests for prompt-caching helpers."""

from __future__ import annotations

from typing import Any

from crypto_toolkit.caching import (
    EPHEMERAL,
    cached_system_blocks,
    cached_tools,
    extract_usage,
)


def test_system_block_carries_cache_control() -> None:
    blocks = cached_system_blocks("hello")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "hello"
    assert blocks[0]["cache_control"] == EPHEMERAL


def test_cached_tools_marks_last_tool_only() -> None:
    tools: list[dict[str, Any]] = [
        {"name": "a", "description": "a", "input_schema": {}},
        {"name": "b", "description": "b", "input_schema": {}},
        {"name": "c", "description": "c", "input_schema": {}},
    ]
    out = cached_tools(tools)
    assert "cache_control" not in out[0]
    assert "cache_control" not in out[1]
    assert out[2]["cache_control"] == EPHEMERAL
    # Source must not be mutated.
    assert "cache_control" not in tools[-1]


def test_cached_tools_empty_list() -> None:
    assert cached_tools([]) == []


def test_extract_usage_handles_missing_fields() -> None:
    class _U:
        input_tokens = 100
        output_tokens = 25

    parsed = extract_usage(_U())
    assert parsed["input_tokens"] == 100
    assert parsed["output_tokens"] == 25
    assert parsed["cache_creation_input_tokens"] == 0
    assert parsed["cache_read_input_tokens"] == 0


def test_extract_usage_full() -> None:
    class _U:
        input_tokens = 10
        output_tokens = 5
        cache_creation_input_tokens = 800
        cache_read_input_tokens = 0

    assert extract_usage(_U())["cache_creation_input_tokens"] == 800


def test_extract_usage_second_run_reads_cache() -> None:
    class _U:
        input_tokens = 10
        output_tokens = 5
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 800

    assert extract_usage(_U())["cache_read_input_tokens"] == 800
