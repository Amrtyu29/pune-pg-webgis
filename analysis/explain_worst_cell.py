"""Q7 helper: where is the worst-served populated H3 cell, and what does the walking route from its
centre to the nearest PG/hostel pass through?  Prints the cell centre, the straight-line and network
distances, and the named streets / bridges along the shortest path, so the barrier can be named.

    .venv\\Scripts\\python.exe analysis\\explain_worst_cell.py 89608851867ffff
"""
import json, sys
from pathlib import Path
import h3, networkx as nx, osmnx as ox
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import text
from dbconf import engine_from_env

ROOT = Path(__file__).resolve().parents[1]
UTM = 32643
cell = sys.argv[1] if len(sys.argv) > 1 else json.loads((ROOT / "docs/outputs/phase3_results.json").read_text())["q7"]["worst_cell_r9"]
lat, lng = h3.cell_to_latlng(cell)
print(f"cell {cell} (res {h3.get_resolution(cell)}) centre: {lat:.5f}, {lng:.5f}  https://www.openstreetmap.org/#map=16/{lat:.5f}/{lng:.5f}")

G = ox.load_graphml(ROOT / "data/raw/walk_extent.graphml")
Gu = ox.convert.to_undirected(ox.project_graph(G, to_crs=f"EPSG:{UTM}"))
with engine_from_env().connect() as con:
    svc = gpd.read_postgis(text("SELECT service_id, name, inside_area, geom FROM services"), con, geom_col="geom", crs=4326).to_crs(UTM)
svc["node"] = ox.distance.nearest_nodes(Gu, svc.geometry.x.values, svc.geometry.y.values)

c = gpd.GeoSeries([Point(lng, lat)], crs=4326).to_crs(UTM).iloc[0]
n0, snap = ox.distance.nearest_nodes(Gu, c.x, c.y, return_dist=True)
lengths = nx.single_source_dijkstra_path_length(Gu, n0, weight="length")
best = min(((sid, nm, lengths[n]) for sid, nm, n in zip(svc.service_id, svc.name, svc.node) if n in lengths), key=lambda t: t[2])
sid, name, d = best
print(f"snap to street: {snap:.0f} m; nearest service by network: #{sid} {name!r} at {d + snap:.0f} m "
      f"(straight line {c.distance(svc.loc[svc.service_id == sid, 'geom'].iloc[0]):.0f} m)")
path = nx.shortest_path(Gu, n0, int(svc.loc[svc.service_id == sid, "node"].iloc[0]), weight="length")
names, seen = [], set()
for u, v in zip(path[:-1], path[1:]):
    data = min(Gu.get_edge_data(u, v).values(), key=lambda e: e["length"])
    tag = f"{data.get('name', '?')} [{data.get('highway', '?')}{', bridge' if str(data.get('bridge', '')).lower() in ('yes', 'true') else ''}]"
    if tag not in seen:
        seen.add(tag); names.append(tag)
print("route passes:", " -> ".join(names))
