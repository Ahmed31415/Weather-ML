"""Open-Meteo API helpers.

The project uses Open-Meteo because it does not require an API key for the
geocoding and historical weather endpoints used here.
"""

from __future__ import annotations

from typing import Any

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
HISTORICAL_WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "wind_speed_10m_max",
]


class OpenMeteoError(RuntimeError):
    """Raised when an Open-Meteo request fails or returns unusable data."""


def geocode_city(city_name: str, count: int = 10, language: str = "en") -> list[dict[str, Any]]:
    """Search Open-Meteo geocoding results for a city name.

    Args:
        city_name: User-entered city name.
        count: Maximum number of matches to return.
        language: Result language code supported by Open-Meteo.

    Returns:
        A list of location dictionaries returned by Open-Meteo.
    """
    cleaned_name = city_name.strip()
    if not cleaned_name:
        return []

    params = {
        "name": cleaned_name,
        "count": count,
        "language": language,
        "format": "json",
    }

    try:
        response = requests.get(GEOCODING_URL, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OpenMeteoError(f"Could not reach the Open-Meteo geocoding API: {exc}") from exc

    payload = response.json()
    return payload.get("results", []) or []


def fetch_historical_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timezone: str = "auto",
) -> dict[str, Any]:
    """Fetch daily historical weather observations from Open-Meteo.

    Args:
        latitude: Location latitude.
        longitude: Location longitude.
        start_date: ISO date string, e.g. "2020-01-01".
        end_date: ISO date string, e.g. "2020-12-31".
        timezone: Timezone handling for daily aggregation. "auto" uses the
            location timezone when Open-Meteo can infer it.

    Returns:
        Raw JSON payload from the historical weather endpoint.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone,
    }

    try:
        response = requests.get(HISTORICAL_WEATHER_URL, params=params, timeout=45)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OpenMeteoError(f"Could not fetch historical weather data: {exc}") from exc

    payload = response.json()
    if "daily" not in payload or "time" not in payload["daily"]:
        reason = payload.get("reason", "The API response did not include daily weather data.")
        raise OpenMeteoError(reason)

    return payload
