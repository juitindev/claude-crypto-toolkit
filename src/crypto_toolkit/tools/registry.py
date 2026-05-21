"""Tool registry — single source of truth the orchestrator dispatches against."""

from __future__ import annotations

from typing import Any

from crypto_toolkit.tools.base import Tool
from crypto_toolkit.tools.get_klines import GetKlinesTool
from crypto_toolkit.tools.get_market_overview import GetMarketOverviewTool
from crypto_toolkit.tools.get_price import GetPriceTool
from crypto_toolkit.tools.make_chart import MakeChartTool


def _build_registry() -> dict[str, Tool]:
    instances: list[Tool] = [
        GetPriceTool(),
        GetKlinesTool(),
        GetMarketOverviewTool(),
        MakeChartTool(),
    ]
    return {tool.name: tool for tool in instances}


TOOL_REGISTRY: dict[str, Tool] = _build_registry()


def get_tool(name: str) -> Tool:
    """Look up a tool by its name."""
    try:
        return TOOL_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown tool: {name!r}") from exc


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return Anthropic-format tool definitions for every registered tool."""
    return [tool.definition() for tool in TOOL_REGISTRY.values()]
