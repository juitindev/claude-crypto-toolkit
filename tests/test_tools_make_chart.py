"""Tests for the make_chart tool."""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
import respx

from crypto_toolkit.tools.base import ToolError
from crypto_toolkit.tools.make_chart import MakeChartTool


def test_returns_base64_png(mock_binance: respx.MockRouter, sample_klines: list[list[Any]]) -> None:
    mock_binance.get("/api/v3/klines").mock(return_value=httpx.Response(200, json=sample_klines))
    out = MakeChartTool().execute({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})
    assert out["symbol"] == "BTCUSDT"
    assert out["interval"] == "1h"
    assert out["candles"] == len(sample_klines)
    decoded = base64.b64decode(out["image_base64"])
    assert decoded.startswith(b"\x89PNG\r\n\x1a\n")


def test_empty_response_raises(mock_binance: respx.MockRouter) -> None:
    mock_binance.get("/api/v3/klines").mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(ToolError):
        MakeChartTool().execute({"symbol": "BTCUSDT", "interval": "1h"})


def test_rejects_bad_interval() -> None:
    with pytest.raises(ToolError):
        MakeChartTool().execute({"symbol": "BTCUSDT", "interval": "30m"})


def test_definition_includes_required_fields() -> None:
    tool = MakeChartTool()
    schema = tool.input_schema
    assert "symbol" in schema["properties"]
    assert "interval" in schema["properties"]
    assert set(schema["required"]) == {"symbol", "interval"}
