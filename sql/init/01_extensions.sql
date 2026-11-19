-- Runs once, automatically, the first time the "db" container starts with an empty volume
-- (the postgres image executes every *.sql in /docker-entrypoint-initdb.d, in name order).
-- It enables PostGIS in the project database so pg_tileserv, pg_featureserv and GeoServer
-- can call PostGIS functions such as ST_AsMVT and postgis_full_version().
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;   -- needed later if a raster is loaded into the database

-- Keep a record of the versions this project was built with (shown by: SELECT * FROM meta_versions;)
CREATE TABLE IF NOT EXISTS meta_versions AS
SELECT now() AS created_at, version() AS postgres, postgis_full_version() AS postgis;
