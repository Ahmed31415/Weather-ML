SELECT
    l.city_name,
    l.country,
    m.year,
    m.month,
    m.avg_temp_c,
    m.avg_temp_max_c,
    m.avg_temp_min_c,
    m.total_precipitation_mm,
    m.avg_wind_speed_kmh,
    m.days_observed
FROM monthly_weather_summary AS m
INNER JOIN locations AS l
    ON m.location_id = l.location_id
WHERE m.location_id = :location_id
ORDER BY m.year, m.month;
