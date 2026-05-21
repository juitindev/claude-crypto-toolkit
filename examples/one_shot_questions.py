"""Send a small set of one-shot questions through the orchestrator."""

from __future__ import annotations

from crypto_toolkit.orchestrator import run_conversation
from crypto_toolkit.streaming import Done, Event, TextDelta, ToolUseStart

QUESTIONS = [
    "What is the current price of BTCUSDT?",
    "Show me a market overview.",
    "Give me 10 1h candles for ETHUSDT.",
]


def main() -> None:
    for q in QUESTIONS:
        print(f"\n=== {q} ===")

        def render(event: Event) -> None:
            if isinstance(event, TextDelta):
                print(event.text, end="", flush=True)
            elif isinstance(event, ToolUseStart):
                print(f"\n[→ {event.tool_name}({event.input})]", flush=True)
            elif isinstance(event, Done):
                print(f"\n[done {event.stop_reason} usage={event.usage}]", flush=True)

        run_conversation(user_message=q, on_event=render)


if __name__ == "__main__":
    main()
