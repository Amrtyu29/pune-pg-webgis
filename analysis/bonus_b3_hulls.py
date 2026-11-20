"""B3: hull choice. One 15-minute isochrone (pgr_drivingDistance, 1,200 m) drawn four ways from the SAME reached
nodes and edges:
  1. convex hull of the reached nodes                         ST_ConvexHull
  2. concave hull, target ratio 0.7                           ST_ConcaveHull algorithm (GEOS ConcaveHull), fairly loose
  3. concave hull, target ratio 0.3                           same algorithm, tighter (what the API returns)
  4. buffered reached edges (30 m, dissolved)                 the Phase 3 method
For each polygon: area in m2, and the share of its area that lies more than 50 m from any reached street
("painted-over ground" a user would read as walkable although no reached street is there).

The concave hulls are computed with shapely's GEOS (3.14) because the database image has GEOS 3.9, where
PostGIS falls back to a legacy ST_ConcaveHull; the legacy result is computed too, for the record, so the
difference between the two implementations is visible.

Start point: Q6's worst case, point 16 (18.55306 N, 73.83177 E), just outside the SPPU campus wall.

    .venv\\Scripts\\python.exe analysis\\bonus_b3_hulls.py [lon lat]

Writes docs/outputs/bonus_b3_hulls.json and docs/screenshots/bonus_b3_hulls.png."""
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import psycopg
import shapely
from shapely.ops import unary_union

from dbconf import read_env

ROOT = Path(__file__).resolve().parents[1]
UTM = 32643
LON, LAT = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (73.83176615313359, 18.55305548264837)
DIST_M = 1200
EDGES = "SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing"
env = read_env()
con = psycopg.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5434")), user=env["POSTGRES_USER"],
                      password=env["POSTGRES_PASSWORD"], dbname=env["POSTGRES_DB"])
cur = con.cursor()

# 1. the isochrone itself: nearest node, then every node reached within 1,200 m
cur.execute("""SELECT node_id, ST_Distance(geom_utm, p) FROM walk_nodes,
               (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s) AS p) q
               ORDER BY geom_utm <-> p LIMIT 1""", (LON, LAT, UTM))
start, snap_m = cur.fetchone()
cur.execute(f"""CREATE TEMP TABLE reached AS
                SELECT r.node, r.agg_cost, n.geom_utm FROM pgr_drivingDistance('{EDGES}', %s, %s, false) r
                JOIN walk_nodes n ON n.node_id = r.node""", (start, DIST_M))
cur.execute("SELECT count(*), ST_AsBinary(ST_Collect(geom_utm)) FROM reached")
n_nodes, pts_wkb = cur.fetchone()
pts = shapely.from_wkb(pts_wkb)
# reached edges = both end nodes reached (exactly what networkx.ego_graph keeps in Phase 3)
cur.execute("""SELECT count(*), ST_AsBinary(ST_Collect(e.geom_utm)) FROM walk_edges_routing e
               WHERE e.source IN (SELECT node FROM reached) AND e.target IN (SELECT node FROM reached)""")
n_edges, edges_wkb = cur.fetchone()
reached_edges = shapely.from_wkb(edges_wkb)
print(f"start node {start} ({snap_m:.0f} m from the point), reached {n_nodes} nodes and {n_edges} edges within {DIST_M} m")

# 2. the four polygons (all in UTM metres)
polys = {
    "convex hull (ST_ConvexHull)": shapely.convex_hull(pts),
    "concave hull, ratio 0.7": shapely.concave_hull(pts, ratio=0.7, allow_holes=False),
    "concave hull, ratio 0.3 (API default)": shapely.concave_hull(pts, ratio=0.3, allow_holes=False),
    "buffered reached edges, 30 m (Phase 3)": unary_union([g.buffer(30) for g in reached_edges.geoms]),
}
# PostGIS's own numbers for the record: convex hull is native; the concave hull is the legacy fallback (GEOS 3.9)
cur.execute("SELECT ST_Area(ST_ConvexHull(ST_Collect(geom_utm))) FROM reached")
pg_convex = cur.fetchone()[0]
legacy = {}
for ratio in (0.7, 0.3):
    t0 = time.perf_counter()
    cur.execute("SELECT ST_Area(ST_ConcaveHull(ST_Collect(geom_utm), %s, false)) FROM reached", (ratio,))
    legacy[ratio] = {"area_m2": round(cur.fetchone()[0]), "seconds": round(time.perf_counter() - t0, 1)}
print(f"PostGIS: convex {pg_convex:.0f} m2; legacy ST_ConcaveHull 0.7 -> {legacy[0.7]} ; 0.3 -> {legacy[0.3]}")

near_streets = reached_edges.buffer(50)                 # ground within 50 m of a reached street
results = []
for name, g in polys.items():
    away = g.difference(near_streets).area
    results.append({"polygon": name, "area_m2": round(g.area), "area_km2": round(g.area / 1e6, 3),
                    "share_more_than_50m_from_a_reached_street_pct": round(100 * away / g.area, 1),
                    "vertices": int(shapely.get_num_coordinates(g))})
print(f"\n{'polygon':42s} {'area m2':>10s} {'km2':>7s} {'>50 m from street':>18s} {'vertices':>9s}")
for r in results:
    print(f"{r['polygon']:42s} {r['area_m2']:10,d} {r['area_km2']:7.3f} {r['share_more_than_50m_from_a_reached_street_pct']:17.1f}% {r['vertices']:9d}")

# 3. figure: four panels, same extent, reached streets in blue, polygon in red
hull_wkb = shapely.to_wkb(polys["convex hull (ST_ConvexHull)"])     # shapely WKB carries no SRID: ST_SetSRID says it is UTM
cur.execute("SELECT ST_AsBinary(ST_Collect(geom_utm)) FROM walk_edges_routing WHERE geom_utm && ST_Expand(ST_SetSRID(%s::geometry, %s), 200)",
            (hull_wkb, UTM))
all_edges = shapely.from_wkb(cur.fetchone()[0])
cur.execute("SELECT ST_AsBinary(geom_utm), name FROM services WHERE ST_DWithin(geom_utm, ST_SetSRID(%s::geometry, %s), 200)", (hull_wkb, UTM))
svc = [(shapely.from_wkb(w), nm) for w, nm in cur.fetchall()]
cur.execute("SELECT ST_X(p), ST_Y(p) FROM (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s) AS p) q", (LON, LAT, UTM))
px, py = cur.fetchone()
minx, miny, maxx, maxy = polys["convex hull (ST_ConvexHull)"].buffer(150).bounds

fig, axes = plt.subplots(2, 2, figsize=(13, 13))
for ax, (name, g), r in zip(axes.flat, polys.items(), results):
    gpd.GeoSeries([all_edges], crs=UTM).plot(ax=ax, color="#c8c8c8", linewidth=0.6)
    gpd.GeoSeries([g], crs=UTM).plot(ax=ax, facecolor="#d62728", alpha=0.25, edgecolor="#d62728", linewidth=1.5)
    gpd.GeoSeries([reached_edges], crs=UTM).plot(ax=ax, color="#1f4e9c", linewidth=1.3)
    gpd.GeoSeries([pts], crs=UTM).plot(ax=ax, color="#1f4e9c", markersize=5)
    for geom, nm in svc:
        ax.plot(geom.x, geom.y, marker="o", color="orange", markersize=7, markeredgecolor="black")
    ax.plot(px, py, marker="*", color="black", markersize=14)
    ax.set_xlim(minx, maxx); ax.set_ylim(miny, maxy); ax.set_axis_off()
    ax.set_title(f"{name}\n{r['area_m2']:,} m² = {r['area_km2']} km²; {r['share_more_than_50m_from_a_reached_street_pct']} % of it >50 m from a reached street", fontsize=10)
fig.suptitle(f"B3: the same 15-minute walk ({DIST_M} m from node {start}, {n_nodes} nodes reached) drawn four ways\n"
             "blue = reached streets and nodes, red = polygon handed to the user, star = click, orange = PGs/hostels", fontsize=12)
png = ROOT / "docs" / "screenshots" / "bonus_b3_hulls.png"
fig.savefig(png, dpi=120, bbox_inches="tight")
print("saved", png.relative_to(ROOT).as_posix())

out = ROOT / "docs" / "outputs" / "bonus_b3_hulls.json"
out.write_text(json.dumps({"point": [LON, LAT], "start_node": start, "snap_m": round(snap_m, 1), "distance_m": DIST_M,
                           "reached_nodes": n_nodes, "reached_edges": n_edges, "polygons": results,
                           "postgis_convex_hull_m2": round(pg_convex), "postgis_legacy_concave_hull": {str(k): v for k, v in legacy.items()},
                           "geos_shapely": shapely.geos_version_string}, indent=1), encoding="utf-8")
print("saved", out.relative_to(ROOT).as_posix())
