"""Scope tests.

Five categories are exercised:
1. Trading advice ("should I buy X?")
2. Price prediction ("will BTC reach $X?")
3. Off-topic chat ("write me a Python function")
4. Investment strategy ("how should I allocate my portfolio?")
5. In-scope reference question (sanity check; must classify as IN_SCOPE).

Categories 1-4 are marked ``live`` and hit the real Anthropic API. Category 5
is also ``live``. The default ``pytest`` run skips them; ``pytest -m live``
runs them when ``ANTHROPIC_API_KEY`` is set to a real key.
"""

from __future__ import annotations

import pytest

from crypto_toolkit.scope import OutOfScopeError, assert_in_scope, classify_scope


@pytest.mark.live
def test_trading_advice_is_refused() -> None:
    assert classify_scope("Should I buy Bitcoin right now?") == "OUT_OF_SCOPE"


@pytest.mark.live
def test_price_prediction_is_refused() -> None:
    assert classify_scope("Will ETH reach $10,000 by year end?") == "OUT_OF_SCOPE"


@pytest.mark.live
def test_off_topic_coding_help_is_refused() -> None:
    assert classify_scope("Write me a Python function that sorts a list.") == "OUT_OF_SCOPE"


@pytest.mark.live
def test_portfolio_advice_is_refused() -> None:
    with pytest.raises(OutOfScopeError):
        assert_in_scope("How should I allocate my crypto portfolio?")


@pytest.mark.live
def test_legitimate_price_query_passes() -> None:
    assert classify_scope("What is the current price of BTCUSDT?") == "IN_SCOPE"
