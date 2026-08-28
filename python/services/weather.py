"""Weather service using the Open-Meteo APIs."""

from dataclasses import dataclass
from typing import Any

import requests


class WeatherError(RuntimeError):
    """Raised when weather information cannot be retrieved."""


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
        """Convert current conditions into concise AI source text."""

        return (
            f"Location: {self.location.display_name}\n"
            f"Observation time: {self.observed_at} "
            f"({self.location.timezone})\n"
            f"Condition: {self.condition}\n"
            f"Temperature: {self.temperature_c:.1f} °C\n"
            f"Feels like: {self.apparent_temperature_c:.1f} °C\n"
            f"Relative humidity: {self.relative_humidity_percent}%\n"
            f"Precipitation: {self.precipitation_mm:.1f} mm\n"
            f"Wind speed: {self.wind_speed_kmh:.1f} km/h\n"
            f"Response guidance: Give a short natural summary. Normally "
            f"mention only the current temperature and condition. Mention "
            f"precipitation if it is currently relevant. Do not list every "
            f"field unless the user asks for details."
        )


@dataclass(frozen=True)
class DailyForecast:
    """Structured weather forecast for one calendar day."""

    location: LocationResult
    date: str
    condition: str
    weather_code: int
    temperature_min_c: float
    temperature_max_c: float
    precipitation_probability_percent: int
    precipitation_sum_mm: float
    wind_speed_max_kmh: float
    sunrise: str
    sunset: str

    def to_tool_text(self, day_label: str = "") -> str:
        """Convert the forecast into concise AI source text."""

        label = day_label.strip()

        if label:
            forecast_heading = f"Forecast for {label}"
        else:
            forecast_heading = "Daily forecast"

        return (
            f"{forecast_heading}\n"
            f"Location: {self.location.display_name}\n"
            f"Date: {self.date} ({self.location.timezone})\n"
            f"Condition: {self.condition}\n"
            f"Minimum temperature: {self.temperature_min_c:.1f} °C\n"
            f"Maximum temperature: {self.temperature_max_c:.1f} °C\n"
            f"Maximum precipitation probability: "
            f"{self.precipitation_probability_percent}%\n"
            f"Expected precipitation: "
            f"{self.precipitation_sum_mm:.1f} mm\n"
            f"Maximum wind speed: {self.wind_speed_max_kmh:.1f} km/h\n"
            f"Sunrise: {self.sunrise}\n"
            f"Sunset: {self.sunset}\n"
            f"Response guidance: Give a short natural summary. Normally "
            f"mention the temperature range, overall condition, and chance "
            f"of rain. Do not list wind, sunrise, sunset, or every field "
            f"unless the user asks for details or the conditions are "
            f"important or hazardous."
        )


class OpenMeteoWeatherService:
    """Retrieve locations and weather from Open-Meteo."""

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

    def get_current_weather(
        self,
        location_query: str,
    ) -> CurrentWeather:
        """Retrieve current conditions for a place name."""

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

    def get_daily_forecast(
        self,
        location_query: str,
        day_offset: int = 1,
    ) -> DailyForecast:
        """
        Retrieve a daily forecast.

        day_offset:
            0 = today
            1 = tomorrow
            2 = the day after tomorrow

        Open-Meteo normally provides several forecast days. This initial
        implementation accepts offsets from zero through six.
        """

        if not isinstance(day_offset, int):
            raise WeatherError(
                "The forecast day offset must be an integer."
            )

        if day_offset < 0 or day_offset > 6:
            raise WeatherError(
                "Forecasts are currently supported from today "
                "through six days ahead."
            )

        location = self.find_location(location_query)

        result = self._get_json(
            self.forecast_url,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "daily": ",".join(
                    [
                        "weather_code",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_probability_max",
                        "precipitation_sum",
                        "wind_speed_10m_max",
                        "sunrise",
                        "sunset",
                    ]
                ),
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
                "timezone": "auto",
                "forecast_days": 7,
            },
            operation="weather forecast request",
        )

        daily = result.get("daily")

        if not isinstance(daily, dict):
            raise WeatherError(
                "The weather service returned no daily forecast."
            )

        try:
            dates = daily["time"]
            weather_codes = daily["weather_code"]
            maximum_temperatures = daily["temperature_2m_max"]
            minimum_temperatures = daily["temperature_2m_min"]
            precipitation_probabilities = daily[
                "precipitation_probability_max"
            ]
            precipitation_sums = daily["precipitation_sum"]
            maximum_wind_speeds = daily["wind_speed_10m_max"]
            sunrises = daily["sunrise"]
            sunsets = daily["sunset"]

            forecast_values = (
                dates,
                weather_codes,
                maximum_temperatures,
                minimum_temperatures,
                precipitation_probabilities,
                precipitation_sums,
                maximum_wind_speeds,
                sunrises,
                sunsets,
            )

            if not all(
                isinstance(values, list)
                and len(values) > day_offset
                for values in forecast_values
            ):
                raise WeatherError(
                    "The requested forecast day is unavailable."
                )

            weather_code = int(weather_codes[day_offset])

            return DailyForecast(
                location=location,
                date=str(dates[day_offset]),
                condition=self.describe_weather_code(weather_code),
                weather_code=weather_code,
                temperature_min_c=float(
                    minimum_temperatures[day_offset]
                ),
                temperature_max_c=float(
                    maximum_temperatures[day_offset]
                ),
                precipitation_probability_percent=int(
                    precipitation_probabilities[day_offset]
                ),
                precipitation_sum_mm=float(
                    precipitation_sums[day_offset]
                ),
                wind_speed_max_kmh=float(
                    maximum_wind_speeds[day_offset]
                ),
                sunrise=str(sunrises[day_offset]),
                sunset=str(sunsets[day_offset]),
            )

        except WeatherError:
            raise

        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise WeatherError(
                "The weather service returned incomplete forecast data."
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
        """Convert a WMO weather code into plain English."""

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
