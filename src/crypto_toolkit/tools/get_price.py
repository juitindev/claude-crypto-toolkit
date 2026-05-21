"""``get_price`` tool — current spot price from Binance."""

from __future__ import annotations

import time
from typing import Any, ClassVar

from crypto_toolkit.http import binance
from crypto_toolkit.tools.base import Tool, ToolError


class GetPriceTool(Tool):
    name: ClassVar[str] = "get_price"
    description: ClassVar[str] = (
        "Get the current spot price of a cryptocurrency trading pair from Binance. "
        "Use this when the user asks for the latest or current price of a coin."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": (
                    "Binance trading pair, e.g. BTCUSDT, ETHUSDT, SOLUSDT. "
                    "Must be uppercase, no separator between base and quote."
                ),
            }
        },
        "required": ["symbol"],
    }

    def execute(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        symbol = tool_input.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ToolError("symbol must be a non-empty string, e.g. BTCUSDT")
        normalised = symbol.upper().strip()
        try:
            payload = binance.get_ticker_price(normalised)
        except binance.BinanceError as exc:
            raise ToolError(str(exc)) from exc
        try:
            price = float(payload["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolError(f"Unexpected Binance response: {payload!r}") from exc
        return {
            "symbol": normalised,
            "price": price,
            "timestamp": int(time.time()),
        }
