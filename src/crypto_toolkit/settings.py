"""Configuration loaded from environment variables via python-dotenv."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-4-5"


class Settings(BaseModel):
    """Runtime configuration."""

    anthropic_api_key: str = Field(..., description="Anthropic API key.")
    model: str = Field(default=DEFAULT_MODEL, description="Claude model identifier.")
    max_tool_rounds: int = Field(default=8, ge=1, le=32)
    max_tokens: int = Field(default=2048, ge=64, le=8192)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance loaded from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    model = os.environ.get("CRYPTO_TOOLKIT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return Settings(anthropic_api_key=api_key, model=model)
