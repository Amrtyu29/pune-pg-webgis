"""B1: latency of the two bonus endpoints for 50 random clicks inside the ward (a script, not by hand).

    .venv\\Scripts\\python.exe analysis\\bench_bonus.py            (API on http://localhost:8000, Compose stack running)

For every point and every variant the script records three numbers:
  db_ms     X-DB-Time-ms header   = time the API waited for PostgreSQL (pgRouting + PostGIS)
  api_ms    X-Total-Time-ms - db  = Python work in the API (building the hull / the JSON)
  net_ms    round trip - total    = HTTP + Docker port forwarding + the browser side (here: the requests library)
and reports p50 / p95 of each, plus the round trip the client actually sees.

Variants (the switches exist only so this "before / after" can be re-run at the viva):
  isochrone  hull=postgis edges=all   the first version: ST_ConcaveHull inside PostgreSQL on the whole graph
  isochrone  hull=shapely edges=all   optimisation 1: hull in the API with shapely's GEOS 3.14 (database GEOS is 3.9)
  isochrone  hull=shapely edges=bbox  optimisation 2: pgRouting loads only the edges around the click (default)
  nearest    edges=all / edges=bbox   whole graph vs expanding window (default bbox)

Writes docs/outputs/bonus_b1_latency.json with the summary and every raw measurement."""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import psycopg
import requests
import shapely
from shapely.geometry import Point

from dbconf import read_env

ROOT = Path(__file__).resolve().parents[1]
API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SEED = 20261120
N_POINTS = 50
MINUTES = 15
K = 5
SLOW_POINTS = 10          # the 7-second hull=postgis variant is run for 10 of the 50 points only (it would take 6 minutes for 50)

VARIANTS = [
    # label, path, extra query parameters, number of points
    ("isochrone: hull in PostgreSQL (legacy ST_ConcaveHull), whole graph", "/isochrone", {"minutes": MINUTES, "hull": "postgis", "edges": "all"}, SLOW_POINTS),
    ("isochrone: hull in the API (shapely/GEOS 3.14), whole graph", "/isochrone", {"minutes": MINUTES, "hull": "shapely", "edges": "all"}, N_POINTS),
    ("isochrone: hull in the API, edges around the click (default)", "/isochrone", {"minutes": MINUTES, "hull": "shapely", "edges": "bbox"}, N_POINTS),
    ("nearest k=5: whole graph", "/nearest", {"k": K, "edges": "all"}, N_POINTS),
    ("nearest k=5: expanding window (default)", "/nearest", {"k": K, "edges": "bbox"}, N_POINTS),
]

# 1. 50 random points inside the ward: rejection sampling in the ward's bounding box with a fixed seed (same idea as Q6)
env = read_env()
with psycopg.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5434")), user=env["POSTGRES_USER"],
                     password=env["POSTGRES_PASSWORD"], dbname=env["POSTGRES_DB"]) as con:
    ward = shapely.from_wkb(con.execute("SELECT ST_AsBinary(geom) FROM area").fetchone()[0])      # EPSG:4326
rng = random.Random(SEED)
minx, miny, maxx, maxy = ward.bounds
points = []
while len(points) < N_POINTS:
    p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
    if ward.contains(p):
        points.append((round(p.x, 6), round(p.y, 6)))
print(f"{len(points)} random points inside the ward (seed {SEED}); API {API}")

# 2. warm-up: the first request after a start pays for the connection pool and the planner caches
requests.get(f"{API}/health", timeout=30).raise_for_status()
requests.get(f"{API}/isochrone", params={"lon": points[0][0], "lat": points[0][1], "minutes": MINUTES}, timeout=60).raise_for_status()


def pct(values, q):
    return float(np.percentile(values, q))


summary, raw = [], []
for label, path, params, n in VARIANTS:
    rows = []
    for i, (lon, lat) in enumerate(points[:n]):
        t0 = time.perf_counter()
        r = requests.get(f"{API}{path}", params={"lon": lon, "lat": lat, **params}, timeout=120)
        rt = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        db = float(r.headers["X-DB-Time-ms"])
        total = float(r.headers["X-Total-Time-ms"])
        body = r.json()
        extra = body["properties"]["reached_nodes"] if path == "/isochrone" else body["query"]["window_radius_m"]
        rows.append({"i": i, "lon": lon, "lat": lat, "db_ms": db, "api_ms": round(total - db, 2), "net_ms": round(rt - total, 2),
                     "total_ms": total, "round_trip_ms": round(rt, 1), "bytes": len(r.content),
                     ("reached_nodes" if path == "/isochrone" else "window_radius_m"): extra})
    s = {"variant": label, "path": path, "params": params, "points": n}
    for key in ("db_ms", "api_ms", "net_ms", "total_ms", "round_trip_ms"):
        vals = [x[key] for x in rows]
        s[key] = {"p50": round(pct(vals, 50), 1), "p95": round(pct(vals, 95), 1), "max": round(max(vals), 1)}
    summary.append(s)
    raw.append({"variant": label, "rows": rows})
    print(f"\n{label}  ({n} points)")
    print(f"  {'':14s} {'p50':>9s} {'p95':>9s} {'max':>9s}")
    for key in ("db_ms", "api_ms", "net_ms", "total_ms", "round_trip_ms"):
        print(f"  {key:14s} {s[key]['p50']:9.1f} {s[key]['p95']:9.1f} {s[key]['max']:9.1f}")

out = ROOT / "docs" / "outputs" / "bonus_b1_latency.json"
out.write_text(json.dumps({"api": API, "seed": SEED, "minutes": MINUTES, "k": K, "points": points,
                           "summary": summary, "raw": raw}, indent=1), encoding="utf-8")
print("\nsaved", out.relative_to(ROOT).as_posix())
