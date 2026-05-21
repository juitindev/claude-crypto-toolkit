"""Tests for the get_price tool."""

from __future__ import annotations

import httpx
import pytest
import respx

from crypto_toolkit.tools.base import ToolError
from crypto_toolkit.tools.get_price import GetPriceTool


def test_returns_price_dict(mock_binance: respx.MockRouter) -> None:
    mock_binance.get("/api/v3/ticker/price", params={"symbol": "BTCUSDT"}).mock(
        return_value=httpx.Response(200, json={"symbol": "BTCUSDT", "price": "67123.45"})
    )
    out = GetPriceTool().execute({"symbol": "BTCUSDT"})
    assert out["symbol"] == "BTCUSDT"
    assert out["price"] == pytest.approx(67123.45)
    assert isinstance(out["timestamp"], int)


def test_symbol_uppercased(mock_binance: respx.MockRouter) -> None:
    mock_binance.get("/api/v3/ticker/price", params={"symbol": "ETHUSDT"}).mock(
        return_value=httpx.Response(200, json={"symbol": "ETHUSDT", "price": "3200.10"})
    )
    out = GetPriceTool().execute({"symbol": "  ethusdt  "})
    assert out["symbol"] == "ETHUSDT"


def test_missing_symbol_raises() -> None:
    with pytest.raises(ToolError):
        GetPriceTool().execute({})


def test_blank_symbol_raises() -> None:
    with pytest.raises(ToolError):
        GetPriceTool().execute({"symbol": "   "})


def test_4xx_surfaces_tool_error(mock_binance: respx.MockRouter) -> None:
    mock_binance.get("/api/v3/ticker/price", params={"symbol": "XXXUSDT"}).mock(
        return_value=httpx.Response(400, json={"msg": "Invalid symbol"})
    )
    with pytest.raises(ToolError):
        GetPriceTool().execute({"symbol": "XXXUSDT"})


def test_5xx_retries_then_succeeds(mock_binance: respx.MockRouter) -> None:
    route = mock_binance.get("/api/v3/ticker/price", params={"symbol": "BTCUSDT"})
    route.side_effect = [
        httpx.Response(503, json={"msg": "Service Unavailable"}),
        httpx.Response(200, json={"symbol": "BTCUSDT", "price": "67000.00"}),
    ]
    out = GetPriceTool().execute({"symbol": "BTCUSDT"})
    assert out["price"] == pytest.approx(67000.0)
    assert route.call_count == 2


def test_definition_shape() -> None:
    tool = GetPriceTool()
    definition = tool.definition()
    assert definition["name"] == "get_price"
    assert "symbol" in definition["input_schema"]["properties"]
    assert definition["input_schema"]["required"] == ["symbol"]
