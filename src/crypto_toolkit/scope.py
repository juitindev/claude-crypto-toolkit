"""Scope-enforcement helpers used by tests.

The production refusal logic lives in the system prompt; this module gives the
test suite an independent classifier so we can assert refusal behavior without
manual transcript inspection.
"""

from __future__ import annotations

from crypto_toolkit.client_factory import get_client
from crypto_toolkit.prompts import SCOPE_CLASSIFIER_PROMPT
from crypto_toolkit.settings import get_settings


class OutOfScopeError(RuntimeError):
    """Raised when a user message is classified as out-of-scope."""


def classify_scope(message: str) -> str:
    """Return either ``IN_SCOPE`` or ``OUT_OF_SCOPE`` for the given message."""
    settings = get_settings()
    client = get_client()
    response = client.messages.create(
        model=settings.model,
        max_tokens=8,
        system=SCOPE_CLASSIFIER_PROMPT,
        messages=[{"role": "user", "content": message}],
    )
    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    verdict = "".join(text_parts).strip().upper()
    if verdict not in {"IN_SCOPE", "OUT_OF_SCOPE"}:
        verdict = "OUT_OF_SCOPE" if "OUT" in verdict else "IN_SCOPE"
    return verdict


def assert_in_scope(message: str) -> None:
    """Raise :class:`OutOfScopeError` if the classifier rejects ``message``."""
    if classify_scope(message) == "OUT_OF_SCOPE":
        raise OutOfScopeError(f"Out of scope: {message!r}")
