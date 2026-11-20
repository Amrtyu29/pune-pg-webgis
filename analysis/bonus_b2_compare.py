"""B2: two engines, one question. For 10 H3 res-9 cells, the walking distance from the cell centre to the nearest
PG/hostel computed by
  (a) Phase 3 / OSMnx: hex_r9.net_dist_m = snap distance to the nearest node + networkx multi-source Dijkstra
      on the undirected projected graph (analysis/02_isochrones_h3.ipynb, section 3), and
  (b) pgRouting: the same snap in SQL (KNN on walk_nodes.geom_utm) + pgr_dijkstraCost from that node to the
      54 service nodes (services_nodes) on walk_edges_routing, minimum cost + snap.
Any cell that differs by more than 10 % is re-checked with networkx (same node? same length?) so the cause can be
named, and all ten are drawn on a map with their pgRouting route.

    .venv\\Scripts\\python.exe analysis\\bonus_b2_compare.py

Writes docs/outputs/bonus_b2_compare.json and docs/screenshots/bonus_b2_engines.png."""
import json
import random
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import osmnx as ox
import psycopg
import shapely
from shapely.geometry import Point

from dbconf import read_env, engine_from_env

ROOT = Path(__file__).resolve().parents[1]
UTM = 32643
SEED = 20261120
EDGES = "SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing"
env = read_env()
con = psycopg.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5434")), user=env["POSTGRES_USER"],
                      password=env["POSTGRES_PASSWORD"], dbname=env["POSTGRES_DB"])
cur = con.cursor()

# 1. ten populated res-9 cells with their centre inside the ward, picked with a fixed seed
cur.execute("SELECT h3 FROM hex_r9 WHERE centre_in_ward AND pop > 0 ORDER BY h3")
cells = random.Random(SEED).sample([r[0] for r in cur.fetchall()], 10)

# 2. pgRouting answer per cell, all in SQL: centre -> nearest node (+snap) -> cheapest service node.
#    Two readings of the pgr_dijkstraCost output are kept:
#    "naive"  = the smallest agg_cost it returns. pgr_dijkstraCost returns NO row for a target equal to the start
#               node (pgRouting treats start = end as "no path"), so a cell whose nearest node IS a service node
#               silently gets the SECOND-nearest service. This was the first version of the script.
#    "fixed"  = the same, but a service sitting on the start node costs 0 (the CASE below; the API does the same).
SQL = f"""
WITH c AS (SELECT h3, net_dist_m AS osmnx_m, snap_m AS osmnx_snap_m, ST_Centroid(geom_utm) AS g FROM hex_r9 WHERE h3 = %s),
start AS (SELECT n.node_id, ST_Distance(n.geom_utm, c.g) AS snap_m FROM c, walk_nodes n ORDER BY n.geom_utm <-> c.g LIMIT 1),
costs AS (SELECT end_vid, agg_cost FROM pgr_dijkstraCost('{EDGES}', (SELECT node_id FROM start), (SELECT array_agg(DISTINCT node_id) FROM services_nodes), false)),
cand AS (SELECT sn.service_id, sn.name, sn.node_id,
                CASE WHEN sn.node_id = s.node_id THEN 0 ELSE k.agg_cost END AS path_m
         FROM services_nodes sn CROSS JOIN start s
         LEFT JOIN costs k ON k.end_vid = sn.node_id
         WHERE sn.node_id = s.node_id OR k.agg_cost IS NOT NULL)
SELECT c.h3, c.osmnx_m, c.osmnx_snap_m, s.node_id, s.snap_m,
       (SELECT min(agg_cost) FROM costs) AS naive_path_m,
       b.path_m, b.service_id, b.name, b.node_id, ST_X(c.g), ST_Y(c.g)
FROM c, start s, (SELECT * FROM cand ORDER BY path_m LIMIT 1) b"""
rows = []
for h in cells:
    cur.execute(SQL, (h,))
    h3, osmnx_m, osmnx_snap, node, snap, naive_cost, cost, sid, sname, snode, cx, cy = cur.fetchone()
    pgr_m, naive_m = float(cost) + float(snap), float(naive_cost) + float(snap)
    rows.append(dict(h3=h3, osmnx_m=float(osmnx_m), osmnx_snap_m=float(osmnx_snap), pgr_node=int(node), pgr_snap_m=round(float(snap), 1),
                     pgr_naive_path_m=round(float(naive_cost), 1), pgr_naive_m=round(naive_m, 1),
                     diff_naive_pct=round(100 * (naive_m - float(osmnx_m)) / float(osmnx_m), 2),
                     pgr_path_m=round(float(cost), 1), pgr_m=round(pgr_m, 1), service_id=int(sid), service=sname, service_node=int(snode),
                     diff_pct=round(100 * (pgr_m - float(osmnx_m)) / float(osmnx_m), 2), cx=float(cx), cy=float(cy)))

# 3. the networkx side, recomputed exactly as the notebook did, to explain any difference (same node? same length?)
G = ox.load_graphml(ROOT / "data/raw/walk_extent.graphml")
Gu = ox.convert.to_undirected(ox.project_graph(G, to_crs=f"EPSG:{UTM}"))
cur.execute("SELECT DISTINCT node_id FROM services_nodes")
service_nodes = {r[0] for r in cur.fetchall()}
dist_to_service = nx.multi_source_dijkstra_path_length(Gu, sources=service_nodes, weight="length")
for r in rows:
    n, s = ox.distance.nearest_nodes(Gu, r["cx"], r["cy"], return_dist=True)
    r["nx_node"] = int(n)
    r["nx_snap_m"] = round(float(s), 1)
    r["nx_path_m"] = round(float(dist_to_service.get(n, float("inf"))), 1)
    r["nx_path_from_pgr_node_m"] = round(float(dist_to_service.get(r["pgr_node"], float("inf"))), 1)
    r["same_node"] = r["nx_node"] == r["pgr_node"]

print(f"{'h3':16s} {'OSMnx m':>8s} {'pgr naive m':>11s} {'diff %':>8s} {'pgr fixed m':>11s} {'diff %':>7s}  same node  snap  nearest service (pgRouting)")
for r in rows:
    print(f"{r['h3']:16s} {r['osmnx_m']:8.1f} {r['pgr_naive_m']:11.1f} {r['diff_naive_pct']:8.2f} {r['pgr_m']:11.1f} {r['diff_pct']:7.2f}  "
          f"{str(r['same_node']):9s} {r['pgr_snap_m']:5.1f}  #{r['service_id']} {r['service'] or '(no name)'}")
over_naive = [r for r in rows if abs(r["diff_naive_pct"]) > 10]
over = [r for r in rows if abs(r["diff_pct"]) > 10]
print(f"\ncells differing by more than 10 % with the naive reading: {len(over_naive)}; after the start-node fix: {len(over)}")
for r in over_naive:
    print(f"  {r['h3']}  naive {r['diff_naive_pct']:+.1f} % -> fixed {r['diff_pct']:+.1f} %;  snap nx/pgr {r['nx_snap_m']} / {r['pgr_snap_m']} m; "
          f"node nx/pgr {r['nx_node']} / {r['pgr_node']}; networkx path {r['nx_path_m']} m, pgRouting naive path {r['pgr_naive_path_m']} m")

# 4. map: the ten cells, their centre, the pgRouting route to the nearest service, coloured by the % difference
cur.execute("SELECT ST_AsBinary(geom_utm) FROM area")
ward = shapely.from_wkb(cur.fetchone()[0])
cur.execute("SELECT ST_AsBinary(ST_Collect(geom_utm)) FROM walk_edges_routing")
edges = shapely.from_wkb(cur.fetchone()[0])
engine = engine_from_env()                                   # geopandas wants a SQLAlchemy engine, not a raw psycopg connection
hexes = gpd.read_postgis("SELECT h3, geom_utm AS geom FROM hex_r9 WHERE h3 = ANY(%(cells)s)", engine, geom_col="geom", params={"cells": cells}, crs=UTM)
services = gpd.read_postgis("SELECT service_id, name, geom_utm AS geom FROM services", engine, geom_col="geom", crs=UTM)
routes = []
for r in rows:
    cur.execute(f"""SELECT ST_AsBinary(ST_LineMerge(ST_Collect(e.geom_utm)))
                    FROM pgr_dijkstra('{EDGES}', %s, %s, false) p JOIN walk_edges_routing e ON e.id = p.edge""",
                (r["pgr_node"], r["service_node"]))
    wkb = cur.fetchone()[0]
    routes.append(shapely.from_wkb(wkb) if wkb else None)

fig, ax = plt.subplots(figsize=(11, 10))
gpd.GeoSeries([edges], crs=UTM).clip(ward.buffer(300)).plot(ax=ax, color="#bbbbbb", linewidth=0.4)
gpd.GeoSeries([ward], crs=UTM).boundary.plot(ax=ax, color="black", linewidth=1)
hexes.plot(ax=ax, facecolor="none", edgecolor="#1f77b4", linewidth=1.5)
services.plot(ax=ax, color="red", markersize=14, zorder=4)
lines = []
for i, (r, route) in enumerate(zip(rows, routes), 1):
    flagged = abs(r["diff_naive_pct"]) > 10
    colour = "#d62728" if flagged else "#2ca02c"
    if route is not None:
        gpd.GeoSeries([route], crs=UTM).plot(ax=ax, color=colour, linewidth=2, zorder=3)
    ax.plot([r["cx"]], [r["cy"]], marker="*", color="black", markersize=10, zorder=5)
    ax.annotate(str(i), (r["cx"], r["cy"]), xytext=(5, 5), textcoords="offset points", fontsize=10, weight="bold", color=colour,
                bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec=colour, lw=0.8), zorder=6)
    line = f"{i:>2}. OSMnx {r['osmnx_m']:7.1f} m | pgRouting {r['pgr_m']:7.1f} m ({r['diff_pct']:+.1f} %)"
    if flagged:
        line += f"\n    naive pgr_dijkstraCost {r['pgr_naive_m']:.0f} m ({r['diff_naive_pct']:+.0f} %): the cell's\n    nearest node IS the service node; pgRouting returns no start=end row"
    lines.append(line)
ax.text(0.01, 0.01, "\n".join(lines), transform=ax.transAxes, fontsize=8, family="monospace", va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#666", alpha=0.95))
minx, miny, maxx, maxy = ward.buffer(250).bounds
ax.set_xlim(minx - 1900, maxx); ax.set_ylim(miny, maxy)          # room on the left for the table
ax.set_title("B2: walking distance from 10 H3 res-9 cell centres (stars) to the nearest PG/hostel (red dots)\n"
             "OSMnx/networkx (Phase 3) vs pgRouting (bonus API); routes = pgRouting path; red = naive pgRouting reading >10 % off")
ax.set_axis_off()
png = ROOT / "docs" / "screenshots" / "bonus_b2_engines.png"
fig.savefig(png, dpi=130, bbox_inches="tight")
print("saved", png.relative_to(ROOT).as_posix())

out = ROOT / "docs" / "outputs" / "bonus_b2_compare.json"
out.write_text(json.dumps({"seed": SEED, "cells": rows, "over_10_percent_naive": [r["h3"] for r in over_naive],
                           "over_10_percent_fixed": [r["h3"] for r in over]}, indent=1), encoding="utf-8")
print("saved", out.relative_to(ROOT).as_posix())
