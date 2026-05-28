"""Plotly visualizations used by the Streamlit dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.processing import add_time_columns


PLOT_TEMPLATE = "plotly_white"


def temperature_timeseries(frame: pd.DataFrame) -> go.Figure:
    """Line chart of daily max/min temperature over time."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["weather_date"],
            y=frame["temp_max_c"],
            mode="lines",
            name="Daily max",
            line={"color": "#d1495b"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["weather_date"],
            y=frame["temp_min_c"],
            mode="lines",
            name="Daily min",
            line={"color": "#247ba0"},
        )
    )
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=430,
        xaxis_title="Date",
        yaxis_title="Temperature (C)",
        legend_title=None,
    )
    return fig


def rolling_temperature(frame: pd.DataFrame, window: int) -> go.Figure:
    """Rolling average temperature line chart."""
    chart_data = frame.copy()
    if "temp_mean_c" not in chart_data or chart_data["temp_mean_c"].isna().all():
        chart_data["temp_reference_c"] = chart_data[["temp_max_c", "temp_min_c"]].mean(axis=1)
    else:
        chart_data["temp_reference_c"] = chart_data["temp_mean_c"]
    chart_data["rolling_temp_c"] = chart_data["temp_reference_c"].rolling(window=window, min_periods=1).mean()

    fig = px.line(
        chart_data,
        x="weather_date",
        y="rolling_temp_c",
        labels={"weather_date": "Date", "rolling_temp_c": f"{window}-day rolling average (C)"},
        template=PLOT_TEMPLATE,
        height=380,
    )
    fig.update_traces(line={"color": "#2a9d8f", "width": 2.5})
    return fig


def monthly_average_temperature(frame: pd.DataFrame) -> go.Figure:
    """Monthly average temperature chart."""
    chart_data = add_time_columns(frame)
    if "temp_mean_c" not in chart_data or chart_data["temp_mean_c"].isna().all():
        chart_data["temp_reference_c"] = chart_data[["temp_max_c", "temp_min_c"]].mean(axis=1)
    else:
        chart_data["temp_reference_c"] = chart_data["temp_mean_c"]

    monthly = (
        chart_data.groupby("year_month", as_index=False)
        .agg(avg_temp_c=("temp_reference_c", "mean"))
        .sort_values("year_month")
    )
    fig = px.line(
        monthly,
        x="year_month",
        y="avg_temp_c",
        markers=True,
        labels={"year_month": "Month", "avg_temp_c": "Average temperature (C)"},
        template=PLOT_TEMPLATE,
        height=400,
    )
    fig.update_traces(line={"color": "#264653"})
    return fig


def monthly_precipitation(frame: pd.DataFrame) -> go.Figure:
    """Monthly precipitation totals."""
    chart_data = add_time_columns(frame)
    monthly = (
        chart_data.groupby("year_month", as_index=False)
        .agg(total_precipitation_mm=("precipitation_mm", "sum"))
        .sort_values("year_month")
    )
    fig = px.bar(
        monthly,
        x="year_month",
        y="total_precipitation_mm",
        labels={"year_month": "Month", "total_precipitation_mm": "Precipitation (mm)"},
        template=PLOT_TEMPLATE,
        height=400,
    )
    fig.update_traces(marker_color="#457b9d")
    return fig


def annual_temperature_trend(frame: pd.DataFrame) -> go.Figure:
    """Annual average temperature trend for multi-year date ranges."""
    chart_data = add_time_columns(frame)
    if "temp_mean_c" not in chart_data or chart_data["temp_mean_c"].isna().all():
        chart_data["temp_reference_c"] = chart_data[["temp_max_c", "temp_min_c"]].mean(axis=1)
    else:
        chart_data["temp_reference_c"] = chart_data["temp_mean_c"]

    annual = chart_data.groupby("year", as_index=False).agg(avg_temp_c=("temp_reference_c", "mean"))
    fig = px.line(
        annual,
        x="year",
        y="avg_temp_c",
        markers=True,
        labels={"year": "Year", "avg_temp_c": "Average temperature (C)"},
        template=PLOT_TEMPLATE,
        height=380,
    )
    fig.update_traces(line={"color": "#e76f51", "width": 2.5})
    return fig


def distribution_with_threshold(
    frame: pd.DataFrame,
    column: str,
    threshold: float | None,
    title: str,
    x_label: str,
) -> go.Figure:
    """Histogram with an optional vertical threshold line."""
    fig = px.histogram(
        frame,
        x=column,
        nbins=40,
        title=title,
        labels={column: x_label},
        template=PLOT_TEMPLATE,
        height=360,
    )
    fig.update_traces(marker_color="#6c757d")
    if threshold is not None:
        fig.add_vline(
            x=threshold,
            line_width=3,
            line_dash="dash",
            line_color="#d1495b",
            annotation_text="threshold",
            annotation_position="top right",
        )
    return fig


def extreme_counts_by_month(frame: pd.DataFrame) -> go.Figure:
    """Stacked bar chart of extreme-day counts by month."""
    chart_data = add_time_columns(frame)
    flag_columns = {
        "is_extreme_heat": "Extreme heat",
        "is_extreme_cold": "Extreme cold",
        "is_heavy_precipitation": "Heavy precipitation",
        "is_high_wind": "High wind",
    }
    available_flags = [column for column in flag_columns if column in chart_data]
    monthly = chart_data.groupby("year_month", as_index=False)[available_flags].sum()
    long_data = monthly.melt(id_vars="year_month", value_vars=available_flags, var_name="condition", value_name="days")
    long_data["condition"] = long_data["condition"].map(flag_columns)

    fig = px.bar(
        long_data,
        x="year_month",
        y="days",
        color="condition",
        labels={"year_month": "Month", "days": "Days", "condition": "Condition"},
        template=PLOT_TEMPLATE,
        height=420,
        color_discrete_map={
            "Extreme heat": "#d1495b",
            "Extreme cold": "#247ba0",
            "Heavy precipitation": "#457b9d",
            "High wind": "#f4a261",
        },
    )
    return fig


def extremity_score_over_time(frame: pd.DataFrame) -> go.Figure:
    """Daily Weather Extremity Score over time."""
    fig = px.scatter(
        frame,
        x="weather_date",
        y="extremity_score",
        color="extremity_class",
        labels={"weather_date": "Date", "extremity_score": "Weather Extremity Score"},
        template=PLOT_TEMPLATE,
        height=420,
        color_discrete_map={"Normal": "#2a9d8f", "Unusual": "#f4a261", "Extreme": "#d1495b"},
        hover_data=["temp_max_c", "temp_min_c", "precipitation_mm", "wind_speed_max_kmh"],
    )
    fig.add_hline(y=40, line_dash="dash", line_color="#f4a261")
    fig.add_hline(y=70, line_dash="dash", line_color="#d1495b")
    return fig
