"""Statistical thresholds, extreme-event flags, and event detection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ExtremeThresholds:
    """City/date-range-specific statistical thresholds."""

    heat_temp_c: float | None
    cold_temp_c: float | None
    heavy_precip_mm: float | None
    high_wind_kmh: float | None
    heat_percentile: float = 95.0
    cold_percentile: float = 5.0
    precip_percentile: float = 95.0
    wind_percentile: float = 95.0


def _percentile(series: pd.Series, percentile: float) -> float | None:
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return None
    return float(np.nanpercentile(cleaned, percentile))


def calculate_extreme_thresholds(
    frame: pd.DataFrame,
    high_percentile: float = 95.0,
    low_percentile: float = 5.0,
) -> ExtremeThresholds:
    """Calculate selected-period thresholds for extreme-condition detection."""
    return ExtremeThresholds(
        heat_temp_c=_percentile(frame.get("temp_max_c", pd.Series(dtype=float)), high_percentile),
        cold_temp_c=_percentile(frame.get("temp_min_c", pd.Series(dtype=float)), low_percentile),
        heavy_precip_mm=_percentile(frame.get("precipitation_mm", pd.Series(dtype=float)), high_percentile),
        high_wind_kmh=_percentile(frame.get("wind_speed_max_kmh", pd.Series(dtype=float)), high_percentile),
        heat_percentile=high_percentile,
        cold_percentile=low_percentile,
        precip_percentile=high_percentile,
        wind_percentile=high_percentile,
    )


def add_z_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Add z-scores for temperature, precipitation, and wind where possible."""
    result = frame.copy()
    if "temp_mean_c" not in result or result["temp_mean_c"].isna().all():
        result["temp_reference_c"] = result[["temp_max_c", "temp_min_c"]].mean(axis=1)
    else:
        result["temp_reference_c"] = result["temp_mean_c"]

    z_score_specs = {
        "temp_reference_c": "temperature_z_score",
        "precipitation_mm": "precipitation_z_score",
        "wind_speed_max_kmh": "wind_z_score",
    }

    for source_column, output_column in z_score_specs.items():
        series = pd.to_numeric(result.get(source_column), errors="coerce")
        std = series.std(skipna=True)
        if pd.isna(std) or std == 0:
            result[output_column] = 0.0
        else:
            result[output_column] = (series - series.mean(skipna=True)) / std

    return result


def add_extreme_flags(frame: pd.DataFrame, thresholds: ExtremeThresholds) -> pd.DataFrame:
    """Add boolean columns for selected-period extreme weather days."""
    result = frame.copy()
    result["is_extreme_heat"] = False
    result["is_extreme_cold"] = False
    result["is_heavy_precipitation"] = False
    result["is_high_wind"] = False

    if thresholds.heat_temp_c is not None:
        result["is_extreme_heat"] = result["temp_max_c"] >= thresholds.heat_temp_c
    if thresholds.cold_temp_c is not None:
        result["is_extreme_cold"] = result["temp_min_c"] <= thresholds.cold_temp_c
    if thresholds.heavy_precip_mm is not None:
        result["is_heavy_precipitation"] = result["precipitation_mm"] >= thresholds.heavy_precip_mm
    if thresholds.high_wind_kmh is not None:
        result["is_high_wind"] = result["wind_speed_max_kmh"] >= thresholds.high_wind_kmh

    return result


def calculate_weather_extremity_score(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate an exploratory 0-100 weather extremity score for each day.

    This is a transparent portfolio metric, not an official warning system.
    It combines normalized anomalies and percentile-based extreme flags.
    """
    result = add_z_scores(frame)

    temp_component = result["temperature_z_score"].abs().clip(upper=3) / 3 * 35
    precip_component = result["precipitation_z_score"].clip(lower=0, upper=3) / 3 * 25
    wind_component = result["wind_z_score"].clip(lower=0, upper=3) / 3 * 15

    flag_component = (
        _flag_series(result, "is_extreme_heat") * 8
        + _flag_series(result, "is_extreme_cold") * 8
        + _flag_series(result, "is_heavy_precipitation") * 6
        + _flag_series(result, "is_high_wind") * 3
    )

    result["extremity_score"] = (temp_component + precip_component + wind_component + flag_component).clip(0, 100).round(1)
    result["extremity_class"] = np.select(
        [
            result["extremity_score"] >= 70,
            result["extremity_score"] >= 40,
        ],
        ["Extreme", "Unusual"],
        default="Normal",
    )
    return result


def prepare_analysis_frame(
    frame: pd.DataFrame,
    high_percentile: float = 95.0,
    low_percentile: float = 5.0,
) -> tuple[pd.DataFrame, ExtremeThresholds]:
    """Apply thresholds, flags, z-scores, and extremity score in one step."""
    thresholds = calculate_extreme_thresholds(frame, high_percentile, low_percentile)
    analyzed = add_extreme_flags(frame, thresholds)
    analyzed = calculate_weather_extremity_score(analyzed)
    return analyzed, thresholds


def detect_consecutive_events(
    frame: pd.DataFrame,
    value_column: str,
    event_type: str,
    threshold: float | None,
    comparison: str,
    minimum_days: int,
    threshold_percentile: float,
    analysis_start_date: str,
    analysis_end_date: str,
) -> pd.DataFrame:
    """Detect consecutive-day weather events that meet a threshold condition."""
    columns = [
        "event_type",
        "start_date",
        "end_date",
        "duration_days",
        "average_value",
        "peak_value",
        "threshold_value",
        "threshold_percentile",
        "minimum_consecutive_days",
        "analysis_start_date",
        "analysis_end_date",
    ]
    if threshold is None or value_column not in frame or frame.empty:
        return pd.DataFrame(columns=columns)

    ordered = frame.sort_values("weather_date").copy()
    values = pd.to_numeric(ordered[value_column], errors="coerce")
    if comparison == ">=":
        ordered["_meets_threshold"] = values >= threshold
    elif comparison == "<=":
        ordered["_meets_threshold"] = values <= threshold
    else:
        raise ValueError("comparison must be either '>=' or '<='")

    ordered["_event_group"] = (ordered["_meets_threshold"] != ordered["_meets_threshold"].shift()).cumsum()
    events: list[dict[str, object]] = []

    for _, group in ordered.groupby("_event_group"):
        event_days = group[group["_meets_threshold"]].copy()
        if len(event_days) < minimum_days:
            continue

        event_values = pd.to_numeric(event_days[value_column], errors="coerce")
        peak_value = event_values.min() if comparison == "<=" else event_values.max()
        events.append(
            {
                "event_type": event_type,
                "start_date": str(event_days["weather_date"].iloc[0]),
                "end_date": str(event_days["weather_date"].iloc[-1]),
                "duration_days": int(len(event_days)),
                "average_value": round(float(event_values.mean()), 2),
                "peak_value": round(float(peak_value), 2),
                "threshold_value": round(float(threshold), 2),
                "threshold_percentile": threshold_percentile,
                "minimum_consecutive_days": int(minimum_days),
                "analysis_start_date": analysis_start_date,
                "analysis_end_date": analysis_end_date,
            }
        )

    return pd.DataFrame(events, columns=columns)


def build_event_table(
    frame: pd.DataFrame,
    heat_threshold: float | None,
    cold_threshold: float | None,
    rain_threshold: float | None,
    heat_minimum_days: int,
    cold_minimum_days: int,
    rain_minimum_days: int,
    high_percentile: float,
    low_percentile: float,
    analysis_start_date: str,
    analysis_end_date: str,
) -> pd.DataFrame:
    """Build one combined event table for heatwaves, cold spells, and rain spells."""
    event_frames = [
        detect_consecutive_events(
            frame,
            "temp_max_c",
            "Heatwave",
            heat_threshold,
            ">=",
            heat_minimum_days,
            high_percentile,
            analysis_start_date,
            analysis_end_date,
        ),
        detect_consecutive_events(
            frame,
            "temp_min_c",
            "Cold spell",
            cold_threshold,
            "<=",
            cold_minimum_days,
            low_percentile,
            analysis_start_date,
            analysis_end_date,
        ),
        detect_consecutive_events(
            frame,
            "precipitation_mm",
            "Heavy rain spell",
            rain_threshold,
            ">=",
            rain_minimum_days,
            high_percentile,
            analysis_start_date,
            analysis_end_date,
        ),
    ]
    combined = pd.concat(event_frames, ignore_index=True)
    if combined.empty:
        return combined
    return combined.sort_values(["start_date", "event_type"]).reset_index(drop=True)


def summarize_overview(frame: pd.DataFrame) -> dict[str, float | int | None]:
    """Create headline metrics for the city overview tab."""
    if frame.empty:
        return {}

    return {
        "days_analyzed": int(len(frame)),
        "average_temperature_c": _safe_round(frame["temp_mean_c"].mean() if not frame["temp_mean_c"].isna().all() else frame[["temp_max_c", "temp_min_c"]].mean(axis=1).mean()),
        "highest_max_temperature_c": _safe_round(frame["temp_max_c"].max()),
        "lowest_min_temperature_c": _safe_round(frame["temp_min_c"].min()),
        "total_precipitation_mm": _safe_round(frame["precipitation_mm"].sum()),
        "average_wind_speed_kmh": _safe_round(frame["wind_speed_max_kmh"].mean()),
        "maximum_wind_speed_kmh": _safe_round(frame["wind_speed_max_kmh"].max()),
        "extreme_heat_days": int(frame.get("is_extreme_heat", pd.Series(dtype=bool)).sum()),
        "extreme_cold_days": int(frame.get("is_extreme_cold", pd.Series(dtype=bool)).sum()),
        "heavy_precipitation_days": int(frame.get("is_heavy_precipitation", pd.Series(dtype=bool)).sum()),
        "high_wind_days": int(frame.get("is_high_wind", pd.Series(dtype=bool)).sum()),
    }


def _safe_round(value: float | int | None, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _flag_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return a 0/1 flag series, defaulting to all zeros when absent."""
    if column not in frame:
        return pd.Series(0, index=frame.index)
    return frame[column].fillna(False).astype(int)
