"""Tests for the get_klines tool."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from crypto_toolkit.tools.base import ToolError
from crypto_toolkit.tools.get_klines import GetKlinesTool


def test_returns_parsed_candles(
    mock_binance: respx.MockRouter, sample_klines: list[list[Any]]
) -> None:
    mock_binance.get("/api/v3/klines").mock(return_value=httpx.Response(200, json=sample_klines))
    out = GetKlinesTool().execute({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})
    assert out["symbol"] == "BTCUSDT"
    assert out["interval"] == "1h"
    assert len(out["candles"]) == len(sample_klines)
    first = out["candles"][0]
    assert set(first.keys()) == {"open_time", "open", "high", "low", "close", "volume"}
    assert isinstance(first["open"], float)


def test_rejects_invalid_interval() -> None:
    with pytest.raises(ToolError):
        GetKlinesTool().execute({"symbol": "BTCUSDT", "interval": "2h"})


def test_rejects_limit_over_max() -> None:
    with pytest.raises(ToolError):
        GetKlinesTool().execute({"symbol": "BTCUSDT", "interval": "1h", "limit": 5000})


def test_rejects_zero_limit() -> None:
    with pytest.raises(ToolError):
        GetKlinesTool().execute({"symbol": "BTCUSDT", "interval": "1h", "limit": 0})


def test_default_limit_used(mock_binance: respx.MockRouter, sample_klines: list[list[Any]]) -> None:
    route = mock_binance.get("/api/v3/klines").mock(
        return_value=httpx.Response(200, json=sample_klines)
    )
    GetKlinesTool().execute({"symbol": "BTCUSDT", "interval": "1h"})
    call = route.calls[0].request
    assert "limit=50" in str(call.url)


def test_definition_lists_allowed_intervals() -> None:
    tool = GetKlinesTool()
    enum = tool.input_schema["properties"]["interval"]["enum"]
    assert enum == ["1m", "5m", "15m", "1h", "4h", "1d"]
