SELECT
    l.city_name,
    l.country,
    e.event_type,
    CAST(strftime('%Y', e.start_date) AS INTEGER) AS year,
    COUNT(*) AS event_count,
    SUM(e.duration_days) AS total_event_days,
    AVG(e.duration_days) AS average_duration_days
FROM extreme_events AS e
INNER JOIN locations AS l
    ON e.location_id = l.location_id
WHERE e.location_id = :location_id
  AND e.analysis_start_date = :analysis_start_date
  AND e.analysis_end_date = :analysis_end_date
GROUP BY l.city_name, l.country, e.event_type, year
ORDER BY year, e.event_type;
