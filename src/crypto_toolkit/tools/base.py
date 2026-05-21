"""Abstract base class for orchestrator tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class ToolError(RuntimeError):
    """Raised by tools when execution fails with a model-visible message."""


class Tool(ABC):
    """Base class every concrete tool must extend."""

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        """Return the Anthropic-format tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @abstractmethod
    def execute(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Run the tool against ``tool_input`` and return a JSON-serialisable dict."""
