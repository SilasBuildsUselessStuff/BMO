"""Current-weather service using the Open-Meteo APIs."""

from dataclasses import dataclass
from typing import Any

import requests


class WeatherError(RuntimeError):
    """Raised when location or weather information cannot be retrieved."""


@dataclass(frozen=True)
class LocationResult:
    """Resolved geographic location."""

    name: str
    country: str
    administrative_area: str
    latitude: float
    longitude: float
    timezone: str

    @property
    def display_name(self) -> str:
        """Return a human-readable location name."""

        parts = [self.name]

        if (
            self.administrative_area
            and self.administrative_area.casefold()
            != self.name.casefold()
        ):
            parts.append(self.administrative_area)

        if self.country:
            parts.append(self.country)

        return ", ".join(parts)


@dataclass(frozen=True)
class CurrentWeather:
    """Structured current-weather result."""

    location: LocationResult
    observed_at: str
    condition: str
    weather_code: int
    temperature_c: float
    apparent_temperature_c: float
    relative_humidity_percent: int
    precipitation_mm: float
    wind_speed_kmh: float

    def to_tool_text(self) -> str:
        """
        Convert the result to concise text suitable for an AI tool result.

        The AI receives measured data rather than being asked to invent it.
        """

        return (
            f"Location: {self.location.display_name}\n"
            f"Observation time: {self.observed_at} "
            f"({self.location.timezone})\n"
            f"Condition: {self.condition}\n"
            f"Temperature: {self.temperature_c:.1f} °C\n"
            f"Feels like: {self.apparent_temperature_c:.1f} °C\n"
            f"Relative humidity: {self.relative_humidity_percent}%\n"
            f"Precipitation: {self.precipitation_mm:.1f} mm\n"
            f"Wind speed: {self.wind_speed_kmh:.1f} km/h"
        )


class OpenMeteoWeatherService:
    """Retrieve locations and current weather from Open-Meteo."""

    def __init__(
        self,
        geocoding_url: str,
        forecast_url: str,
        timeout: float = 10.0,
    ) -> None:
        self.geocoding_url = geocoding_url
        self.forecast_url = forecast_url
        self.timeout = timeout

    def find_location(self, query: str) -> LocationResult:
        """
        Resolve a place name into coordinates.

        Raises:
            WeatherError: If the query is empty, the request fails, or no
            matching location is found.
        """

        cleaned_query = query.strip()

        if not cleaned_query:
            raise WeatherError("A location name is required.")

        result = self._get_json(
            self.geocoding_url,
            params={
                "name": cleaned_query,
                "count": 1,
                "language": "en",
                "format": "json",
            },
            operation="location search",
        )

        locations = result.get("results")

        if not isinstance(locations, list) or not locations:
            raise WeatherError(
                f"No location was found for '{cleaned_query}'."
            )

        location = locations[0]

        if not isinstance(location, dict):
            raise WeatherError(
                "The location service returned invalid data."
            )

        try:
            return LocationResult(
                name=str(location["name"]),
                country=str(location.get("country", "")),
                administrative_area=str(
                    location.get("admin1", "")
                ),
                latitude=float(location["latitude"]),
                longitude=float(location["longitude"]),
                timezone=str(location.get("timezone", "auto")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WeatherError(
                "The location service returned incomplete data."
            ) from error

    def get_current_weather(self, location_query: str) -> CurrentWeather:
        """
        Retrieve current weather for a place name.

        The location is resolved first, so callers can use names such as
        "Palma de Mallorca" instead of geographic coordinates.
        """

        location = self.find_location(location_query)

        result = self._get_json(
            self.forecast_url,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": ",".join(
                    [
                        "temperature_2m",
                        "apparent_temperature",
                        "relative_humidity_2m",
                        "precipitation",
                        "weather_code",
                        "wind_speed_10m",
                    ]
                ),
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
                "timezone": "auto",
            },
            operation="current weather request",
        )

        current = result.get("current")

        if not isinstance(current, dict):
            raise WeatherError(
                "The weather service returned no current conditions."
            )

        try:
            weather_code = int(current["weather_code"])

            return CurrentWeather(
                location=location,
                observed_at=str(current["time"]),
                condition=self.describe_weather_code(weather_code),
                weather_code=weather_code,
                temperature_c=float(current["temperature_2m"]),
                apparent_temperature_c=float(
                    current["apparent_temperature"]
                ),
                relative_humidity_percent=int(
                    current["relative_humidity_2m"]
                ),
                precipitation_mm=float(current["precipitation"]),
                wind_speed_kmh=float(current["wind_speed_10m"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WeatherError(
                "The weather service returned incomplete conditions."
            ) from error

    def _get_json(
        self,
        url: str,
        params: dict[str, Any],
        operation: str,
    ) -> dict[str, Any]:
        """Perform an HTTP GET request and validate its JSON response."""

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

        except requests.Timeout as error:
            raise WeatherError(
                f"The {operation} timed out."
            ) from error

        except requests.ConnectionError as error:
            raise WeatherError(
                f"Could not connect during the {operation}. "
                "Check the internet connection."
            ) from error

        except requests.HTTPError as error:
            raise WeatherError(
                f"The {operation} returned HTTP "
                f"{response.status_code}."
            ) from error

        except requests.RequestException as error:
            raise WeatherError(
                f"The {operation} failed: {error}"
            ) from error

        try:
            result = response.json()
        except ValueError as error:
            raise WeatherError(
                f"The {operation} returned invalid JSON."
            ) from error

        if not isinstance(result, dict):
            raise WeatherError(
                f"The {operation} returned invalid data."
            )

        return result

    @staticmethod
    def describe_weather_code(code: int) -> str:
        """
        Convert a WMO weather interpretation code into plain English.

        Unknown codes remain explicit instead of being guessed.
        """

        descriptions = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "fog",
            48: "depositing rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            56: "light freezing drizzle",
            57: "dense freezing drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            66: "light freezing rain",
            67: "heavy freezing rain",
            71: "slight snowfall",
            73: "moderate snowfall",
            75: "heavy snowfall",
            77: "snow grains",
            80: "slight rain showers",
            81: "moderate rain showers",
            82: "violent rain showers",
            85: "slight snow showers",
            86: "heavy snow showers",
            95: "thunderstorm",
            96: "thunderstorm with slight hail",
            99: "thunderstorm with heavy hail",
        }

        return descriptions.get(
            code,
            f"unknown weather condition (code {code})",
        )


.\.venv\Scripts\python.exe -m py_compile services\weather.py


.\.venv\Scripts\python.exe -c "from services.weather import OpenMeteoWeatherService, WeatherError; print('Weather service loaded successfully')"

@'
from config import (
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_TIMEOUT,
)
from services.weather import OpenMeteoWeatherService

weather = OpenMeteoWeatherService(
    geocoding_url=WEATHER_GEOCODING_URL,
    forecast_url=WEATHER_FORECAST_URL,
    timeout=WEATHER_TIMEOUT,
)

location = weather.find_location("Palma de Mallorca")

print("Name:", location.name)
print("Country:", location.country)
print("Area:", location.administrative_area)
print("Coordinates:", location.latitude, location.longitude)
print("Timezone:", location.timezone)
print("Display name:", location.display_name)
'@ | .\.venv\Scripts\python.exe -


@'
from config import (
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_TIMEOUT,
)
from services.weather import OpenMeteoWeatherService

weather = OpenMeteoWeatherService(
    geocoding_url=WEATHER_GEOCODING_URL,
    forecast_url=WEATHER_FORECAST_URL,
    timeout=WEATHER_TIMEOUT,
)

result = weather.get_current_weather("Palma de Mallorca")

print(result.to_tool_text())
'@ | .\.venv\Scripts\python.exe -


@'
from config import (
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_TIMEOUT,
)
from services.weather import OpenMeteoWeatherService, WeatherError

weather = OpenMeteoWeatherService(
    WEATHER_GEOCODING_URL,
    WEATHER_FORECAST_URL,
    WEATHER_TIMEOUT,
)

try:
    weather.get_current_weather(
        "ThisPlaceShouldDefinitelyNotExist123456"
    )
except WeatherError as error:
    print("Handled correctly:", error)
'@ | .\.venv\Scripts\python.exe -


