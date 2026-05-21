"""``get_market_overview`` tool — top-10 by market cap from CoinGecko."""

from __future__ import annotations

from typing import Any, ClassVar

from crypto_toolkit.http import coingecko
from crypto_toolkit.tools.base import Tool, ToolError


class GetMarketOverviewTool(Tool):
    name: ClassVar[str] = "get_market_overview"
    description: ClassVar[str] = (
        "Get the top 10 cryptocurrencies by market capitalisation in USD, with "
        "current price and 24h percent change. Source: CoinGecko. Use this when "
        "the user asks for an overview, top coins, leaderboard, or market "
        "snapshot."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = coingecko.get_top_markets(per_page=10)
        except coingecko.CoinGeckoError as exc:
            raise ToolError(str(exc)) from exc

        coins = [
            {
                "rank": int(row.get("market_cap_rank") or idx + 1),
                "symbol": str(row.get("symbol", "")).upper(),
                "name": str(row.get("name", "")),
                "price_usd": float(row.get("current_price") or 0.0),
                "market_cap_usd": float(row.get("market_cap") or 0.0),
                "change_24h_pct": float(row.get("price_change_percentage_24h") or 0.0),
            }
            for idx, row in enumerate(rows[:10])
        ]
        return {"coins": coins}
