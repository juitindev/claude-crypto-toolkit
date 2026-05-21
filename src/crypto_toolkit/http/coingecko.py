"""CoinGecko public REST wrapper. Same retry policy as the Binance client."""

from __future__ import annotations

import time
from typing import Any

import httpx

BASE_URL = "https://api.coingecko.com"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
MAX_RETRIES = 3
BACKOFF_BASE = 0.25


class CoinGeckoError(RuntimeError):
    """Raised when CoinGecko returns an error or the request fails."""


def _request(path: str, params: dict[str, Any] | None = None) -> Any:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
                response = client.get(path, params=params)
            if 500 <= response.status_code < 600 or response.status_code == 429:
                raise CoinGeckoError(f"CoinGecko transient {response.status_code}: {response.text}")
            if response.status_code >= 400:
                raise CoinGeckoError(
                    f"CoinGecko {response.status_code}: {response.text.strip()[:200]}"
                )
            return response.json()
        except (httpx.RequestError, CoinGeckoError) as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES:
                break
            if isinstance(exc, CoinGeckoError) and "transient" not in str(exc):
                break
            time.sleep(BACKOFF_BASE * (2**attempt))
    assert last_exc is not None
    raise CoinGeckoError(f"CoinGecko request failed after retries: {last_exc}") from last_exc


def get_top_markets(per_page: int = 10) -> list[dict[str, Any]]:
    """Return the top ``per_page`` coins by market cap in USD."""
    return _request(
        "/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        },
    )
