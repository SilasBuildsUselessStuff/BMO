"""AI tool adapter for the structured weather service."""

from typing import Any

from core.tools import (
    ToolDefinition,
    ToolExecutionError,
    ToolResult,
)
from services.weather import (
    OpenMeteoWeatherService,
    WeatherError,
)


class CurrentWeatherTool:
    """
    Expose current weather as a provider-independent BMO tool.

    The result contains both:
    - Concise source text for the language model
    - Structured display data for the future physical WEATHER screen
    """

    TOOL_NAME = "get_current_weather"

    def __init__(
        self,
        weather_service: OpenMeteoWeatherService,
        default_location: str,
        location_aliases: dict[str, str] | None = None,
    ) -> None:
        self.weather_service = weather_service
        self.default_location = default_location.strip()

        self.location_aliases = {
            key.strip().casefold(): value.strip()
            for key, value in (location_aliases or {}).items()
        }

    definition()

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Retrieve current weather and prepare AI and display results."""

        supplied_location = arguments.get("location")

        if supplied_location is None:
            location_query = self.default_location
        elif not isinstance(supplied_location, str):
            raise ToolExecutionError(
                "The weather location must be text."
            )
        elif not supplied_location.strip():
            location_query = self.default_location
        else:
            location_query = supplied_location.strip()

        canonical_query = self.location_aliases.get(
            location_query.casefold(),
            location_query,
        )

        try:
            weather = self.weather_service.get_current_weather(
                canonical_query
            )
        except WeatherError as error:
            raise ToolExecutionError(str(error)) from error

        display_data = {
            "location": weather.location.display_name,
            "latitude": weather.location.latitude,
            "longitude": weather.location.longitude,
            "timezone": weather.location.timezone,
            "observed_at": weather.observed_at,
            "condition": weather.condition,
            "weather_code": weather.weather_code,
            "temperature_c": weather.temperature_c,
            "apparent_temperature_c": (
                weather.apparent_temperature_c
            ),
            "relative_humidity_percent": (
                weather.relative_humidity_percent
            ),
            "precipitation_mm": weather.precipitation_mm,
            "wind_speed_kmh": weather.wind_speed_kmh,
        }

        return ToolResult(
            text=weather.to_tool_text(),
            display_type="WEATHER",
            display_data=display_data,
        )


.\.venv\Scripts\python.exe -m py_compile core\tools.py services\weather_tool.py


@'
from config import (
    WEATHER_DEFAULT_LOCATION,
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_LOCATION_ALIASES,
    WEATHER_TIMEOUT,
)
from core.tools import ToolRegistry
from services.weather import OpenMeteoWeatherService
from services.weather_tool import CurrentWeatherTool

service = OpenMeteoWeatherService(
    WEATHER_GEOCODING_URL,
    WEATHER_FORECAST_URL,
    WEATHER_TIMEOUT,
)

weather_tool = CurrentWeatherTool(
    weather_service=service,
    default_location=WEATHER_DEFAULT_LOCATION,
    location_aliases=WEATHER_LOCATION_ALIASES,
)

registry = ToolRegistry()
registry.register(weather_tool.definition())

result = registry.execute(
    "get_current_weather",
    {},
)

print("Registered tools:", registry.names)
print()
print("AI text:")
print(result.text)
print()
print("Display type:", result.display_type)
print("Display data:", result.display_data)
'@ | .\.venv\Scripts\python.exe -



@'
from config import (
    WEATHER_DEFAULT_LOCATION,
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_LOCATION_ALIASES,
    WEATHER_TIMEOUT,
)
from core.tools import ToolRegistry
from services.weather import OpenMeteoWeatherService
from services.weather_tool import CurrentWeatherTool

service = OpenMeteoWeatherService(
    WEATHER_GEOCODING_URL,
    WEATHER_FORECAST_URL,
    WEATHER_TIMEOUT,
)

tool = CurrentWeatherTool(
    service,
    WEATHER_DEFAULT_LOCATION,
    WEATHER_LOCATION_ALIASES,
)

registry = ToolRegistry()
registry.register(tool.definition())

result = registry.execute(
    "get_current_weather",
    {
        "location": "Palma de Mallorca",
    },
)

print(result.text)
print()
print("Resolved location:", result.display_data["location"])
print(
    "Coordinates:",
    result.display_data["latitude"],
    result.display_data["longitude"],
)
'@ | .\.venv\Scripts\python.exe -




@'
import json

from config import (
    WEATHER_DEFAULT_LOCATION,
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_LOCATION_ALIASES,
    WEATHER_TIMEOUT,
)
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

print(json.dumps(registry.ollama_schemas(), indent=2))
'@ | .\.venv\Scripts\python.exe -



