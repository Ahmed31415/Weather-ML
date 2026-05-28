"""Streamlit dashboard for weather trends and extreme-condition analysis."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.api import OpenMeteoError, fetch_historical_weather, geocode_city
from src.database import (
    DEFAULT_DB_PATH,
    get_saved_locations,
    get_weather_for_location,
    initialize_database,
    refresh_monthly_summary,
    replace_extreme_events,
    upsert_daily_weather,
    upsert_location,
)
from src.processing import standardize_weather_data
from src.statistics import build_event_table, prepare_analysis_frame, summarize_overview
from src.utils import format_location_label, validate_date_range
from src.visualization import (
    annual_temperature_trend,
    distribution_with_threshold,
    extreme_counts_by_month,
    extremity_score_over_time,
    monthly_average_temperature,
    monthly_precipitation,
    rolling_temperature,
    temperature_timeseries,
)


APP_TITLE = "Weather Trends & Extreme Conditions Dashboard"
DB_PATH = Path(DEFAULT_DB_PATH)


st.set_page_config(
    page_title="Weather Extreme Dashboard",
    page_icon="",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def cached_geocode_city(city_name: str) -> list[dict]:
    """Cached wrapper for city search."""
    return geocode_city(city_name)


@st.cache_data(show_spinner=False)
def cached_fetch_weather(latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
    """Cached wrapper for Open-Meteo historical weather."""
    return fetch_historical_weather(latitude, longitude, start_date, end_date)


@st.cache_data(show_spinner=False)
def cached_load_weather(location_id: int, start_date: str, end_date: str, cache_version: int) -> pd.DataFrame:
    """Cached database query. cache_version is bumped after writes."""
    _ = cache_version
    return get_weather_for_location(location_id, start_date, end_date, DB_PATH)


@st.cache_data(show_spinner=False)
def cached_prepare_analysis(frame: pd.DataFrame, high_percentile: float, low_percentile: float):
    """Cached analysis transformation."""
    return prepare_analysis_frame(frame, high_percentile, low_percentile)


def metric_value(value, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if isinstance(value, int):
        return f"{value}{suffix}"
    return f"{value:,.2f}{suffix}"


def render_overview(frame: pd.DataFrame, selected_location: dict, start_date: str, end_date: str) -> None:
    summary = summarize_overview(frame)
    st.subheader("City Overview")

    top_cols = st.columns(4)
    top_cols[0].metric("City", selected_location.get("name", "Selected city"))
    top_cols[1].metric("Country/region", selected_location.get("country", ""))
    top_cols[2].metric("Latitude", f"{float(selected_location.get('latitude', 0)):.3f}")
    top_cols[3].metric("Longitude", f"{float(selected_location.get('longitude', 0)):.3f}")

    st.caption(f"Selected date range: {start_date} to {end_date}")

    metric_columns = st.columns(4)
    metric_columns[0].metric("Days analyzed", metric_value(summary.get("days_analyzed")))
    metric_columns[1].metric("Average temp", metric_value(summary.get("average_temperature_c"), " C"))
    metric_columns[2].metric("Highest max temp", metric_value(summary.get("highest_max_temperature_c"), " C"))
    metric_columns[3].metric("Lowest min temp", metric_value(summary.get("lowest_min_temperature_c"), " C"))

    metric_columns = st.columns(4)
    metric_columns[0].metric("Total precipitation", metric_value(summary.get("total_precipitation_mm"), " mm"))
    metric_columns[1].metric("Avg/max wind", f"{metric_value(summary.get('average_wind_speed_kmh'))} / {metric_value(summary.get('maximum_wind_speed_kmh'), ' km/h')}")
    metric_columns[2].metric("Extreme heat days", metric_value(summary.get("extreme_heat_days")))
    metric_columns[3].metric("Extreme cold days", metric_value(summary.get("extreme_cold_days")))

    metric_columns = st.columns(2)
    metric_columns[0].metric("Heavy precipitation days", metric_value(summary.get("heavy_precipitation_days")))
    metric_columns[1].metric("High-wind days", metric_value(summary.get("high_wind_days")))


def render_trends(frame: pd.DataFrame) -> None:
    st.subheader("Weather Trends")
    rolling_window = st.slider("Rolling average window", min_value=3, max_value=60, value=30, step=1)

    st.plotly_chart(temperature_timeseries(frame), use_container_width=True)
    st.plotly_chart(rolling_temperature(frame, rolling_window), use_container_width=True)

    col1, col2 = st.columns(2)
    col1.plotly_chart(monthly_average_temperature(frame), use_container_width=True)
    col2.plotly_chart(monthly_precipitation(frame), use_container_width=True)

    year_count = pd.to_datetime(frame["weather_date"]).dt.year.nunique()
    if year_count >= 2:
        st.plotly_chart(annual_temperature_trend(frame), use_container_width=True)
    else:
        st.info("Annual trend appears after the selected date range includes at least two calendar years.")


def render_extremes(frame: pd.DataFrame, thresholds) -> None:
    st.subheader("Extreme Conditions")
    st.write(
        "Extremes are statistically unusual compared to the selected historical period, "
        "using city-specific percentile thresholds."
    )

    threshold_cols = st.columns(4)
    threshold_cols[0].metric("95th pct max temp", metric_value(thresholds.heat_temp_c, " C"))
    threshold_cols[1].metric("5th pct min temp", metric_value(thresholds.cold_temp_c, " C"))
    threshold_cols[2].metric("95th pct precipitation", metric_value(thresholds.heavy_precip_mm, " mm"))
    threshold_cols[3].metric("95th pct wind", metric_value(thresholds.high_wind_kmh, " km/h"))

    st.plotly_chart(extreme_counts_by_month(frame), use_container_width=True)

    top_cols = st.columns(2)
    top_cols[0].dataframe(
        frame.nlargest(10, "temp_max_c")[["weather_date", "temp_max_c", "temp_min_c", "precipitation_mm"]],
        use_container_width=True,
        hide_index=True,
    )
    top_cols[0].caption("Top 10 hottest days")

    top_cols[1].dataframe(
        frame.nsmallest(10, "temp_min_c")[["weather_date", "temp_min_c", "temp_max_c", "precipitation_mm"]],
        use_container_width=True,
        hide_index=True,
    )
    top_cols[1].caption("Top 10 coldest days")

    top_cols = st.columns(2)
    top_cols[0].dataframe(
        frame.nlargest(10, "precipitation_mm")[["weather_date", "precipitation_mm", "temp_max_c", "temp_min_c"]],
        use_container_width=True,
        hide_index=True,
    )
    top_cols[0].caption("Top 10 rainiest days")

    wind_frame = frame.dropna(subset=["wind_speed_max_kmh"])
    if wind_frame.empty:
        top_cols[1].info("Wind speed was not available for this selected dataset.")
    else:
        top_cols[1].dataframe(
            wind_frame.nlargest(10, "wind_speed_max_kmh")[["weather_date", "wind_speed_max_kmh", "temp_max_c", "precipitation_mm"]],
            use_container_width=True,
            hide_index=True,
        )
        top_cols[1].caption("Top 10 windiest days")

    dist_cols = st.columns(2)
    dist_cols[0].plotly_chart(
        distribution_with_threshold(frame, "temp_max_c", thresholds.heat_temp_c, "Max temperature distribution", "Max temperature (C)"),
        use_container_width=True,
    )
    dist_cols[1].plotly_chart(
        distribution_with_threshold(frame, "precipitation_mm", thresholds.heavy_precip_mm, "Precipitation distribution", "Precipitation (mm)"),
        use_container_width=True,
    )


def render_events(
    frame: pd.DataFrame,
    thresholds,
    location_id: int,
    start_date: str,
    end_date: str,
) -> None:
    st.subheader("Heatwave / Cold Spell Detection")
    col1, col2, col3 = st.columns(3)
    high_percentile = col1.slider("Heat/rain percentile", min_value=80, max_value=99, value=95, step=1)
    low_percentile = col2.slider("Cold percentile", min_value=1, max_value=20, value=5, step=1)
    min_days = col3.number_input("Minimum consecutive days", min_value=2, max_value=14, value=3, step=1)
    rain_min_days = st.number_input("Minimum consecutive heavy rain days", min_value=2, max_value=14, value=2, step=1)

    event_frame, event_thresholds = cached_prepare_analysis(frame, high_percentile, low_percentile)
    events = build_event_table(
        event_frame,
        event_thresholds.heat_temp_c,
        event_thresholds.cold_temp_c,
        event_thresholds.heavy_precip_mm,
        int(min_days),
        int(min_days),
        int(rain_min_days),
        high_percentile,
        low_percentile,
        start_date,
        end_date,
    )

    replace_extreme_events(location_id, events, start_date, end_date, DB_PATH)

    if events.empty:
        st.info("No consecutive-day events were detected using the current settings.")
    else:
        st.dataframe(events, use_container_width=True, hide_index=True)


def render_score(frame: pd.DataFrame) -> None:
    st.subheader("Weather Extremity Score")
    st.write(
        "The score is an exploratory 0-100 metric based on temperature, precipitation, "
        "wind anomalies, and extreme-event flags. It is not an official warning system."
    )
    st.plotly_chart(extremity_score_over_time(frame), use_container_width=True)
    st.dataframe(
        frame.sort_values("extremity_score", ascending=False)[
            [
                "weather_date",
                "extremity_score",
                "extremity_class",
                "temperature_z_score",
                "precipitation_z_score",
                "wind_z_score",
                "temp_max_c",
                "precipitation_mm",
                "wind_speed_max_kmh",
            ]
        ].head(25),
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    initialize_database(DB_PATH)
    st.title(APP_TITLE)
    st.write(
        "Search a city, fetch historical daily weather from Open-Meteo, and analyze trends "
        "plus statistically unusual conditions for the selected period."
    )

    if "db_version" not in st.session_state:
        st.session_state.db_version = 0
    if "active_location_id" not in st.session_state:
        st.session_state.active_location_id = None
    if "active_location" not in st.session_state:
        st.session_state.active_location = None

    with st.sidebar:
        st.header("Data selection")
        city_query = st.text_input("City name", value="Lahore")
        today = date.today()
        default_start = today - timedelta(days=365 * 3)
        start_date_input = st.date_input("Start date", value=default_start)
        end_date_input = st.date_input("End date", value=today - timedelta(days=2))

        date_error = validate_date_range(start_date_input, end_date_input)
        if date_error:
            st.error(date_error)

        results = []
        selected_location = None
        if city_query.strip():
            try:
                results = cached_geocode_city(city_query)
            except OpenMeteoError as exc:
                st.error(str(exc))

        if results:
            selected_location = st.selectbox(
                "Select matching city",
                options=results,
                format_func=format_location_label,
            )
        elif city_query.strip():
            st.warning("No city matches found yet.")

        fetch_clicked = st.button("Fetch and analyze", type="primary", disabled=bool(date_error) or selected_location is None)

        st.divider()
        saved_locations = get_saved_locations(DB_PATH)
        if saved_locations.empty:
            st.caption("No saved locations yet.")
        else:
            st.caption(f"{len(saved_locations)} saved location(s) in SQLite.")

    if fetch_clicked and selected_location:
        start_date = start_date_input.isoformat()
        end_date = end_date_input.isoformat()
        try:
            with st.spinner("Fetching historical weather from Open-Meteo..."):
                payload = cached_fetch_weather(
                    float(selected_location["latitude"]),
                    float(selected_location["longitude"]),
                    start_date,
                    end_date,
                )
                weather_frame = standardize_weather_data(payload, selected_location)
                location_id = upsert_location(selected_location, DB_PATH)
                row_count = upsert_daily_weather(weather_frame, location_id, DB_PATH)
                refresh_monthly_summary(location_id, DB_PATH)
        except OpenMeteoError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"Unexpected error while saving weather data: {exc}")
            return

        st.session_state.db_version += 1
        st.session_state.active_location_id = location_id
        st.session_state.active_location = selected_location
        st.success(f"Saved or updated {row_count:,} daily weather rows in SQLite.")

    if st.session_state.active_location_id is None or st.session_state.active_location is None:
        st.info("Choose a city and date range from the sidebar, then fetch weather data to start the analysis.")
        return

    start_date = start_date_input.isoformat()
    end_date = end_date_input.isoformat()
    stored_frame = cached_load_weather(
        st.session_state.active_location_id,
        start_date,
        end_date,
        st.session_state.db_version,
    )
    if stored_frame.empty:
        st.warning("No stored weather rows were found for the selected city and date range. Try fetching this range first.")
        return

    analyzed_frame, thresholds = cached_prepare_analysis(stored_frame, 95.0, 5.0)

    tabs = st.tabs(
        [
            "City Overview",
            "Weather Trends",
            "Extreme Conditions",
            "Spells",
            "Extremity Score",
        ]
    )

    with tabs[0]:
        render_overview(analyzed_frame, st.session_state.active_location, start_date, end_date)
    with tabs[1]:
        render_trends(analyzed_frame)
    with tabs[2]:
        render_extremes(analyzed_frame, thresholds)
    with tabs[3]:
        render_events(analyzed_frame, thresholds, st.session_state.active_location_id, start_date, end_date)
    with tabs[4]:
        render_score(analyzed_frame)


if __name__ == "__main__":
    main()
