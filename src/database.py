"""SQLite database helpers for local weather storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_DB_PATH = Path("data/weather.db")


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection and ensure parent folders exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create database tables if they do not already exist."""
    with get_connection(db_path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_name TEXT NOT NULL,
                country TEXT,
                admin1 TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timezone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(city_name, country, admin1, latitude, longitude)
            );

            CREATE TABLE IF NOT EXISTS daily_weather (
                location_id INTEGER NOT NULL,
                weather_date TEXT NOT NULL,
                temp_max_c REAL,
                temp_min_c REAL,
                temp_mean_c REAL,
                precipitation_mm REAL,
                rain_mm REAL,
                wind_speed_max_kmh REAL,
                latitude REAL,
                longitude REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (location_id, weather_date),
                FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS monthly_weather_summary (
                location_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                avg_temp_c REAL,
                avg_temp_max_c REAL,
                avg_temp_min_c REAL,
                total_precipitation_mm REAL,
                avg_wind_speed_kmh REAL,
                days_observed INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (location_id, year, month),
                FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS extreme_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                duration_days INTEGER NOT NULL,
                average_value REAL,
                peak_value REAL,
                threshold_value REAL,
                threshold_percentile REAL,
                minimum_consecutive_days INTEGER,
                analysis_start_date TEXT,
                analysis_end_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE CASCADE
            );
            """
        )


def upsert_location(location: dict, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Insert or update a location and return its database id."""
    values = {
        "city_name": location.get("name", "Unknown"),
        "country": location.get("country", ""),
        "admin1": location.get("admin1", ""),
        "latitude": float(location["latitude"]),
        "longitude": float(location["longitude"]),
        "timezone": location.get("timezone", ""),
    }
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO locations (city_name, country, admin1, latitude, longitude, timezone)
            VALUES (:city_name, :country, :admin1, :latitude, :longitude, :timezone)
            ON CONFLICT(city_name, country, admin1, latitude, longitude)
            DO UPDATE SET
                timezone = excluded.timezone,
                updated_at = CURRENT_TIMESTAMP;
            """,
            values,
        )
        row = connection.execute(
            """
            SELECT location_id
            FROM locations
            WHERE city_name = :city_name
              AND COALESCE(country, '') = COALESCE(:country, '')
              AND COALESCE(admin1, '') = COALESCE(:admin1, '')
              AND latitude = :latitude
              AND longitude = :longitude;
            """,
            values,
        ).fetchone()
    return int(row["location_id"])


def upsert_daily_weather(frame: pd.DataFrame, location_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Insert or update daily observations without creating duplicate rows."""
    if frame.empty:
        return 0

    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            {
                "location_id": location_id,
                "weather_date": str(record["weather_date"]),
                "temp_max_c": _none_if_nan(record.get("temp_max_c")),
                "temp_min_c": _none_if_nan(record.get("temp_min_c")),
                "temp_mean_c": _none_if_nan(record.get("temp_mean_c")),
                "precipitation_mm": _none_if_nan(record.get("precipitation_mm")),
                "rain_mm": _none_if_nan(record.get("rain_mm")),
                "wind_speed_max_kmh": _none_if_nan(record.get("wind_speed_max_kmh")),
                "latitude": _none_if_nan(record.get("latitude")),
                "longitude": _none_if_nan(record.get("longitude")),
            }
        )

    with get_connection(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO daily_weather (
                location_id, weather_date, temp_max_c, temp_min_c, temp_mean_c,
                precipitation_mm, rain_mm, wind_speed_max_kmh, latitude, longitude
            )
            VALUES (
                :location_id, :weather_date, :temp_max_c, :temp_min_c, :temp_mean_c,
                :precipitation_mm, :rain_mm, :wind_speed_max_kmh, :latitude, :longitude
            )
            ON CONFLICT(location_id, weather_date)
            DO UPDATE SET
                temp_max_c = excluded.temp_max_c,
                temp_min_c = excluded.temp_min_c,
                temp_mean_c = excluded.temp_mean_c,
                precipitation_mm = excluded.precipitation_mm,
                rain_mm = excluded.rain_mm,
                wind_speed_max_kmh = excluded.wind_speed_max_kmh,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                updated_at = CURRENT_TIMESTAMP;
            """,
            rows,
        )
    return len(rows)


def refresh_monthly_summary(location_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Rebuild monthly aggregates for one location."""
    with get_connection(db_path) as connection:
        connection.execute(
            "DELETE FROM monthly_weather_summary WHERE location_id = ?;",
            (location_id,),
        )
        connection.execute(
            """
            INSERT INTO monthly_weather_summary (
                location_id, year, month, avg_temp_c, avg_temp_max_c, avg_temp_min_c,
                total_precipitation_mm, avg_wind_speed_kmh, days_observed
            )
            SELECT
                location_id,
                CAST(strftime('%Y', weather_date) AS INTEGER) AS year,
                CAST(strftime('%m', weather_date) AS INTEGER) AS month,
                AVG(COALESCE(temp_mean_c, (temp_max_c + temp_min_c) / 2.0)) AS avg_temp_c,
                AVG(temp_max_c) AS avg_temp_max_c,
                AVG(temp_min_c) AS avg_temp_min_c,
                SUM(precipitation_mm) AS total_precipitation_mm,
                AVG(wind_speed_max_kmh) AS avg_wind_speed_kmh,
                COUNT(*) AS days_observed
            FROM daily_weather
            WHERE location_id = ?
            GROUP BY location_id, year, month;
            """,
            (location_id,),
        )


def get_weather_for_location(
    location_id: int,
    start_date: str,
    end_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """Load daily weather data for one location and date range."""
    with get_connection(db_path) as connection:
        frame = pd.read_sql_query(
            """
            SELECT
                dw.weather_date,
                l.city_name,
                l.country,
                l.admin1,
                dw.latitude,
                dw.longitude,
                dw.temp_max_c,
                dw.temp_min_c,
                dw.temp_mean_c,
                dw.precipitation_mm,
                dw.rain_mm,
                dw.wind_speed_max_kmh
            FROM daily_weather AS dw
            INNER JOIN locations AS l
                ON dw.location_id = l.location_id
            WHERE dw.location_id = ?
              AND dw.weather_date BETWEEN ? AND ?
            ORDER BY dw.weather_date;
            """,
            connection,
            params=(location_id, start_date, end_date),
        )
    if not frame.empty:
        frame["weather_date"] = pd.to_datetime(frame["weather_date"]).dt.date
    return frame


def get_saved_locations(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Return locations that have at least one stored weather observation."""
    with get_connection(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT
                l.location_id,
                l.city_name,
                l.country,
                l.admin1,
                l.latitude,
                l.longitude,
                MIN(dw.weather_date) AS first_weather_date,
                MAX(dw.weather_date) AS last_weather_date,
                COUNT(dw.weather_date) AS stored_days
            FROM locations AS l
            INNER JOIN daily_weather AS dw
                ON l.location_id = dw.location_id
            GROUP BY l.location_id
            ORDER BY l.city_name, l.country;
            """,
            connection,
        )


def replace_extreme_events(
    location_id: int,
    events: pd.DataFrame,
    analysis_start_date: str,
    analysis_end_date: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Replace stored event rows for a location and selected analysis window."""
    with get_connection(db_path) as connection:
        connection.execute(
            """
            DELETE FROM extreme_events
            WHERE location_id = ?
              AND analysis_start_date = ?
              AND analysis_end_date = ?;
            """,
            (location_id, analysis_start_date, analysis_end_date),
        )
        if events.empty:
            return 0

        rows = []
        for record in events.to_dict(orient="records"):
            rows.append(
                {
                    "location_id": location_id,
                    "event_type": record["event_type"],
                    "start_date": record["start_date"],
                    "end_date": record["end_date"],
                    "duration_days": int(record["duration_days"]),
                    "average_value": _none_if_nan(record.get("average_value")),
                    "peak_value": _none_if_nan(record.get("peak_value")),
                    "threshold_value": _none_if_nan(record.get("threshold_value")),
                    "threshold_percentile": _none_if_nan(record.get("threshold_percentile")),
                    "minimum_consecutive_days": int(record["minimum_consecutive_days"]),
                    "analysis_start_date": analysis_start_date,
                    "analysis_end_date": analysis_end_date,
                }
            )

        connection.executemany(
            """
            INSERT INTO extreme_events (
                location_id, event_type, start_date, end_date, duration_days,
                average_value, peak_value, threshold_value, threshold_percentile,
                minimum_consecutive_days, analysis_start_date, analysis_end_date
            )
            VALUES (
                :location_id, :event_type, :start_date, :end_date, :duration_days,
                :average_value, :peak_value, :threshold_value, :threshold_percentile,
                :minimum_consecutive_days, :analysis_start_date, :analysis_end_date
            );
            """,
            rows,
        )
    return len(events)


def run_saved_query(
    sql_path: str | Path,
    params: Iterable | dict | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """Execute a SQL file from the sql folder and return the result."""
    query = Path(sql_path).read_text(encoding="utf-8")
    with get_connection(db_path) as connection:
        return pd.read_sql_query(query, connection, params=params)


def _none_if_nan(value):
    if pd.isna(value):
        return None
    return value
