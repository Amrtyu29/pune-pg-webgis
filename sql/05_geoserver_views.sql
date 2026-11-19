-- Views for GeoServer. The base tables carry TWO geometry columns (geom in EPSG:4326 and geom_utm in
-- EPSG:32643). GeoServer computed the layer bounding box from both, mixing degrees and metres
-- (BoundingBox minx=18.5 maxx=2053095 in the capabilities). Each view exposes only the 4326 geometry
-- and the attributes the map needs, so WMS/WFS see one clean geometry per layer.
CREATE OR REPLACE VIEW gs_area AS
SELECT area_id, name, ward_number, area_km2_utm, geom FROM area;

CREATE OR REPLACE VIEW gs_services AS
SELECT service_id, name, service_type, element_type, osmid, tourism, building, amenity, inside_area, geom FROM services;

CREATE OR REPLACE VIEW gs_buildings AS
SELECT building_id, osmid, building, name, levels, area_m2, inside_area, geom FROM buildings;
