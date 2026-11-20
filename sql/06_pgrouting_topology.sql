-- Bonus: routing topology for pgRouting, built from the OSMnx walking network loaded in Phase 1.
--   .venv\Scripts\python.exe analysis\run_sql.py sql\06_pgrouting_topology.sql     (output -> docs/outputs/06_pgrouting_topology.txt)
--
-- OSMnx already gives us a topology: every row of walk_edges carries its start node u and end node v.
-- The walk graph was downloaded as a DIRECTED graph in which every street appears twice (u->v and v->u):
-- 17,090 rows for 8,545 physical street segments. pgRouting wants ONE row per segment with a cost for each
-- direction, so we keep one row per unordered pair (u, v, key) and set cost = reverse_cost = length:
-- pedestrians ignore one-way rules, so both directions cost the same (Phase 3 did the same with
-- osmnx.convert.to_undirected).

-- 0. The extension. On a fresh volume sql/init/01_extensions.sql already created it; this line is for a database
--    volume that was created with the old postgis/postgis image before the switch to pgrouting/pgrouting.
CREATE EXTENSION IF NOT EXISTS pgrouting;
SELECT pgr_version();

-- 1. The routing edge table. Column names id / source / target / cost / reverse_cost are what every pgr_* function expects.
DROP TABLE IF EXISTS walk_edges_routing;
CREATE TABLE walk_edges_routing AS
SELECT DISTINCT ON (least(u, v), greatest(u, v), key)
       edge_id  AS id,
       u        AS source,
       v        AS target,
       length   AS cost,            -- metres (OSMnx great-circle length), the Dijkstra weight
       length   AS reverse_cost,    -- same cost backwards: walkers ignore one-way tags
       name, highway,
       geom_utm                     -- EPSG:32643, used for the bounding-box filter in the API and for drawing
FROM walk_edges
ORDER BY least(u, v), greatest(u, v), key, edge_id;

ALTER TABLE walk_edges_routing ADD PRIMARY KEY (id);
CREATE INDEX walk_edges_routing_source_idx    ON walk_edges_routing (source);
CREATE INDEX walk_edges_routing_target_idx    ON walk_edges_routing (target);
CREATE INDEX walk_edges_routing_geom_utm_gist ON walk_edges_routing USING GIST (geom_utm);

-- 2. Nodes: a unique index on node_id (pgRouting results are joined back on it) and a GiST index on the UTM point
--    so "nearest node to the click" is a KNN index scan (ORDER BY geom_utm <-> point LIMIT 1), not a scan of 6,645 rows.
CREATE UNIQUE INDEX IF NOT EXISTS walk_nodes_node_id_key   ON walk_nodes (node_id);
CREATE INDEX        IF NOT EXISTS walk_nodes_geom_utm_gist ON walk_nodes USING GIST (geom_utm);
ANALYZE walk_edges_routing;
ANALYZE walk_nodes;

-- 3. Checks: row counts, no edge pointing at a missing node, and how many islands the graph has.
SELECT (SELECT count(*) FROM walk_edges)         AS directed_rows_from_osmnx,
       (SELECT count(*) FROM walk_edges_routing) AS routing_segments,
       (SELECT count(*) FROM walk_nodes)         AS nodes,
       (SELECT round(sum(cost)::numeric / 1000, 1) FROM walk_edges_routing) AS network_km;

SELECT count(*) AS edges_with_missing_node
FROM walk_edges_routing e
LEFT JOIN walk_nodes a ON a.node_id = e.source
LEFT JOIN walk_nodes b ON b.node_id = e.target
WHERE a.node_id IS NULL OR b.node_id IS NULL;

-- connected components: a click on a small island can only reach that island
SELECT component, count(*) AS nodes_in_component
FROM pgr_connectedComponents('SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing')
GROUP BY component ORDER BY 2 DESC LIMIT 5;

SELECT count(DISTINCT component) AS number_of_components
FROM pgr_connectedComponents('SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing');

-- 4. services_nodes: every PG/hostel snapped to its nearest street node (KNN with the GiST index) plus the snap
--    distance, so /nearest can run ONE pgr_dijkstraCost from the click to all 54 service nodes at once.
DROP TABLE IF EXISTS services_nodes;
CREATE TABLE services_nodes AS
SELECT s.service_id, s.name, s.service_type, s.inside_area,
       n.node_id,
       round(ST_Distance(s.geom_utm, n.geom_utm)::numeric, 1) AS snap_m,
       s.geom, s.geom_utm
FROM services s
CROSS JOIN LATERAL (SELECT node_id, geom_utm FROM walk_nodes ORDER BY geom_utm <-> s.geom_utm LIMIT 1) AS n;

ALTER TABLE services_nodes ADD PRIMARY KEY (service_id);
CREATE INDEX services_nodes_node_idx ON services_nodes (node_id);
ANALYZE services_nodes;

-- same statistic as the Phase 3 notebook printed ("median 41, max 174"): the snapping agrees between the two engines
SELECT count(*) AS services, count(DISTINCT node_id) AS distinct_nodes,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY snap_m) AS median_snap_m, max(snap_m) AS max_snap_m
FROM services_nodes;

-- 5. Smoke tests from the ward centroid, the exact SQL the API runs.
-- 5a. nearest node: must be an Index Scan on walk_nodes_geom_utm_gist with "Order By: (geom_utm <-> ...)"
EXPLAIN (ANALYZE, COSTS OFF)
SELECT node_id, ST_Distance(geom_utm, (SELECT ST_Centroid(geom_utm) FROM area)) AS snap_m
FROM walk_nodes ORDER BY geom_utm <-> (SELECT ST_Centroid(geom_utm) FROM area) LIMIT 1;

-- 5b. 15 minutes = 1,200 m of walking from that node: how many nodes are reached, and the concave-hull area
WITH start AS (SELECT node_id FROM walk_nodes ORDER BY geom_utm <-> (SELECT ST_Centroid(geom_utm) FROM area) LIMIT 1),
reached AS (SELECT node, agg_cost FROM pgr_drivingDistance('SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing', (SELECT node_id FROM start), 1200, false))
SELECT count(*) AS reached_nodes, round(max(agg_cost)) AS farthest_m,
       round(ST_Area(ST_ConcaveHull(ST_Collect(n.geom_utm), 0.3, false))) AS concave_hull_m2
FROM reached r JOIN walk_nodes n ON n.node_id = r.node;

-- 5c. five nearest services by walking time from the ward centroid (what /nearest?k=5 returns)
WITH start AS (SELECT node_id, ST_Distance(geom_utm, (SELECT ST_Centroid(geom_utm) FROM area)) AS snap_m FROM walk_nodes ORDER BY geom_utm <-> (SELECT ST_Centroid(geom_utm) FROM area) LIMIT 1),
costs AS (SELECT end_vid, agg_cost FROM pgr_dijkstraCost('SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing', (SELECT node_id FROM start), (SELECT array_agg(DISTINCT node_id) FROM services_nodes), false))
SELECT sn.service_id, sn.name, round(c.agg_cost) AS path_m, round((c.agg_cost + s.snap_m + sn.snap_m)::numeric) AS walk_m,
       round(((c.agg_cost + s.snap_m + sn.snap_m) / 80)::numeric, 1) AS minutes
FROM costs c JOIN services_nodes sn ON sn.node_id = c.end_vid, start s
ORDER BY walk_m LIMIT 5;
