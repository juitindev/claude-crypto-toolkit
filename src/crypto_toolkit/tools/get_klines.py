"""``get_klines`` tool — OHLCV candles from Binance."""

from __future__ import annotations

from typing import Any, ClassVar

from crypto_toolkit.http import binance
from crypto_toolkit.tools.base import Tool, ToolError

ALLOWED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")
MAX_LIMIT = 200


class GetKlinesTool(Tool):
    name: ClassVar[str] = "get_klines"
    description: ClassVar[str] = (
        "Get historical OHLCV candlestick data for a Binance trading pair. "
        "Returns a list of candles where each entry has open_time, open, high, "
        "low, close, and volume. Use this for trend or volume questions."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Binance trading pair, e.g. BTCUSDT.",
            },
            "interval": {
                "type": "string",
                "description": "Candle interval. One of: 1m, 5m, 15m, 1h, 4h, 1d.",
                "enum": list(ALLOWED_INTERVALS),
            },
            "limit": {
                "type": "integer",
                "description": "Number of candles to return (1-200). Default 50.",
                "minimum": 1,
                "maximum": MAX_LIMIT,
            },
        },
        "required": ["symbol", "interval"],
    }

    def execute(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        symbol = tool_input.get("symbol")
        interval = tool_input.get("interval")
        limit = tool_input.get("limit", 50)
        if not isinstance(symbol, str) or not symbol.strip():
            raise ToolError("symbol must be a non-empty string, e.g. BTCUSDT")
        if interval not in ALLOWED_INTERVALS:
            raise ToolError(f"interval must be one of {ALLOWED_INTERVALS!r}, got {interval!r}")
        if not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            raise ToolError(f"limit must be an integer in [1, {MAX_LIMIT}], got {limit!r}")

        try:
            rows = binance.get_klines(symbol.upper().strip(), interval, limit)
        except binance.BinanceError as exc:
            raise ToolError(str(exc)) from exc

        candles = [
            {
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in rows
        ]
        return {
            "symbol": symbol.upper().strip(),
            "interval": interval,
            "candles": candles,
        }
