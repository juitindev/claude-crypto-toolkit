"""Shared fixtures for tool, orchestrator, and caching tests."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import respx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _set_api_key(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee settings.get_settings() never explodes during unit tests.

    Live tests need the real ANTHROPIC_API_KEY from the environment, so don't
    stomp it; just clear caches so the real client gets rebuilt.
    """
    from crypto_toolkit import client_factory, settings

    if request.node.get_closest_marker("live"):
        settings.get_settings.cache_clear()
        client_factory.get_client.cache_clear()
        return

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("CRYPTO_TOOLKIT_MODEL", "claude-sonnet-4-5")
    settings.get_settings.cache_clear()
    client_factory.get_client.cache_clear()


@pytest.fixture
def sample_klines() -> list[list[Any]]:
    return json.loads((FIXTURES_DIR / "sample_klines.json").read_text())


@pytest.fixture
def mock_binance() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url="https://api.binance.com", assert_all_called=False) as router:
        yield router


@pytest.fixture
def mock_coingecko() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url="https://api.coingecko.com", assert_all_called=False) as router:
        yield router


# ---------- Fake Anthropic client for orchestrator tests ----------


class _FakeStream:
    def __init__(self, text_chunks: list[str], final_message: Any) -> None:
        self._text_chunks = text_chunks
        self._final_message = final_message
        self.text_stream = iter(text_chunks)

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get_final_message(self) -> Any:
        return self._final_message


class _FakeMessages:
    def __init__(self) -> None:
        self.scripted: list[Any] = []
        self.calls: list[dict[str, Any]] = []

    def script(self, *responses: Any) -> None:
        self.scripted = list(responses)

    @contextmanager
    def stream(self, **kwargs: Any) -> Iterator[_FakeStream]:
        if not self.scripted:
            raise RuntimeError("FakeMessages.stream called with empty script")
        spec = self.scripted.pop(0)
        self.calls.append({"kwargs": kwargs})
        text_chunks = spec.get("text_chunks", [])
        yield _FakeStream(text_chunks, _FakeFinalMessage(spec))

    def create(self, **kwargs: Any) -> Any:
        if not self.scripted:
            raise RuntimeError("FakeMessages.create called with empty script")
        spec = self.scripted.pop(0)
        self.calls.append({"kwargs": kwargs})
        return _FakeFinalMessage(spec)


class _FakeFinalMessage:
    def __init__(self, spec: dict[str, Any]) -> None:
        self.content = [_FakeBlock(b) for b in spec.get("blocks", [])]
        self.stop_reason = spec.get("stop_reason", "end_turn")
        self.usage = _FakeUsage(spec.get("usage", {}))


class _FakeBlock:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.type = payload["type"]
        if self.type == "text":
            self.text = payload["text"]
        elif self.type == "tool_use":
            self.id = payload["id"]
            self.name = payload["name"]
            self.input = payload.get("input", {})


class _FakeUsage:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.input_tokens = payload.get("input_tokens", 0)
        self.output_tokens = payload.get("output_tokens", 0)
        self.cache_creation_input_tokens = payload.get("cache_creation_input_tokens", 0)
        self.cache_read_input_tokens = payload.get("cache_read_input_tokens", 0)


@pytest.fixture
def fake_anthropic_client() -> MagicMock:
    client = MagicMock()
    client.messages = _FakeMessages()
    return client


# ---------- Live test gating ----------


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip live tests unless explicitly selected and ANTHROPIC_API_KEY is real."""
    if config.getoption("-m") and "live" in str(config.getoption("-m")):
        if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant"):
            return
        skip_live = pytest.mark.skip(reason="Live tests require a real ANTHROPIC_API_KEY")
        for item in items:
            if item.get_closest_marker("live"):
                item.add_marker(skip_live)
