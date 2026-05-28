"""Small utility helpers shared across the dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def format_location_label(location: dict[str, Any]) -> str:
    """Create a readable label for city search results."""
    parts = [
        location.get("name"),
        location.get("admin1"),
        location.get("country"),
    ]
    label = ", ".join(str(part) for part in parts if part)
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is not None and lon is not None:
        label = f"{label} ({float(lat):.2f}, {float(lon):.2f})"
    return label


def validate_date_range(start_date: date, end_date: date) -> str | None:
    """Return an error message when dates are invalid, otherwise None."""
    if start_date > end_date:
        return "Start date must be earlier than or equal to end date."
    return None


def load_sql(filename: str, sql_dir: str | Path = "sql") -> str:
    """Load a SQL query from the sql folder."""
    return Path(sql_dir, filename).read_text(encoding="utf-8")
