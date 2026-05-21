"""Prompt-caching helpers.

We mark two cache breakpoints on every request:
1. The system prompt (large, stable, refusal rules embedded).
2. The tool definitions (stable schema across turns).

When both are unchanged across requests, Anthropic serves them from cache and
charges ``cache_read_input_tokens`` (cheap) instead of full input tokens.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CacheControl = dict[str, str]
EPHEMERAL: CacheControl = {"type": "ephemeral"}


def cached_system_blocks(system_prompt: str) -> list[dict[str, Any]]:
    """Return a system block list with an ephemeral cache breakpoint."""
    return [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": dict(EPHEMERAL),
        }
    ]


def cached_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of ``tools`` with a cache breakpoint on the final tool.

    Anthropic caches everything up to and including the last block carrying a
    ``cache_control`` marker, so a single marker on the last tool covers the
    entire tool array.
    """
    if not tools:
        return []
    cloned = [deepcopy(t) for t in tools]
    cloned[-1]["cache_control"] = dict(EPHEMERAL)
    return cloned


def extract_usage(usage: Any) -> dict[str, int]:
    """Extract cache-related counters from an SDK Usage object.

    Missing fields are reported as 0 so downstream callers can sum freely.
    """
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_creation_input_tokens": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        "cache_read_input_tokens": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
    }
