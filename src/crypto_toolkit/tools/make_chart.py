"""``make_chart`` tool — render a candlestick PNG using matplotlib."""

from __future__ import annotations

import base64
import io
from datetime import UTC, datetime
from typing import Any, ClassVar

import matplotlib

matplotlib.use("Agg")  # non-interactive backend, must be set before pyplot import
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from crypto_toolkit.http import binance
from crypto_toolkit.tools.base import Tool, ToolError
from crypto_toolkit.tools.get_klines import ALLOWED_INTERVALS, MAX_LIMIT

DEFAULT_LIMIT = 50


class MakeChartTool(Tool):
    name: ClassVar[str] = "make_chart"
    description: ClassVar[str] = (
        "Render a candlestick chart PNG for a Binance trading pair and return it "
        "as a base64-encoded image. Use this when the user explicitly asks for a "
        "chart, plot, or visualisation. Returns the image plus metadata about "
        "the candles drawn."
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
                "description": "Number of candles to draw (1-200). Default 50.",
                "minimum": 1,
                "maximum": MAX_LIMIT,
            },
        },
        "required": ["symbol", "interval"],
    }

    def execute(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        symbol = tool_input.get("symbol")
        interval = tool_input.get("interval")
        limit = tool_input.get("limit", DEFAULT_LIMIT)
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

        if not rows:
            raise ToolError(f"No candles returned for {symbol!r}/{interval!r}")

        image_bytes = _render_candlestick(symbol.upper().strip(), interval, rows)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {
            "image_base64": encoded,
            "symbol": symbol.upper().strip(),
            "interval": interval,
            "candles": len(rows),
        }


def _render_candlestick(symbol: str, interval: str, rows: list[list[Any]]) -> bytes:
    """Render rows into a PNG and return the bytes."""
    times = [datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC) for r in rows]
    opens = [float(r[1]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    closes = [float(r[4]) for r in rows]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=110)
    times_num = mdates.date2num(times)
    width = (times_num[1] - times_num[0]) * 0.7 if len(times_num) > 1 else 0.02

    for x, o, h, low_v, c in zip(times_num, opens, highs, lows, closes, strict=True):
        colour = "#26a69a" if c >= o else "#ef5350"
        ax.add_line(plt.Line2D((x, x), (low_v, h), color=colour, linewidth=1))
        body_low = min(o, c)
        body_height = max(abs(c - o), (h - low_v) * 0.001)
        ax.add_patch(
            Rectangle(
                (x - width / 2, body_low),
                width,
                body_height,
                facecolor=colour,
                edgecolor=colour,
            )
        )

    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    fig.autofmt_xdate()
    ax.set_title(f"{symbol}  {interval}  ({len(rows)} candles)")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.25)
    ax.margins(x=0.01)

    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    return buffer.getvalue()
