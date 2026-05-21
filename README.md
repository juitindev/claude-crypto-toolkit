# claude-crypto-toolkit

[![CI](https://github.com/juitindev/claude-crypto-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/juitindev/claude-crypto-toolkit/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A reference implementation of Anthropic Claude's advanced API patterns — **Tool Use**, **Prompt Caching**, **Streaming**, and **Scope Enforcement** — using public crypto market data (Binance, CoinGecko).

## What this demonstrates

- **Tool Use orchestration** — multi-round loop with 4 production tools
- **Streaming with interleaved tool calls** — text + tool execution events
- **Prompt caching** — system prompt and tool definitions cached, **51.8% measured input-cost reduction**
- **Strict scope enforcement** — model refuses trading advice and price prediction

## Quickstart

```bash
git clone https://github.com/juitindev/claude-crypto-toolkit.git
cd claude-crypto-toolkit

python -m venv .venv
. .venv/Scripts/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
# . .venv/bin/activate            # macOS / Linux
pip install -e ".[dev]"

cp .env.example .env
# edit .env and paste your real ANTHROPIC_API_KEY

crypto-toolkit chat
```

One-shot:

```bash
crypto-toolkit ask "What is the current price of BTCUSDT?"
```

Caching benchmark:

```bash
crypto-toolkit benchmark-caching
```

FastAPI server:

```bash
uvicorn crypto_toolkit.server:app --reload
# POST http://127.0.0.1:8000/chat
```

Docker:

```bash
docker compose up --build
```

## Architecture

```
┌──────────────┐         ┌──────────────────────────────────────┐
│   CLI (Typer)│         │           FastAPI server             │
│   or curl    │────────▶│  POST /chat  →  SSE event stream     │
└──────────────┘         └──────────────────┬───────────────────┘
                                            │
                                            ▼
                         ┌──────────────────────────────────────┐
                         │       Orchestrator (loop)            │
                         │                                      │
                         │  client.messages.stream()            │
                         │      │                               │
                         │      ▼                               │
                         │  parse tool_use blocks               │
                         │      │                               │
                         │      ▼                               │
                         │  Tool Registry  ──▶  execute(input)  │
                         │      │                               │
                         │      ▼                               │
                         │  tool_result  ──▶  next turn         │
                         │      │                               │
                         │      ▼                               │
                         │  stop_reason == end_turn  →  done    │
                         └──────────────────┬───────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────┐
              ▼                             ▼                         ▼
       ┌─────────────┐            ┌─────────────────┐         ┌──────────────┐
       │ Binance API │            │  CoinGecko API  │         │  matplotlib  │
       │ (price,     │            │  (top 10 by     │         │  (chart PNG  │
       │  klines)    │            │   market cap)   │         │   in base64) │
       └─────────────┘            └─────────────────┘         └──────────────┘
```

## The four patterns, explained

### Tool Use

The orchestrator drives the canonical `messages.stream → tool_use → execute → tool_result → loop` until `stop_reason == end_turn`. Each tool implements a thin `Tool` subclass with `name`, `description`, `input_schema`, and `execute()`, registered in a single dict the orchestrator dispatches against. Errors raised inside `execute()` flow back to Claude as `is_error=True` tool results so the model can recover instead of crashing the turn. A configurable round ceiling (default 8) guarantees the loop terminates.

| Name | Description | Source |
|------|-------------|--------|
| `get_price` | Current spot price | Binance |
| `get_klines` | OHLCV candles | Binance |
| `get_market_overview` | Top 10 by market cap | CoinGecko |
| `make_chart` | Candlestick PNG (base64) | matplotlib |

File reference: `src/crypto_toolkit/orchestrator.py`

### Streaming

Every model turn uses `client.messages.stream(...)` and forwards `text_stream` chunks to caller-provided event hooks in real time, while still parsing the final assembled message to discover any `tool_use` blocks. Events are typed dataclasses (`TextDelta`, `ToolUseStart`, `ToolUseResult`, `Done`, `Error`) so both the CLI and the FastAPI/SSE layer can render them identically. The FastAPI endpoint wraps the same emitter in a background thread and pushes each event to the wire as a Server-Sent Event.

File reference: `src/crypto_toolkit/streaming.py`

### Prompt Caching

Two ephemeral cache breakpoints are placed on every request: one on the system prompt block, one on the last tool definition (which extends the cache up to and including the full tool array). Cached blocks dominate input tokens after the priming turn.

Benchmark (run `crypto-toolkit benchmark-caching`) — two consecutive identical 3-turn conversations:

| Metric                        |    Run 1 |    Run 2 |
|-------------------------------|---------:|---------:|
| `input_tokens`                |    2,472 |    2,074 |
| `output_tokens`               |      716 |      677 |
| `cache_creation_input_tokens` |      696 |      748 |
| `cache_read_input_tokens`     |    4,362 |    4,694 |

Applying Anthropic's pricing (cache reads at 0.1x, cache writes at 1.25x):

| Metric                  |    Run 1 |    Run 2 |
|-------------------------|---------:|---------:|
| Uncached equivalent     |    7,530 |    7,516 |
| Effective cost (cached) |    3,778 |    3,478 |
| **Savings vs uncached** | **49.8%** | **53.7%** |

**Overall savings across both runs: 51.8%**

> Why this large? The system prompt + four tool definitions are ~5K input tokens that would be re-paid on every turn without caching. With caching, they're written once at 1.25x and read at 0.1x thereafter.

File reference: `src/crypto_toolkit/caching.py`

### Scope Enforcement

The system prompt is the production refusal layer: it tells the model to reject trading advice, price predictions, and any off-topic request with fixed responses. No code-level filter blocks user input; the contract is purely prompt-level, which mirrors how production assistants are usually constrained. To prove this works in practice, the test suite includes a second, independent classifier prompt that labels messages `IN_SCOPE` / `OUT_OF_SCOPE`; the scope tests assert the classifier's verdicts on five known-bad and known-good inputs against the real API.

File reference: `src/crypto_toolkit/prompts.py`, `src/crypto_toolkit/scope.py`

## Project layout

```
claude-crypto-toolkit/
├── src/crypto_toolkit/
│   ├── cli.py                  # Typer CLI (chat / ask / benchmark-caching)
│   ├── server.py               # FastAPI SSE endpoint
│   ├── orchestrator.py         # tool-use + streaming loop
│   ├── streaming.py            # typed event dataclasses
│   ├── caching.py              # cache_control helpers + usage parser
│   ├── prompts.py              # SYSTEM_PROMPT + scope classifier prompt
│   ├── scope.py                # test-only classifier (assert_in_scope)
│   ├── settings.py             # pydantic Settings from env
│   ├── client_factory.py       # Anthropic() singleton
│   ├── tools/                  # 4 tools + registry + base class
│   └── http/                   # Binance + CoinGecko REST clients
├── examples/                   # runnable demo scripts
└── tests/                      # respx-mocked unit tests + live scope tests
```

## Testing

```bash
pytest                          # offline tests only (HTTP + Anthropic both mocked)
pytest -m live                  # also run the 5 real-API scope tests
ruff check . && ruff format --check . && mypy src/
```

Live tests are skipped automatically unless `ANTHROPIC_API_KEY` is set to a real key.

## Non-goals

This is a patterns demo. It is deliberately **not**:

- A trading bot (no order placement, no private API keys)
- An investment-advice product (the model refuses it)
- An MCP server (separate future project)
- Multi-LLM (Anthropic only)

## License

MIT
