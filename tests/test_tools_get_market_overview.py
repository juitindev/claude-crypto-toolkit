"""Tests for the get_market_overview tool."""

from __future__ import annotations

import httpx
import pytest
import respx

from crypto_toolkit.tools.base import ToolError
from crypto_toolkit.tools.get_market_overview import GetMarketOverviewTool

_SAMPLE = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 67000.0,
        "market_cap": 1_300_000_000_000,
        "market_cap_rank": 1,
        "price_change_percentage_24h": 1.23,
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "current_price": 3200.0,
        "market_cap": 380_000_000_000,
        "market_cap_rank": 2,
        "price_change_percentage_24h": -0.45,
    },
]


def test_returns_normalised_rows(mock_coingecko: respx.MockRouter) -> None:
    mock_coingecko.get("/api/v3/coins/markets").mock(return_value=httpx.Response(200, json=_SAMPLE))
    out = GetMarketOverviewTool().execute({})
    assert len(out["coins"]) == 2
    btc = out["coins"][0]
    assert btc["symbol"] == "BTC"
    assert btc["rank"] == 1
    assert btc["price_usd"] == pytest.approx(67000.0)
    assert btc["change_24h_pct"] == pytest.approx(1.23)


def test_truncates_to_top_10(mock_coingecko: respx.MockRouter) -> None:
    payload = [dict(_SAMPLE[0], id=f"x{i}", market_cap_rank=i) for i in range(1, 13)]
    mock_coingecko.get("/api/v3/coins/markets").mock(return_value=httpx.Response(200, json=payload))
    out = GetMarketOverviewTool().execute({})
    assert len(out["coins"]) == 10


def test_429_surfaces_as_tool_error(mock_coingecko: respx.MockRouter) -> None:
    mock_coingecko.get("/api/v3/coins/markets").mock(
        return_value=httpx.Response(429, json={"error": "rate-limited"})
    )
    with pytest.raises(ToolError):
        GetMarketOverviewTool().execute({})


def test_handles_missing_fields(mock_coingecko: respx.MockRouter) -> None:
    mock_coingecko.get("/api/v3/coins/markets").mock(
        return_value=httpx.Response(200, json=[{"symbol": "doge", "name": "Dogecoin"}])
    )
    out = GetMarketOverviewTool().execute({})
    coin = out["coins"][0]
    assert coin["symbol"] == "DOGE"
    assert coin["price_usd"] == 0.0
    assert coin["market_cap_usd"] == 0.0
