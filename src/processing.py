"""Data cleaning and standardization helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


OPEN_METEO_COLUMN_MAP = {
    "time": "weather_date",
    "temperature_2m_max": "temp_max_c",
    "temperature_2m_min": "temp_min_c",
    "temperature_2m_mean": "temp_mean_c",
    "precipitation_sum": "precipitation_mm",
    "rain_sum": "rain_mm",
    "wind_speed_10m_max": "wind_speed_max_kmh",
}

WEATHER_COLUMNS = [
    "weather_date",
    "city_name",
    "country",
    "admin1",
    "latitude",
    "longitude",
    "temp_max_c",
    "temp_min_c",
    "temp_mean_c",
    "precipitation_mm",
    "rain_mm",
    "wind_speed_max_kmh",
]


def _location_value(location: dict[str, Any], key: str, default: Any = None) -> Any:
    return location.get(key, default)


def standardize_weather_data(api_payload: dict[str, Any], location: dict[str, Any]) -> pd.DataFrame:
    """Convert raw Open-Meteo daily data into a consistent tabular format.

    Missing optional weather variables are added as null columns so later
    analysis can degrade gracefully instead of failing on absent API fields.
    """
    daily_payload = api_payload.get("daily", {})
    if not daily_payload or "time" not in daily_payload:
        return pd.DataFrame(columns=WEATHER_COLUMNS)

    frame = pd.DataFrame(daily_payload).rename(columns=OPEN_METEO_COLUMN_MAP)

    for column in WEATHER_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan

    frame["weather_date"] = pd.to_datetime(frame["weather_date"], errors="coerce").dt.date
    frame["city_name"] = _location_value(location, "name", "Unknown")
    frame["country"] = _location_value(location, "country", "")
    frame["admin1"] = _location_value(location, "admin1", "")
    frame["latitude"] = float(_location_value(location, "latitude", api_payload.get("latitude", np.nan)))
    frame["longitude"] = float(_location_value(location, "longitude", api_payload.get("longitude", np.nan)))

    numeric_columns = [
        "temp_max_c",
        "temp_min_c",
        "temp_mean_c",
        "precipitation_mm",
        "rain_mm",
        "wind_speed_max_kmh",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["weather_date"]).sort_values("weather_date")
    return frame[WEATHER_COLUMNS].reset_index(drop=True)


def add_time_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add year, month, and month label columns for grouping and charts."""
    result = frame.copy()
    dates = pd.to_datetime(result["weather_date"])
    result["year"] = dates.dt.year
    result["month"] = dates.dt.month
    result["month_name"] = dates.dt.strftime("%b")
    result["year_month"] = dates.dt.to_period("M").astype(str)
    return result
