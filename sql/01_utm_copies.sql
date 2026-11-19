-- Phase 1, step 4: give every layer a metric copy of its geometry in UTM zone 43N (EPSG:32643).
-- The notebook loads the tables in EPSG:4326 (degrees); this adds a geom_utm column so that
-- ST_DWithin / ST_Area / ST_Length can be read directly in metres and square metres.
-- No spatial index is created here on purpose: Q2 measures the query with and without one.

ALTER TABLE area      ADD COLUMN IF NOT EXISTS geom_utm geometry(Geometry, 32643);
ALTER TABLE services  ADD COLUMN IF NOT EXISTS geom_utm geometry(Point,    32643);
ALTER TABLE buildings ADD COLUMN IF NOT EXISTS geom_utm geometry(Geometry, 32643);
ALTER TABLE walk_edges ADD COLUMN IF NOT EXISTS geom_utm geometry(LineString, 32643);
ALTER TABLE walk_nodes ADD COLUMN IF NOT EXISTS geom_utm geometry(Point,    32643);

UPDATE area       SET geom_utm = ST_Transform(geom, 32643);
UPDATE services   SET geom_utm = ST_Transform(geom, 32643);
UPDATE buildings  SET geom_utm = ST_Transform(geom, 32643);
UPDATE walk_edges SET geom_utm = ST_Transform(geom, 32643);
UPDATE walk_nodes SET geom_utm = ST_Transform(geom, 32643);

-- Length of every edge in metres (used for Dijkstra weights in SQL later, and as a sanity check
-- against the OSMnx "length" attribute, which is also metres on the ellipsoid).
ALTER TABLE walk_edges ADD COLUMN IF NOT EXISTS length_utm_m double precision;
UPDATE walk_edges SET length_utm_m = ST_Length(geom_utm);

-- Primary keys so GeoServer and pg_featureserv can identify features
ALTER TABLE services  ADD PRIMARY KEY (service_id);
ALTER TABLE buildings ADD PRIMARY KEY (building_id);
ALTER TABLE area      ADD PRIMARY KEY (area_id);

ANALYZE area; ANALYZE services; ANALYZE buildings; ANALYZE walk_edges; ANALYZE walk_nodes;
