"""Factory for the Anthropic SDK client."""

from __future__ import annotations

from functools import lru_cache

from anthropic import Anthropic

from crypto_toolkit.settings import get_settings


@lru_cache(maxsize=1)
def get_client() -> Anthropic:
    """Return a process-wide Anthropic client instance."""
    settings = get_settings()
    return Anthropic(api_key=settings.anthropic_api_key)
