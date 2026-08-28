"""AI tool adapters for the structured weather service."""

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


def _prepare_location_aliases(
    location_aliases: dict[str, str] | None,
) -> dict[str, str]:
    """Create a cleaned, case-insensitive location-alias mapping."""

    return {
        key.strip().casefold(): value.strip()
        for key, value in (location_aliases or {}).items()
        if key.strip() and value.strip()
    }


def _resolve_location_query(
    arguments: dict[str, Any],
    default_location: str,
    location_aliases: dict[str, str],
) -> str:
    """
    Select the requested location or use the configured default.

    Missing, null, empty, and whitespace-only values all use the default.
    Known aliases are then converted into canonical geocoding queries.
    """

    supplied_location = arguments.get("location")

    if supplied_location is None:
        location_query = default_location

    elif not isinstance(supplied_location, str):
        raise ToolExecutionError(
            "The weather location must be text."
        )

    elif not supplied_location.strip():
        location_query = default_location

    else:
        location_query = supplied_location.strip()

    return location_aliases.get(
        location_query.casefold(),
        location_query,
    )


class CurrentWeatherTool:
    """
    Expose current weather as a provider-independent BMO tool.

    The result contains:

    1. Concise source text for the language model.
    2. Structured data for the development GUI and physical BMO screen.
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

        self.location_aliases = _prepare_location_aliases(
            location_aliases
        )

    def definition(self) -> ToolDefinition:
        """
        Return the current-weather tool definition.

        The model is explicitly instructed to use the default location rather
        than asking a follow-up question.
        """

        return ToolDefinition(
            name=self.TOOL_NAME,
            description=(
                "Get live current weather for a location. "
                "Always call this tool for every current-weather request, "
                "even if weather for that location or another location was "
                "discussed earlier. Never answer current weather from "
                "conversation history. "
                f"The configured default location is "
                f"'{self.default_location}'. "
                "Use this tool only for current weather conditions. "
                "If the user asks about current weather without naming a "
                "location, call this tool immediately with an empty argument "
                "object. Do not ask which location they mean. "
                "Only use another location when the user explicitly names "
                "one. For tomorrow or another future day, use the daily "
                "forecast tool instead."
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
                            "a location. The default location "
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
        """Retrieve current conditions and prepare the structured result."""

        canonical_query = _resolve_location_query(
            arguments=arguments,
            default_location=self.default_location,
            location_aliases=self.location_aliases,
        )

        try:
            weather = self.weather_service.get_current_weather(
                canonical_query
            )
        except WeatherError as error:
            raise ToolExecutionError(str(error)) from error

        display_data = {
            # The mode lets the future physical screen distinguish current
            # conditions from a daily forecast.
            "mode": "current",
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


class DailyForecastTool:
    """
    Expose a daily weather forecast as a provider-independent BMO tool.

    The tool supports today and up to six days into the future. If the model
    omits the day offset, tomorrow is used.
    """

    TOOL_NAME = "get_daily_weather_forecast"

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
                "The forecast tool requires a default location."
            )

        self.location_aliases = _prepare_location_aliases(
            location_aliases
        )

    def definition(self) -> ToolDefinition:
        """Return the daily-forecast tool definition."""

        return ToolDefinition(
            name=self.TOOL_NAME,
            description=(
                "Get a daily weather forecast for today or a future day. "
                "Always call this tool for every forecast request, even if "
                "weather was discussed earlier. Never answer a forecast "
                "from conversation history. "
                "Use day_offset 0 for today, 1 for tomorrow, 2 for the day "
                "after tomorrow, and up to 6 for six days ahead. "
                f"The configured default location is "
                f"'{self.default_location}'. "
                "If the user asks for a forecast without naming a location, "
                "use the default location immediately and do not ask which "
                "location they mean. Use this tool for future weather, rain "
                "probability, daily minimum or maximum temperature, sunrise, "
                "sunset, or expected daily conditions. Use the current "
                "weather tool only when the user asks about conditions "
                "right now."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "Optional city or place name. Omit it to use "
                            f"the default location "
                            f"'{self.default_location}'."
                        ),
                        "default": self.default_location,
                    },
                    "day_offset": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 6,
                        "description": (
                            "Number of calendar days from today. "
                            "Use 0 for today, 1 for tomorrow, 2 for the "
                            "day after tomorrow, through 6 for six days "
                            "ahead."
                        ),
                        "default": 1,
                    },
                },
                "required": [],
            },
            handler=self.execute,
        )

    def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Retrieve a daily forecast and prepare the structured result."""

        canonical_query = _resolve_location_query(
            arguments=arguments,
            default_location=self.default_location,
            location_aliases=self.location_aliases,
        )

        day_offset = self._parse_day_offset(
            arguments.get("day_offset", 1)
        )
        day_label = self._day_label(day_offset)

        try:
            forecast = self.weather_service.get_daily_forecast(
                location_query=canonical_query,
                day_offset=day_offset,
            )
        except WeatherError as error:
            raise ToolExecutionError(str(error)) from error

        display_data = {
            "mode": "forecast",
            "day_offset": day_offset,
            "day_label": day_label,
            "date": forecast.date,
            "location": forecast.location.display_name,
            "latitude": forecast.location.latitude,
            "longitude": forecast.location.longitude,
            "timezone": forecast.location.timezone,
            "condition": forecast.condition,
            "weather_code": forecast.weather_code,
            "temperature_min_c": forecast.temperature_min_c,
            "temperature_max_c": forecast.temperature_max_c,
            "precipitation_probability_percent": (
                forecast.precipitation_probability_percent
            ),
            "precipitation_sum_mm": (
                forecast.precipitation_sum_mm
            ),
            "wind_speed_max_kmh": (
                forecast.wind_speed_max_kmh
            ),
            "sunrise": forecast.sunrise,
            "sunset": forecast.sunset,
        }

        return ToolResult(
            text=forecast.to_tool_text(day_label),
            display_type="WEATHER",
            display_data=display_data,
        )

    @staticmethod
    def _parse_day_offset(value: Any) -> int:
        """
        Validate a forecast day offset.

        JSON tool calls should supply an integer, but numeric strings are
        accepted defensively in case a model returns "1" instead of 1.
        """

        if isinstance(value, bool):
            raise ToolExecutionError(
                "The forecast day offset must be a number from 0 to 6."
            )

        if isinstance(value, int):
            day_offset = value

        elif isinstance(value, str):
            cleaned_value = value.strip()

            if not cleaned_value.isdigit():
                raise ToolExecutionError(
                    "The forecast day offset must be a number from 0 to 6."
                )

            day_offset = int(cleaned_value)

        elif isinstance(value, float) and value.is_integer():
            day_offset = int(value)

        else:
            raise ToolExecutionError(
                "The forecast day offset must be a number from 0 to 6."
            )

        if day_offset < 0 or day_offset > 6:
            raise ToolExecutionError(
                "Forecasts are currently supported from today through "
                "six days ahead."
            )

        return day_offset

    @staticmethod
    def _day_label(day_offset: int) -> str:
        """Return a natural label for a forecast day."""

        labels = {
            0: "today",
            1: "tomorrow",
            2: "the day after tomorrow",
        }

        return labels.get(
            day_offset,
            f"in {day_offset} days",
        )
