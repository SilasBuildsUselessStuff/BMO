"""Provider-independent tool definitions for BMO."""

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


class ToolExecutionError(RuntimeError):
    """Raised when a registered tool cannot be executed."""


@dataclass(frozen=True)
class ToolResult:
    """
    Result produced by a BMO tool.

    text:
        Information passed to the AI model.

    display_type and display_data:
        Structured information that can later be sent to the ESP32 or shown
        in the development GUI without parsing the AI's response.
    """

    text: str
    display_type: str | None = None
    display_data: dict[str, Any] = field(default_factory=dict)


ToolHandler = Callable[[dict[str, Any]], ToolResult]


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of a function that an AI model may request."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_ollama_schema(self) -> dict[str, Any]:
        """Convert this definition to Ollama's function-tool format."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """
    Store and execute tools independently from Ollama.

    This allows another AI provider to use the same services later.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._lock = RLock()

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool by its unique name."""

        with self._lock:
            if tool.name in self._tools:
                raise ValueError(
                    f"A tool named '{tool.name}' is already registered."
                )

            self._tools[tool.name] = tool

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute one registered tool."""

        with self._lock:
            tool = self._tools.get(name)

        if tool is None:
            raise ToolExecutionError(
                f"Unknown tool requested: '{name}'."
            )

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise ToolExecutionError(
                f"Arguments for '{name}' must be an object."
            )

        try:
            result = tool.handler(arguments)
        except ToolExecutionError:
            raise
        except Exception as error:
            raise ToolExecutionError(
                f"Tool '{name}' failed: {error}"
            ) from error

        if not isinstance(result, ToolResult):
            raise ToolExecutionError(
                f"Tool '{name}' returned an invalid result."
            )

        return result

    def ollama_schemas(self) -> list[dict[str, Any]]:
        """Return all registered tools in Ollama-compatible format."""

        with self._lock:
            tools = list(self._tools.values())

        return [tool.to_ollama_schema() for tool in tools]

    @property
    def names(self) -> list[str]:
        """Return the registered tool names."""

        with self._lock:
            return list(self._tools.keys())
