-- Q3. Data quality of the OSM services inside Prabhag 11.

-- 3a. Share of services with no name tag
SELECT count(*)                                         AS services_in_area,
       count(*) FILTER (WHERE name IS NULL)             AS without_name,
       round(100.0 * count(*) FILTER (WHERE name IS NULL) / count(*), 1) AS percent_without_name
FROM services
WHERE inside_area;

-- 3b. Pairs of services within 25 m of each other (each pair counted once: a.id < b.id)
SELECT count(*) AS pairs_within_25m
FROM services a
JOIN services b ON a.service_id < b.service_id
               AND ST_DWithin(a.geom_utm, b.geom_utm, 25)
WHERE a.inside_area AND b.inside_area;

-- 3b. The pairs themselves, with the distance in metres
SELECT a.service_id AS id_a, a.name AS name_a, b.service_id AS id_b, b.name AS name_b,
       round(ST_Distance(a.geom_utm, b.geom_utm)::numeric, 1) AS distance_m
FROM services a
JOIN services b ON a.service_id < b.service_id
               AND ST_DWithin(a.geom_utm, b.geom_utm, 25)
WHERE a.inside_area AND b.inside_area
ORDER BY distance_m;

-- 3c. Breakdown by type and by OSM element type (node vs way), named vs unnamed
SELECT service_type, element_type,
       count(*) AS n,
       count(*) FILTER (WHERE name IS NOT NULL) AS named
FROM services
WHERE inside_area
GROUP BY service_type, element_type
ORDER BY service_type, element_type;

-- 3d. The full list, for the five-service verification against a second source
SELECT service_id, name, service_type, element_type, osmid,
       round(ST_Y(geom)::numeric, 5) AS lat, round(ST_X(geom)::numeric, 5) AS lon
FROM services
WHERE inside_area
ORDER BY service_id;
