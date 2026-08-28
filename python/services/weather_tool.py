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

    The result contains two separate outputs:

    1. Concise source text for the language model.
    2. Structured display data for the development GUI and the future
       physical 480x320 WEATHER screen.
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

        if not self.default_location:
            raise ValueError(
                "The weather tool requires a default location."
            )

        # Store aliases case-insensitively. For example:
        #
        #   "palma de mallorca" -> "Palma, Spain"
        #   "74746"             -> "Höpfingen, Germany"
        #
        self.location_aliases = {
            key.strip().casefold(): value.strip()
            for key, value in (location_aliases or {}).items()
            if key.strip() and value.strip()
        }

    def definition(self) -> ToolDefinition:
        """
        Return the generic tool definition registered with BMO.

        The instructions explicitly tell the language model to use the
        configured default instead of asking the user for a location.
        """

        return ToolDefinition(
            name=self.TOOL_NAME,
            description=(
                "Get live current weather for a location. "
                f"The configured default location is "
                f"'{self.default_location}'. "
                "If the user asks about the weather without naming a "
                "location, call this tool immediately with an empty "
                "argument object. Do not ask which location they mean. "
                "Only use another location when the user explicitly names "
                "one."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "Optional city or place name, for example "
                            "'Palma de Mallorca' or 'Berlin, Germany'. "
                            "Omit this argument when the user does not name "
                            "a location. The configured default "
                            f"'{self.default_location}' will then be used."
                        ),
                        "default": self.default_location,
                    }
                },
                "required": [],
            },
            handler=self.execute,
        )

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        Retrieve current weather and prepare AI and display results.

        Missing, null, empty, or whitespace-only location values all use the
        configured default location.
        """

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

        # Resolve known ambiguous names before calling the geocoding API.
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

        # Keep this payload structured. The GUI and ESP32 must never need to
        # extract data from BMO's generated natural-language sentence.
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


