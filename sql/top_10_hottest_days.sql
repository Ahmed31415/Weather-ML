SELECT
    l.city_name,
    l.country,
    dw.weather_date,
    dw.temp_max_c,
    dw.temp_min_c,
    dw.temp_mean_c,
    dw.precipitation_mm,
    dw.wind_speed_max_kmh
FROM daily_weather AS dw
INNER JOIN locations AS l
    ON dw.location_id = l.location_id
WHERE dw.location_id = :location_id
  AND dw.weather_date BETWEEN :start_date AND :end_date
ORDER BY dw.temp_max_c DESC
LIMIT 10;
