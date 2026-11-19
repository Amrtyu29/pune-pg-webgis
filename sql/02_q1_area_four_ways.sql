-- Q1. One area, four areas.
-- The same Prabhag 11 polygon measured four ways. Only the geography and UTM numbers are real
-- square metres; the 4326 number is square DEGREES and the 3857 number is inflated by Web Mercator.
SELECT
  ST_Area(geom)                                  AS area_4326_square_degrees,
  ST_Area(geom::geography)                       AS area_geography_m2,
  ST_Area(geom_utm)                              AS area_utm43n_m2,
  ST_Area(ST_Transform(geom, 3857))              AS area_3857_m2,
  ST_Y(ST_Centroid(geom))                        AS centre_latitude_deg
FROM area;

-- The same in km2, plus the ratio the brief asks for: 3857 / UTM against 1 / cos^2(latitude).
SELECT
  round((ST_Area(geom::geography) / 1e6)::numeric, 4)             AS geography_km2,
  round((ST_Area(geom_utm) / 1e6)::numeric, 4)                    AS utm43n_km2,
  round((ST_Area(ST_Transform(geom, 3857)) / 1e6)::numeric, 4)    AS mercator3857_km2,
  round((ST_Area(ST_Transform(geom, 3857)) / ST_Area(geom_utm))::numeric, 5)             AS ratio_3857_over_utm,
  round((1 / power(cos(radians(ST_Y(ST_Centroid(geom)))), 2))::numeric, 5)              AS one_over_cos2_lat,
  round((100 * (ST_Area(ST_Transform(geom, 3857)) / ST_Area(geom_utm)
         / (1 / power(cos(radians(ST_Y(ST_Centroid(geom)))), 2)) - 1))::numeric, 3)      AS difference_percent
FROM area;
