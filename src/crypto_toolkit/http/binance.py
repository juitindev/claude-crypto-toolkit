"""Binance public REST wrapper.

Retries 5xx responses up to three times with exponential backoff (0.25s, 0.5s,
1s). 4xx responses are surfaced immediately so the caller can present a useful
error to the model.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

BASE_URL = "https://api.binance.com"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_RETRIES = 3
BACKOFF_BASE = 0.25


class BinanceError(RuntimeError):
    """Raised when Binance returns an error or the request fails."""


def _request(path: str, params: dict[str, Any] | None = None) -> Any:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
                response = client.get(path, params=params)
            if 500 <= response.status_code < 600:
                raise BinanceError(f"Binance 5xx {response.status_code}: {response.text}")
            if response.status_code >= 400:
                raise BinanceError(f"Binance {response.status_code}: {response.text.strip()[:200]}")
            return response.json()
        except (httpx.RequestError, BinanceError) as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES:
                break
            if isinstance(exc, BinanceError) and "5xx" not in str(exc):
                break
            time.sleep(BACKOFF_BASE * (2**attempt))
    assert last_exc is not None
    raise BinanceError(f"Binance request failed after retries: {last_exc}") from last_exc


def get_ticker_price(symbol: str) -> dict[str, Any]:
    """Return current spot price for ``symbol`` (e.g. ``BTCUSDT``)."""
    return _request("/api/v3/ticker/price", params={"symbol": symbol.upper()})


def get_klines(symbol: str, interval: str, limit: int) -> list[list[Any]]:
    """Return raw kline rows for the given pair, interval, and bar count."""
    return _request(
        "/api/v3/klines",
        params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
    )
