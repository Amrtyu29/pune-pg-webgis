"""Phase 5 Part A: export the finished layers from PostGIS to GeoJSON files for the serverless copy
of the map (GitHub Pages).  Small layers are loaded by the client directly; the big ones (hexagons,
buildings) are turned into one PMTiles file by tippecanoe inside the GitHub Actions workflow.

    .venv\\Scripts\\python.exe analysis\\export_static.py

Writes (all EPSG:4326, coordinates rounded to 6 decimals ~ 0.1 m):
  client/data/area.geojson, services.geojson, isochrones_15min.geojson, buffers_1200m.geojson   (loaded directly)
  client/data/tiles-src/hex_r8.geojson, hex_r9.geojson, buildings.geojson                      (tippecanoe input)"""
import json
from pathlib import Path
import psycopg
from dbconf import read_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "client" / "data"
SRC = OUT / "tiles-src"
OUT.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)
env = read_env()

LAYERS = {
    # name: (folder, SQL selecting the properties + geom)
    "area": (OUT, "SELECT area_id, name, ward_number, area_km2_utm, geom FROM area"),
    "services": (OUT, "SELECT service_id, name, service_type, element_type, osmid, inside_area, geom FROM services"),
    # buffered street networks have thousands of vertices: simplify by ~3 m (0.00003 deg) for the web copy
    "isochrones_15min": (OUT, "SELECT service_id, name, service_type, inside_area, ST_SimplifyPreserveTopology(geom, 0.00003) AS geom FROM isochrones_15min"),
    "isochrones_15min_slow": (OUT, "SELECT service_id, name, ST_SimplifyPreserveTopology(geom, 0.00003) AS geom FROM isochrones_15min_slow"),
    "buffers_1200m": (OUT, "SELECT service_id, name, geom FROM buffers_1200m"),
    "hex_r8": (SRC, "SELECT h3, res, pop, net_dist_m, sl_dist_m, snap_m, covered_net_15, covered_buf_15, covered_net_slow, centre_in_ward, geom FROM hex_r8"),
    "hex_r9": (SRC, "SELECT h3, res, pop, net_dist_m, sl_dist_m, snap_m, covered_net_15, covered_buf_15, covered_net_slow, centre_in_ward, geom FROM hex_r9"),
    "buildings": (SRC, "SELECT building_id, building, name, levels, area_m2, inside_area, geom FROM buildings"),
}

with psycopg.connect(host="localhost", port=int(env.get("POSTGRES_PORT", "5434")), user=env["POSTGRES_USER"],
                     password=env["POSTGRES_PASSWORD"], dbname=env["POSTGRES_DB"]) as con, con.cursor() as cur:
    for name, (folder, sql) in LAYERS.items():
        # PostGIS builds the whole FeatureCollection; 6 decimals keep the file small
        cur.execute(f"""
            SELECT json_build_object('type','FeatureCollection','features', coalesce(json_agg(ST_AsGeoJSON(t.*, 'geom', 6)::json), '[]'::json))
            FROM ({sql}) AS t""")
        fc = cur.fetchone()[0]
        path = folder / f"{name}.geojson"
        path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
        print(f"{path.relative_to(ROOT).as_posix():45s} {len(fc['features']):6d} features  {path.stat().st_size/1024:8.0f} KB")
