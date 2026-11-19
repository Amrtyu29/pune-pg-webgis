-- Q2. Indexes and query plans.
-- Count buildings within 500 m of each service point (UTM geometry, so 500 really is metres).
-- Run 1: no spatial index on the UTM columns. Expect a Seq Scan on buildings inside a Nested Loop.
DROP INDEX IF EXISTS buildings_geom_utm_gist;
DROP INDEX IF EXISTS services_geom_utm_gist;

-- 2a. WITHOUT a GiST index
EXPLAIN (ANALYZE, BUFFERS)
SELECT s.service_id, s.name, count(b.building_id) AS buildings_within_500m
FROM services s
LEFT JOIN buildings b ON ST_DWithin(s.geom_utm, b.geom_utm, 500)
WHERE s.inside_area
GROUP BY s.service_id, s.name
ORDER BY s.service_id;

-- 2b. Create the GiST index (an R-tree of bounding boxes) and refresh planner statistics
CREATE INDEX buildings_geom_utm_gist ON buildings USING GIST (geom_utm);
CREATE INDEX services_geom_utm_gist  ON services  USING GIST (geom_utm);
ANALYZE buildings;
ANALYZE services;

-- 2b. WITH the GiST index: expect an Index Scan / Bitmap Index Scan on buildings_geom_utm_gist
EXPLAIN (ANALYZE, BUFFERS)
SELECT s.service_id, s.name, count(b.building_id) AS buildings_within_500m
FROM services s
LEFT JOIN buildings b ON ST_DWithin(s.geom_utm, b.geom_utm, 500)
WHERE s.inside_area
GROUP BY s.service_id, s.name
ORDER BY s.service_id;

-- 2c. Same question written as ST_Distance(a, b) < 500, index still present.
-- ST_Distance is a plain function returning a number, so the planner cannot use the index: Seq Scan again.
EXPLAIN (ANALYZE, BUFFERS)
SELECT s.service_id, s.name, count(b.building_id) AS buildings_within_500m
FROM services s
LEFT JOIN buildings b ON ST_Distance(s.geom_utm, b.geom_utm) < 500
WHERE s.inside_area
GROUP BY s.service_id, s.name
ORDER BY s.service_id;

-- The actual answer (the counts themselves), for the record
SELECT s.service_id, s.name, s.service_type, count(b.building_id) AS buildings_within_500m
FROM services s
LEFT JOIN buildings b ON ST_DWithin(s.geom_utm, b.geom_utm, 500)
WHERE s.inside_area
GROUP BY s.service_id, s.name, s.service_type
ORDER BY buildings_within_500m DESC;
