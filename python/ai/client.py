"""Provider-independent AI interface and local Ollama implementation."""

import json
import re

from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import RLock
from typing import Any

import requests

from core.tools import (
    ToolExecutionError,
    ToolRegistry,
    ToolResult,
)


class AIError(RuntimeError):
    """Raised when an AI response cannot be generated."""


@dataclass(frozen=True)
class AIResponse:
    """
    Complete result of one AI interaction.

    text:
        The natural-language response shown in the GUI and sent to TTS.

    tool_results:
        Structured results produced during this interaction. These can later
        drive the PC development GUI and physical BMO display directly.
    """

    text: str
    tool_results: tuple[ToolResult, ...] = ()


class AIClient(ABC):
    """Common interface implemented by every AI backend."""

    @abstractmethod
    def generate_response(self, user_text: str) -> AIResponse:
        """Generate one response, including any structured tool results."""


class OllamaClient(AIClient):
    """
    Generate BMO responses through Ollama's local HTTP API.

    Recent conversation history is retained for the current application
    session. Live tool results are not stored in history because information
    such as weather becomes stale.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        system_prompt: str,
        timeout: float = 120.0,
        keep_alive: str = "10m",
        temperature: float = 0.7,
        max_tokens: int = 120,
        history_turns: int = 6,
        tool_registry: ToolRegistry | None = None,
        max_tool_rounds: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.history_turns = max(0, history_turns)
        self.tool_registry = tool_registry
        self.max_tool_rounds = max(1, max_tool_rounds)

        self._history: list[tuple[str, str]] = []
        self._generation_lock = RLock()

    def generate_response(self, user_text: str) -> AIResponse:
        """
        Generate BMO's response and execute requested tools.

        The returned AIResponse keeps natural-language text separate from
        structured display information.
        """

        cleaned_text = user_text.strip()

        if not cleaned_text:
            raise AIError("Cannot generate a response for empty user input.")

        with self._generation_lock:
            messages = self._build_messages(cleaned_text)
            tool_results: list[ToolResult] = []

            # If the model initially ignores the weather tools, it receives
            # one strict retry. This prevents it from inventing live weather.
            weather_tool_retry_used = False

            for _round in range(self.max_tool_rounds + 1):
                message = self._request_message(messages)
                tool_calls = message.get("tool_calls")

                if not tool_calls:
                    # Weather is time-sensitive. If Ollama tries to answer
                    # without a tool, discard that ungrounded answer and give
                    # it one explicit tool-call retry.
                    if (
                        not tool_results
                        and self._requires_weather_tool(cleaned_text)
                        and self._weather_tools_are_available()
                    ):
                        if weather_tool_retry_used:
                            # Ollama ignored the weather tool twice. Execute
                            # the correct weather service deterministically
                            # instead of abandoning the interaction.
                            tool_name, arguments = (
                                self._build_weather_fallback_call(
                                    cleaned_text
                                )
                            )

                            print(
                                "AI routing: Ollama still ignored the "
                                f"weather tool; executing {tool_name} "
                                f"directly with {arguments}."
                            )

                            try:
                                result = self.tool_registry.execute(
                                    tool_name,
                                    arguments,
                                )

                                tool_results.append(result)
                                tool_content = result.text

                            except ToolExecutionError as error:
                                tool_content = f"Tool error: {error}"

                            # Add a synthetic tool call and its result to the
                            # conversation so Ollama can now summarize the
                            # verified data naturally.
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "type": "function",
                                            "function": {
                                                "name": tool_name,
                                                "arguments": arguments,
                                            },
                                        }
                                    ],
                                }
                            )

                            messages.append(
                                {
                                    "role": "tool",
                                    "content": tool_content,
                                    "tool_name": tool_name,
                                }
                            )

                            continue

                        weather_tool_retry_used = True

                        print(
                            "AI routing: weather request did not use a tool; "
                            "forcing one retry."
                        )

                        messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "The current user request requires live "
                                    "weather data. Do not answer from memory "
                                    "or conversation history. You must call "
                                    "get_current_weather for present "
                                    "conditions or "
                                    "get_daily_weather_forecast for today "
                                    "or a future day. If no location was "
                                    "named, omit the location argument so "
                                    "the configured default is used. Return "
                                    "no natural-language answer until after "
                                    "the tool result is available."
                                ),
                            }
                        )

                        continue

                    content = message.get("content")

                    if not isinstance(content, str) or not content.strip():
                        raise AIError(
                            "Ollama returned an empty response."
                        )

                    final_text = content.strip()

                    # Only the user message and final answer are kept in
                    # conversation history. Live tool data is not retained.
                    self._history.append(
                        (cleaned_text, final_text)
                    )
                    self._trim_history()

                    return AIResponse(
                        text=final_text,
                        tool_results=tuple(tool_results),
                    )

                if _round >= self.max_tool_rounds:
                    raise AIError(
                        "Ollama exceeded the allowed number of tool rounds."
                    )

                if self.tool_registry is None:
                    raise AIError(
                        "Ollama requested a tool, but no tool registry "
                        "is configured."
                    )

                if not isinstance(tool_calls, list):
                    raise AIError(
                        "Ollama returned invalid tool-call data."
                    )

                # Preserve Ollama's assistant tool-call message before adding
                # the results returned by our Python tools.
                messages.append(message)

                for tool_call in tool_calls:
                    tool_name, arguments = self._parse_tool_call(tool_call)

                    try:
                        result = self.tool_registry.execute(
                            tool_name,
                            arguments,
                        )
                        tool_results.append(result)
                        tool_content = result.text

                    except ToolExecutionError as error:
                        # Give the model a controlled error result so it can
                        # explain the failure naturally to the user.
                        tool_content = f"Tool error: {error}"

                    messages.append(
                        {
                            "role": "tool",
                            "content": tool_content,
                            "tool_name": tool_name,
                        }
                    )

            raise AIError("Ollama did not produce a final response.")

    def clear_history(self) -> None:
        """Forget all temporary conversation context."""

        with self._generation_lock:
            self._history.clear()

    @property
    def history_size(self) -> int:
        """Return the number of stored user/BMO exchanges."""

        with self._generation_lock:
            return len(self._history)


    def _build_weather_fallback_call(
        self,
        user_text: str,
    ) -> tuple[str, dict[str, Any]]:
        """
        Build a safe weather call if Ollama refuses to select a tool.

        This fallback handles common current-weather and forecast phrases.
        The weather service still applies its configured default location
        whenever no explicit location is found.
        """

        normalized = user_text.casefold()
        arguments: dict[str, Any] = {}

        location = self._extract_weather_location(user_text)

        if location:
            arguments["location"] = location

        day_offset = self._extract_forecast_day_offset(normalized)

        forecast_terms = (
            "forecast",
            "tomorrow",
            "day after tomorrow",
            "in two days",
            "in three days",
            "in four days",
            "in five days",
            "in six days",
        )

        requires_forecast = (
            day_offset is not None
            or any(
                term in normalized
                for term in forecast_terms
            )
        )

        available_names = (
            set(self.tool_registry.names)
            if self.tool_registry is not None
            else set()
        )

        if (
            requires_forecast
            and "get_daily_weather_forecast" in available_names
        ):
            arguments["day_offset"] = (
                day_offset
                if day_offset is not None
                else 1
            )

            return (
                "get_daily_weather_forecast",
                arguments,
            )

        if "get_current_weather" in available_names:
            return (
                "get_current_weather",
                arguments,
            )

        if "get_daily_weather_forecast" in available_names:
            arguments["day_offset"] = (
                day_offset
                if day_offset is not None
                else 0
            )

            return (
                "get_daily_weather_forecast",
                arguments,
            )

        raise AIError(
            "A weather request was detected, but no weather tool "
            "is registered."
        )

    @staticmethod
    def _extract_forecast_day_offset(
        normalized_text: str,
    ) -> int | None:
        """Extract common forecast-day phrases from user text."""

        if "day after tomorrow" in normalized_text:
            return 2

        if "tomorrow" in normalized_text:
            return 1

        if "today" in normalized_text:
            return 0

        number_words = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
        }

        match = re.search(
            r"\bin\s+"
            r"(zero|one|two|three|four|five|six|[0-6])"
            r"\s+days?\b",
            normalized_text,
        )

        if match is None:
            return None

        value = match.group(1)

        if value.isdigit():
            return int(value)

        return number_words[value]

    @staticmethod
    def _extract_weather_location(
        user_text: str,
    ) -> str | None:
        """
        Extract common location phrases such as:

            weather in Berlin
            forecast for Palma de Mallorca
            weather in Berlin in two days

        This is a fallback only. Ollama normally supplies the arguments.
        """

        match = re.search(
            r"\b(?:in|for|at)\s+"
            r"(.+?)"
            r"(?="
            r"\s+in\s+"
            r"(?:zero|one|two|three|four|five|six|[0-6])"
            r"\s+days?\b"
            r"|\s+(?:today|tomorrow|right now|now)\b"
            r"|[?.!,]"
            r"|$"
            r")",
            user_text,
            flags=re.IGNORECASE,
        )

        if match is None:
            return None

        location = match.group(1).strip(" \t,.-")

        # Remove polite words that may occur at the end.
        location = re.sub(
            r"\s+please$",
            "",
            location,
            flags=re.IGNORECASE,
        ).strip()

        temporal_phrases = {
            "today",
            "tomorrow",
            "right now",
            "now",
            "one day",
            "two days",
            "three days",
            "four days",
            "five days",
            "six days",
        }

        if (
            not location
            or location.casefold() in temporal_phrases
        ):
            return None

        return location
    
    def _weather_tools_are_available(self) -> bool:
        """Return whether a weather tool is currently registered."""

        if self.tool_registry is None:
            return False

        available_names = set(self.tool_registry.names)

        return bool(
            {
                "get_current_weather",
                "get_daily_weather_forecast",
            }
            & available_names
        )

    @staticmethod
    def _requires_weather_tool(user_text: str) -> bool:
        """
        Detect requests that require live weather information.

        This is intentionally a routing safeguard, not a full natural-language
        parser. Ollama still chooses between current conditions and forecast
        and extracts the requested location.
        """

        normalized = user_text.casefold()

        weather_terms = (
            "weather",
            "forecast",
            "temperature",
            "rain",
            "raining",
            "snow",
            "snowing",
            "sunny",
            "cloudy",
            "windy",
            "wind speed",
            "sunrise",
            "sunset",
            "how warm",
            "how hot",
            "how cold",
        )

        return any(
            term in normalized
            for term in weather_terms
        )

    
    
    def _request_message(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send one chat request to Ollama and return its message."""

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        if self.tool_registry is not None:
            schemas = self.tool_registry.ollama_schemas()

            if schemas:
                payload["tools"] = schemas

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

        except requests.Timeout as error:
            raise AIError(
                f"Ollama did not respond within "
                f"{self.timeout:g} seconds."
            ) from error

        except requests.ConnectionError as error:
            raise AIError(
                "Could not connect to Ollama. "
                "Make sure Ollama is running."
            ) from error

        except requests.HTTPError as error:
            detail = self._extract_error_detail(response)
            raise AIError(
                f"Ollama returned an HTTP error: {detail}"
            ) from error

        except requests.RequestException as error:
            raise AIError(
                f"Ollama request failed: {error}"
            ) from error

        try:
            result = response.json()
        except ValueError as error:
            raise AIError(
                "Ollama returned a response that was not valid JSON."
            ) from error

        message = result.get("message")

        if not isinstance(message, dict):
            raise AIError(
                "Ollama response did not contain a message."
            )

        return message

    @staticmethod
    def _parse_tool_call(
        tool_call: Any,
    ) -> tuple[str, dict[str, Any]]:
        """Validate one Ollama function call."""

        if not isinstance(tool_call, dict):
            raise AIError("Ollama returned an invalid tool call.")

        function = tool_call.get("function")

        if not isinstance(function, dict):
            raise AIError(
                "Ollama tool call did not contain a function."
            )

        name = function.get("name")
        arguments = function.get("arguments", {})

        if not isinstance(name, str) or not name.strip():
            raise AIError(
                "Ollama tool call did not contain a valid name."
            )

        # Depending on the Ollama/model version, arguments may be returned
        # either as an object or as a JSON-encoded string.
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise AIError(
                    f"Ollama returned invalid arguments for '{name}'."
                ) from error

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise AIError(
                f"Ollama returned invalid arguments for '{name}'."
            )

        return name.strip(), arguments

    def _build_messages(
        self,
        current_user_text: str,
    ) -> list[dict[str, Any]]:
        """Build the system prompt, recent history, and current message."""

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self.system_prompt,
            }
        ]

        for previous_user_text, previous_bmo_response in self._history:
            messages.append(
                {
                    "role": "user",
                    "content": previous_user_text,
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": previous_bmo_response,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": current_user_text,
            }
        )

        return messages

    def _trim_history(self) -> None:
        """Keep only the configured number of recent exchanges."""

        if self.history_turns == 0:
            self._history.clear()
            return

        if len(self._history) > self.history_turns:
            self._history = self._history[-self.history_turns:]

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str:
        """Extract a useful message from a failed Ollama response."""

        try:
            result = response.json()
            detail = result.get("error")

            if isinstance(detail, str) and detail.strip():
                return detail.strip()

        except ValueError:
            pass

        if response.text.strip():
            return response.text.strip()

        return f"HTTP {response.status_code}"







.\.venv\Scripts\python.exe -m py_compile ai\client.py ai\identity.py



@'
from ai.client import OllamaClient
from ai.personality import BMO_SYSTEM_PROMPT
from config import (
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MAX_TOKENS,
    OLLAMA_MAX_TOOL_ROUNDS,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
    WEATHER_DEFAULT_LOCATION,
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_LOCATION_ALIASES,
    WEATHER_TIMEOUT,
)
from core.tools import ToolRegistry
from services.weather import OpenMeteoWeatherService
from services.weather_tool import CurrentWeatherTool

weather_service = OpenMeteoWeatherService(
    WEATHER_GEOCODING_URL,
    WEATHER_FORECAST_URL,
    WEATHER_TIMEOUT,
)

registry = ToolRegistry()
registry.register(
    CurrentWeatherTool(
        weather_service=weather_service,
        default_location=WEATHER_DEFAULT_LOCATION,
        location_aliases=WEATHER_LOCATION_ALIASES,
    ).definition()
)

client = OllamaClient(
    base_url=OLLAMA_BASE_URL,
    model=OLLAMA_MODEL,
    system_prompt=BMO_SYSTEM_PROMPT,
    timeout=OLLAMA_TIMEOUT,
    keep_alive=OLLAMA_KEEP_ALIVE,
    temperature=OLLAMA_TEMPERATURE,
    max_tokens=OLLAMA_MAX_TOKENS,
    tool_registry=registry,
    max_tool_rounds=OLLAMA_MAX_TOOL_ROUNDS,
)

response = client.generate_response(
    "What is the weather right now?"
)

print("BMO:", response.text)
print("Tool results:", len(response.tool_results))

for result in response.tool_results:
    print()
    print("Display type:", result.display_type)
    print("Display data:", result.display_data)
'@ | .\.venv\Scripts\python.exe -





@'
from ai.client import OllamaClient
from ai.personality import BMO_SYSTEM_PROMPT
from config import *
from core.tools import ToolRegistry
from services.weather import OpenMeteoWeatherService
from services.weather_tool import CurrentWeatherTool

service = OpenMeteoWeatherService(
    WEATHER_GEOCODING_URL,
    WEATHER_FORECAST_URL,
    WEATHER_TIMEOUT,
)

registry = ToolRegistry()
registry.register(
    CurrentWeatherTool(
        service,
        WEATHER_DEFAULT_LOCATION,
        WEATHER_LOCATION_ALIASES,
    ).definition()
)

client = OllamaClient(
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    BMO_SYSTEM_PROMPT,
    OLLAMA_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_TEMPERATURE,
    OLLAMA_MAX_TOKENS,
    tool_registry=registry,
    max_tool_rounds=OLLAMA_MAX_TOOL_ROUNDS,
)

response = client.generate_response(
    "What is the current weather in Palma de Mallorca?"
)

print("BMO:", response.text)

weather_data = response.tool_results[0].display_data
print("Resolved:", weather_data["location"])
print(
    "Coordinates:",
    weather_data["latitude"],
    weather_data["longitude"],
)
'@ | .\.venv\Scripts\python.exe -





@'
from ai.client import OllamaClient
from ai.personality import BMO_SYSTEM_PROMPT
from config import *
from core.tools import ToolRegistry
from services.weather import OpenMeteoWeatherService
from services.weather_tool import CurrentWeatherTool

service = OpenMeteoWeatherService(
    WEATHER_GEOCODING_URL,
    WEATHER_FORECAST_URL,
    WEATHER_TIMEOUT,
)

registry = ToolRegistry()
registry.register(
    CurrentWeatherTool(
        service,
        WEATHER_DEFAULT_LOCATION,
        WEATHER_LOCATION_ALIASES,
    ).definition()
)

client = OllamaClient(
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    BMO_SYSTEM_PROMPT,
    OLLAMA_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_TEMPERATURE,
    OLLAMA_MAX_TOKENS,
    tool_registry=registry,
    max_tool_rounds=OLLAMA_MAX_TOOL_ROUNDS,
)

response = client.generate_response(
    "Tell me a tiny joke."
)

print("BMO:", response.text)
print("Tool results:", len(response.tool_results))
'@ | .\.venv\Scripts\python.exe -
