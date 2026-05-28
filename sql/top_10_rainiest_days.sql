SELECT
    l.city_name,
    l.country,
    dw.weather_date,
    dw.precipitation_mm,
    dw.rain_mm,
    dw.temp_max_c,
    dw.temp_min_c,
    dw.wind_speed_max_kmh
FROM daily_weather AS dw
INNER JOIN locations AS l
    ON dw.location_id = l.location_id
WHERE dw.location_id = :location_id
  AND dw.weather_date BETWEEN :start_date AND :end_date
ORDER BY dw.precipitation_mm DESC
LIMIT 10;
