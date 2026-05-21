"""Typer CLI: ``crypto-toolkit chat | ask | benchmark-caching``."""

from __future__ import annotations

import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from crypto_toolkit.orchestrator import run_conversation
from crypto_toolkit.streaming import (
    Done,
    Error,
    Event,
    TextDelta,
    ToolUseResult,
    ToolUseStart,
)

app = typer.Typer(
    name="crypto-toolkit",
    help="Reference implementation of Claude's tool-use, streaming, caching, and scope patterns.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def _print_event(event: Event, *, buffer: list[str]) -> None:
    """Render a stream event to the terminal."""
    if isinstance(event, TextDelta):
        buffer.append(event.text)
        console.print(event.text, end="", soft_wrap=True, highlight=False)
    elif isinstance(event, ToolUseStart):
        args = ", ".join(f"{k}={v!r}" for k, v in event.input.items())
        console.print()
        console.print(f"[dim italic]→ calling {event.tool_name}({args})[/dim italic]")
    elif isinstance(event, ToolUseResult):
        marker = "x" if event.is_error else "ok"
        console.print(
            f"[dim italic]← {event.tool_name} {marker} ({event.duration_ms} ms)[/dim italic]"
        )
    elif isinstance(event, Done):
        console.print()
    elif isinstance(event, Error):
        console.print(f"[red]! {event.message}[/red]")


@app.command()
def chat() -> None:
    """Start an interactive multi-turn chat."""
    console.print("[bold]Claude Crypto Toolkit[/bold] — type 'exit' to quit.\n")
    history: list[dict[str, Any]] = []
    while True:
        try:
            message = console.input("[bold cyan]you[/bold cyan] > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not message:
            continue
        if message.lower() in {"exit", "quit", ":q"}:
            break
        console.print("[bold green]claude[/bold green] > ", end="")
        buffer: list[str] = []

        def render(event: Event, b: list[str] = buffer) -> None:
            _print_event(event, buffer=b)

        try:
            history = run_conversation(
                user_message=message,
                history=history,
                on_event=render,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Error:[/red] {exc}")


@app.command()
def ask(question: str = typer.Argument(..., help="Question to ask Claude.")) -> None:
    """Ask a single question and exit."""
    buffer: list[str] = []

    def render(event: Event, b: list[str] = buffer) -> None:
        _print_event(event, buffer=b)

    try:
        run_conversation(
            user_message=question,
            on_event=render,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("benchmark-caching")
def benchmark_caching() -> None:
    """Run a 3-turn conversation twice and report cache savings."""
    questions = [
        "What is the current price of BTCUSDT?",
        "Now show me the last 10 1h candles for the same pair.",
        "What's the top coin by market cap right now?",
    ]
    runs: list[dict[str, int]] = []
    for run_idx in (1, 2):
        console.print(f"\n[bold]Run {run_idx}[/bold]")
        history: list[dict[str, Any]] = []
        totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }

        def collect(event: Event, totals: dict[str, int] = totals) -> None:
            if isinstance(event, Done):
                for key, value in event.usage.items():
                    totals[key] = totals.get(key, 0) + value
            elif isinstance(event, ToolUseStart):
                args = ", ".join(f"{k}={v!r}" for k, v in event.input.items())
                console.print(f"  [dim]→ {event.tool_name}({args})[/dim]")

        for q in questions:
            console.print(f"[cyan]you >[/cyan] {q}")
            history = run_conversation(user_message=q, history=history, on_event=collect)
        runs.append(totals)

    table = Table(title="Prompt caching benchmark (3-turn conversation x2)")
    table.add_column("Metric", style="bold")
    table.add_column("Run 1", justify="right")
    table.add_column("Run 2", justify="right")
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        table.add_row(key, str(runs[0][key]), str(runs[1][key]))
    console.print()
    console.print(table)

    cost_table = Table(
        title="Cost analysis (input tokens only, normalised to base-rate equivalents)"
    )
    cost_table.add_column("Metric", style="bold")
    cost_table.add_column("Run 1", justify="right")
    cost_table.add_column("Run 2", justify="right")
    uncached = [_uncached_equivalent_cost(runs[0]), _uncached_equivalent_cost(runs[1])]
    effective = [_effective_input_cost(runs[0]), _effective_input_cost(runs[1])]
    cost_table.add_row("Uncached equivalent", f"{uncached[0]:,.1f}", f"{uncached[1]:,.1f}")
    cost_table.add_row("Effective cost (cached)", f"{effective[0]:,.1f}", f"{effective[1]:,.1f}")
    cost_table.add_row(
        "Savings vs uncached",
        f"{_saved_pct(runs[0]):.1f}%",
        f"{_saved_pct(runs[1]):.1f}%",
    )
    console.print()
    console.print(cost_table)

    total_uncached = uncached[0] + uncached[1]
    total_effective = effective[0] + effective[1]
    overall = (
        max(0.0, (total_uncached - total_effective) / total_uncached * 100)
        if total_uncached > 0
        else 0.0
    )
    console.print(f"\nOverall savings across both runs: [bold green]{overall:.1f}%[/bold green]")


def _effective_input_cost(run: dict[str, int]) -> float:
    return (
        run["input_tokens"]
        + run["cache_creation_input_tokens"] * CACHE_WRITE_MULTIPLIER
        + run["cache_read_input_tokens"] * CACHE_READ_MULTIPLIER
    )


def _uncached_equivalent_cost(run: dict[str, int]) -> int:
    return run["input_tokens"] + run["cache_creation_input_tokens"] + run["cache_read_input_tokens"]


def _saved_pct(run: dict[str, int]) -> float:
    uncached = _uncached_equivalent_cost(run)
    if uncached <= 0:
        return 0.0
    saved = (uncached - _effective_input_cost(run)) / uncached
    return max(0.0, saved * 100)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
