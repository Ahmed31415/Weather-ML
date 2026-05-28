# Weather Trends & Extreme Conditions Dashboard

A Python and Streamlit portfolio project for exploring historical weather trends and statistically unusual weather conditions for any city supported by Open-Meteo.

## Project Overview

This dashboard lets a user search for a city, select the correct geocoding result, fetch historical daily weather observations, store the cleaned data locally in SQLite, and analyze weather trends, extreme days, multi-day weather events, and a simple Weather Extremity Score.

The project is designed to be readable, modular, and GitHub-ready rather than overly complex. It demonstrates API integration, data cleaning, local persistence, SQL querying, statistical feature engineering, and interactive analytics in Streamlit.

## Motivation

Weather extremes are local. A day that is unusually hot in one city may be normal in another. This project uses city-specific percentile thresholds from the selected historical period so the dashboard can describe conditions as statistically unusual compared to that city's own selected history.

## Data Source

Data comes from [Open-Meteo](https://open-meteo.com/), using:

- Open-Meteo Geocoding API for city lookup
- Open-Meteo Historical Weather API for daily weather observations

No API key is required.

## Features

- City search with multiple result selection
- Historical daily weather download
- SQLite local storage with duplicate-safe upserts
- Daily max/min/mean temperature analysis
- Precipitation and rain analysis where available
- Wind speed analysis where available
- Monthly and annual trend charts
- City/date-range-specific percentile thresholds
- Extreme heat, cold, precipitation, and wind flags
- Heatwave, cold spell, and heavy rain spell detection
- Exploratory Weather Extremity Score from 0 to 100
- SQL query files for reusable analysis

## Methodology

### Data Collection

The app first calls the Open-Meteo Geocoding API to convert a city name into latitude and longitude. It then calls the Historical Weather API for the selected date range using daily variables such as max temperature, min temperature, mean temperature, precipitation, rain, and maximum wind speed.

### Data Cleaning

Raw API data is standardized into consistent column names:

- `weather_date`
- `temp_max_c`
- `temp_min_c`
- `temp_mean_c`
- `precipitation_mm`
- `rain_mm`
- `wind_speed_max_kmh`
- location metadata

Optional variables are handled gracefully. If Open-Meteo does not return a requested variable, the app keeps the column with missing values and skips analyses that require that field.

### Statistical Thresholds

Extreme conditions are calculated using the selected city and selected historical date range:

- Extreme heat threshold: 95th percentile of daily max temperature
- Extreme cold threshold: 5th percentile of daily min temperature
- Heavy precipitation threshold: 95th percentile of daily precipitation
- High-wind threshold: 95th percentile of daily max wind speed, when available

The project intentionally avoids universal thresholds such as "30 C is extreme heat" because local climate context matters.

### Extreme Event Detection

The dashboard flags individual days as statistically unusual compared to the selected historical period:

- Extreme heat days: max temperature at or above the city-specific 95th percentile
- Extreme cold days: min temperature at or below the city-specific 5th percentile
- Heavy precipitation days: precipitation at or above the city-specific 95th percentile
- High-wind days: wind speed at or above the city-specific 95th percentile, when available

### Consecutive-Day Events

The app detects multi-day events using adjustable settings:

- Heatwave: default 3 or more consecutive days above the heat threshold
- Cold spell: default 3 or more consecutive days below the cold threshold
- Heavy rain spell: default 2 or more consecutive days above the precipitation threshold

Detected events are saved to the local SQLite `extreme_events` table for the selected analysis window.

### Weather Extremity Score

The Weather Extremity Score is an exploratory rule-based metric from 0 to 100. It combines:

- Temperature anomaly
- Precipitation anomaly
- Wind anomaly, if available
- Extreme-event flags

Days are classified as:

- Normal
- Unusual
- Extreme

This score is transparent and educational. It is not an official warning metric.

## Dashboard Screenshots

Add screenshots here after running the dashboard locally.

Suggested screenshots:

- City Overview page
- Weather Trends page
- Extreme Conditions page
- Heatwave / Cold Spell Detection page
- Weather Extremity Score page

## Tech Stack

- Python
- Streamlit
- pandas
- numpy
- requests
- Plotly
- SQLite

## Project Structure

```text
weather-extreme-dashboard/
  README.md
  requirements.txt
  .gitignore
  app.py
  data/
    raw/
    processed/
    weather.db
  notebooks/
    01_api_exploration.ipynb
    02_eda_extreme_weather.ipynb
  sql/
    monthly_weather_summary.sql
    top_10_hottest_days.sql
    top_10_rainiest_days.sql
    extreme_days_by_year.sql
  src/
    __init__.py
    api.py
    database.py
    processing.py
    statistics.py
    visualization.py
    utils.py
  reports/
    figures/
```

## How to Run Locally

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the Streamlit app:

```bash
streamlit run app.py
```

The SQLite database is created automatically at:

```text
data/weather.db
```

## Example Insights

The dashboard can help answer questions like:

- Which days were statistically hottest compared to the selected city history?
- Did monthly precipitation vary strongly across the selected period?
- How many heavy precipitation days occurred each year?
- Were there any multi-day heatwaves or cold spells?
- Which days had the highest exploratory Weather Extremity Score?

## Limitations

- Open-Meteo historical availability can vary by location and date.
- Some variables, such as rain or wind speed, may be unavailable for certain responses.
- Percentile thresholds are sensitive to the selected date range.
- The app describes historical patterns only. It does not predict future weather.
- The Weather Extremity Score is exploratory and should not be interpreted as an official hazard index.

## Future Improvements

- Add a full two-city comparison page.
- Add downloadable CSV exports.
- Add automated tests for processing and statistical functions.
- Add richer SQL reporting pages.
- Add map-based location selection.
- Add optional screenshot images to the README.

## Disclaimer

This project is for educational and exploratory analytics purposes only. It is not an official weather forecasting or emergency warning system.
