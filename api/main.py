"""Bonus: live walking-isochrone API on PostGIS + pgRouting (FastAPI).

Two endpoints, both GET, both answering GeoJSON in EPSG:4326:

  /isochrone?lon=&lat=&minutes=   the area reachable on foot in N minutes from the click:
                                  nearest street node -> pgr_drivingDistance -> concave hull of the reached nodes
  /nearest?lon=&lat=&k=           the k PGs/hostels closest by WALKING time (pgr_dijkstraCost, one-to-many)

Both set two response headers for the B1 latency question:
  X-DB-Time-ms     time this process spent waiting for PostgreSQL (all queries of the request added up)
  X-Total-Time-ms  time from the start of the handler to the moment the answer was ready
The difference is API time (Python, JSON); whatever the browser measures on top of X-Total is network time.

Assumptions are the same as Phase 3: 4.8 km/h = 80 m per minute, snap to the nearest node.
The database URL comes from the environment (DATABASE_URL), set by docker-compose.yml; nothing is hard-coded.

Two switches exist only so the B1 "before / after" numbers can be reproduced at any time:
  edges=all|bbox   load the whole graph into pgRouting, or only the edges around the click
                   (default bbox for /isochrone, all for /nearest: see the B1 measurements in ANSWERS.md)
  hull=postgis|shapely   ST_ConcaveHull inside PostgreSQL, or the same GEOS algorithm in Python (default shapely).
  The database image (pgrouting/pgrouting:16-3.5-3.7, Debian 11) has GEOS 3.9, and PostGIS only uses the fast
  native concave hull from GEOS 3.11 on; below that it falls back to a legacy plpgsql implementation that took
  about 7 s for 150 points. shapely 2 ships its own GEOS (>= 3.11), so the identical algorithm runs in ~2 ms.

Interactive documentation (try the endpoints in the browser): http://localhost:8000/docs
"""
import json
import os
import time
from contextlib import asynccontextmanager

import shapely
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import ConnectionPool

SPEED_M_PER_MIN = 80.0            # 4.8 km/h
HULL_RATIO = 0.3                  # concave hull target ratio (1 = convex hull, smaller = tighter)
UTM = 32643                       # WGS 84 / UTM zone 43N: metres for the network and the hull
EDGE_COLUMNS = "SELECT id, source, target, cost, reverse_cost FROM walk_edges_routing"
# clicks are accepted only inside this lon/lat window (ward + margin); anything else is a user error, not a 500
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = 73.76, 18.49, 73.90, 18.62
NEAREST_RADII_M = (1500, 3000, 6000)   # expanding search windows for /nearest (see nearest_services)

# A small pool of open connections: a brand-new PostgreSQL login costs 20-40 ms, which would be a large share of a
# sub-second budget. open=False: the pool connects on startup (lifespan below), not at import time.
pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=8, open=False)


@asynccontextmanager
async def lifespan(_app):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Prabhag 11 walking-isochrone API (pgRouting)", lifespan=lifespan)
# CORS: the MapLibre page is served from another port (8088), so the browser needs permission to read our answers,
# including the two timing headers (browsers hide non-standard headers unless they are exposed).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"],
                   expose_headers=["X-DB-Time-ms", "X-Total-Time-ms"])


class Timer:
    """Adds up the milliseconds spent inside PostgreSQL for one request."""

    def __init__(self):
        self.db_ms = 0.0
        self.t_start = time.perf_counter()

    def query(self, cur, sql, params=None):
        t0 = time.perf_counter()
        cur.execute(sql, params)
        rows = cur.fetchall()
        self.db_ms += (time.perf_counter() - t0) * 1000
        return rows

    def total_ms(self):
        return (time.perf_counter() - self.t_start) * 1000


def check_point(lon, lat):
    if not (LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX):
        raise HTTPException(400, f"point must be inside the study area: lon {LON_MIN}-{LON_MAX}, lat {LAT_MIN}-{LAT_MAX}")


def nearest_node(cur, t, lon, lat):
    """Snap the click to the nearest street node. KNN order-by on the GiST index of walk_nodes.geom_utm.
    Returns node_id, snap distance (m) and the click in UTM metres (x, y)."""
    rows = t.query(cur, """
        SELECT node_id,
               ST_Distance(geom_utm, ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(utm)s)) AS snap_m,
               ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(utm)s)) AS x,
               ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(utm)s)) AS y
        FROM walk_nodes
        ORDER BY geom_utm <-> ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(utm)s)
        LIMIT 1""", {"lon": lon, "lat": lat, "utm": UTM})
    if not rows:
        raise HTTPException(500, "walk_nodes is empty: run the Phase 1 notebook and sql/06_pgrouting_topology.sql")
    node_id, snap_m, x, y = rows[0]
    return int(node_id), float(snap_m), float(x), float(y)


def edges_sql(mode, x, y, radius_m):
    """The inner SQL that pgRouting runs to load the graph.
    'all'  : every segment (8,545 rows): pgRouting rebuilds the whole in-memory graph on every request.
    'bbox' : only segments whose bounding box touches the square of half-width radius_m around the click,
             found through the GiST index. No path of length <= radius_m can leave that square, so the
             answer inside the budget is identical; only the graph-loading work shrinks (B1 optimisation).
    x, y, radius_m are floats computed by PostGIS itself, never raw user text, so formatting them in is safe."""
    if mode == "all":
        return EDGE_COLUMNS
    return (f"{EDGE_COLUMNS} WHERE geom_utm && ST_Expand(ST_SetSRID(ST_MakePoint({x:.3f}, {y:.3f}), {UTM}), {radius_m:.1f})")


def timing_headers(response, t):
    response.headers["X-DB-Time-ms"] = f"{t.db_ms:.1f}"
    response.headers["X-Total-Time-ms"] = f"{t.total_ms():.1f}"


@app.get("/")
def index():
    return {"service": "Prabhag 11 walking-isochrone API (FastAPI + PostGIS + pgRouting)",
            "endpoints": {"/isochrone": "?lon=73.829&lat=18.557&minutes=15[&edges=bbox|all][&hull=shapely|postgis]",
                          "/nearest": "?lon=73.829&lat=18.557&k=5[&edges=all|bbox]",
                          "/health": "database and topology check", "/docs": "interactive documentation"},
            "speed_m_per_min": SPEED_M_PER_MIN, "hull": f"ST_ConcaveHull ratio {HULL_RATIO}"}


@app.get("/health")
def health():
    with pool.connection() as con, con.cursor() as cur:
        cur.execute("SELECT postgis_lib_version(), postgis_geos_version(), pgr_version()")
        postgis, geos_db, pgr = cur.fetchone()
        cur.execute("SELECT to_regclass('public.walk_edges_routing') IS NOT NULL AND to_regclass('public.services_nodes') IS NOT NULL")
        topology_ready = cur.fetchone()[0]
    return {"status": "ok", "postgis": postgis, "geos_in_database": geos_db, "geos_in_api": shapely.geos_version_string,
            "pgrouting": pgr, "topology_ready": topology_ready}


@app.get("/isochrone")
def isochrone(response: Response,
              lon: float = Query(..., description="longitude of the click, EPSG:4326"),
              lat: float = Query(..., description="latitude of the click"),
              minutes: float = Query(15, ge=1, le=60, description="walking time budget"),
              edges: str = Query("bbox", pattern="^(all|bbox)$", description="graph loading: bbox (fast) or all (B1 'before')"),
              hull: str = Query("shapely", pattern="^(postgis|shapely)$", description="where the concave hull is computed")):
    check_point(lon, lat)
    t = Timer()
    distance_m = minutes * SPEED_M_PER_MIN
    with pool.connection() as con, con.cursor() as cur:
        start, snap_m, x, y = nearest_node(cur, t, lon, lat)
        # pgr_drivingDistance = Dijkstra that stops at the distance budget and returns every node it reached.
        # directed := false, so cost and reverse_cost are both used (they are equal anyway for walking).
        pgr = {"edges": edges_sql(edges, x, y, distance_m), "start": start, "dist": distance_m, "ratio": HULL_RATIO}
        if hull == "postgis":
            # Everything in one SQL statement: reached nodes -> multipoint -> ST_ConcaveHull -> GeoJSON in 4326.
            # With fewer than three nodes (a click on a dead end) a hull is impossible, so the points are buffered.
            rows = t.query(cur, """
                WITH reached AS (
                    SELECT node, agg_cost FROM pgr_drivingDistance(%(edges)s, %(start)s, %(dist)s, false)),
                pts AS (
                    SELECT n.geom_utm, r.agg_cost FROM reached r JOIN walk_nodes n ON n.node_id = r.node),
                h AS (
                    SELECT count(*) AS n, max(agg_cost) AS farthest_m,
                           CASE WHEN count(*) >= 3 THEN ST_ConcaveHull(ST_Collect(geom_utm), %(ratio)s, false)
                                ELSE ST_Buffer(ST_Collect(geom_utm), 30) END AS g
                    FROM pts),
                poly AS (
                    SELECT n, farthest_m, CASE WHEN ST_Dimension(g) = 2 THEN g ELSE ST_Buffer(g, 30) END AS g FROM h)
                SELECT n, farthest_m, ST_Area(g), ST_AsGeoJSON(ST_Transform(g, 4326), 6) FROM poly""", pgr)
            n, farthest_m, area_m2, geojson = rows[0]
        else:
            # Step 1 (SQL): the reached nodes as UTM coordinates. Step 2 (Python): the concave hull with shapely's
            # GEOS. Step 3 (SQL): PostGIS reprojects the hull to EPSG:4326 and writes the GeoJSON, as before.
            rows = t.query(cur, """
                SELECT ST_X(n.geom_utm), ST_Y(n.geom_utm), r.agg_cost
                FROM pgr_drivingDistance(%(edges)s, %(start)s, %(dist)s, false) r
                JOIN walk_nodes n ON n.node_id = r.node""", pgr)
            n = len(rows)
            farthest_m = max((r[2] for r in rows), default=0)
            pts = shapely.multipoints([(r[0], r[1]) for r in rows]) if n else None
            g = shapely.concave_hull(pts, ratio=HULL_RATIO, allow_holes=False) if n >= 3 else (pts.buffer(30) if n else None)
            if g is not None and shapely.get_dimensions(g) < 2:      # three nodes in a row give a line, not a polygon
                g = g.buffer(30)
            area_m2 = g.area if g is not None else 0
            geojson = t.query(cur, "SELECT ST_AsGeoJSON(ST_Transform(ST_GeomFromWKB(%s, %s), 4326), 6)",
                              (shapely.to_wkb(g), UTM))[0][0] if g is not None else None
    if not n:
        raise HTTPException(404, "no street node reachable from this point")
    feature = {"type": "Feature", "geometry": json.loads(geojson),
               "properties": {"minutes": minutes, "speed_m_per_min": SPEED_M_PER_MIN, "distance_m": distance_m,
                              "start_node": start, "snap_m": round(snap_m, 1), "reached_nodes": int(n),
                              "farthest_node_m": round(float(farthest_m), 1), "area_m2": round(float(area_m2)),
                              "hull": f"concave hull ratio {HULL_RATIO} ({hull})", "edges": edges,
                              "db_ms": round(t.db_ms, 1), "total_ms": round(t.total_ms(), 1)}}
    timing_headers(response, t)
    return feature


def nearest_services(cur, t, start, x, y, k, mode):
    """k services ranked by path length from the start node. One pgr_dijkstraCost call from the start node to
    all 54 service nodes at once (one-to-many). With mode 'bbox' the graph is loaded in growing windows:
    a result set of k services whose longest path is shorter than the window radius cannot change when more
    edges are added (any path to a service outside the window is longer than the radius), so the search stops
    there; otherwise the window doubles, and the last attempt is the whole graph."""
    sql = """
        WITH costs AS (
            SELECT end_vid, agg_cost
            FROM pgr_dijkstraCost(%(edges)s, %(start)s, (SELECT array_agg(DISTINCT node_id) FROM services_nodes), false))
        SELECT sn.service_id, sn.name, sn.service_type, sn.inside_area, sn.snap_m,
               CASE WHEN sn.node_id = %(start)s THEN 0 ELSE c.agg_cost END AS path_m,
               ST_X(sn.geom), ST_Y(sn.geom)
        FROM services_nodes sn LEFT JOIN costs c ON c.end_vid = sn.node_id
        WHERE sn.node_id = %(start)s OR c.agg_cost IS NOT NULL
        ORDER BY path_m LIMIT %(k)s"""
    radii = list(NEAREST_RADII_M) if mode == "bbox" else []
    for r in radii:
        rows = t.query(cur, sql, {"edges": edges_sql("bbox", x, y, r), "start": start, "k": k})
        if len(rows) == k and float(rows[-1][5]) <= r:
            return rows, r
    rows = t.query(cur, sql, {"edges": EDGE_COLUMNS, "start": start, "k": k})
    return rows, None


@app.get("/nearest")
def nearest(response: Response,
            lon: float = Query(...), lat: float = Query(...),
            k: int = Query(5, ge=1, le=54, description="how many services"),
            # default "all": the B1 benchmark showed the expanding window helps the median but not p95 for this
            # endpoint (a second or third attempt costs more than loading the whole 8,561-row graph once)
            edges: str = Query("all", pattern="^(all|bbox)$")):
    check_point(lon, lat)
    t = Timer()
    with pool.connection() as con, con.cursor() as cur:
        start, snap_m, x, y = nearest_node(cur, t, lon, lat)
        rows, radius = nearest_services(cur, t, start, x, y, k, edges)
    features = []
    for rank, (sid, name, stype, inside, svc_snap, path_m, sx, sy) in enumerate(rows, 1):
        walk_m = float(snap_m) + float(path_m) + float(svc_snap)      # click->street + path + street->door
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(sx), float(sy)]},
                         "properties": {"rank": rank, "service_id": int(sid), "name": name, "service_type": stype,
                                        "inside_area": bool(inside), "path_m": round(float(path_m)),
                                        "snap_service_m": float(svc_snap), "walk_m": round(walk_m),
                                        "minutes": round(walk_m / SPEED_M_PER_MIN, 1)}})
    fc = {"type": "FeatureCollection", "features": features,
          "query": {"lon": lon, "lat": lat, "k": k, "start_node": start, "snap_m": round(snap_m, 1),
                    "edges": edges, "window_radius_m": radius, "db_ms": round(t.db_ms, 1), "total_ms": round(t.total_ms(), 1)}}
    timing_headers(response, t)
    return fc
