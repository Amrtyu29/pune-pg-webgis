"""Q3 baseline: how many PG / hostel listings did my EARLIER project (PuneStay) hold inside
Prabhag 11?  PuneStay's public API returns listings in a bounding box as GeoJSON; this script
asks for the ward's bbox, keeps only the points that fall inside the ward polygon, and saves
them to data/raw/punestay_baseline.geojson (git-ignored) plus a summary printed here.

    .venv\\Scripts\\python.exe analysis\\baseline_punestay.py

The live API is https://punestay.onrender.com (free tier: the first request may take ~60 s to wake)."""
import json, sys, time
from pathlib import Path
import requests
from shapely.geometry import shape, Point

ROOT = Path(__file__).resolve().parents[1]
API = "https://punestay.onrender.com/listings"

area = shape(json.loads((ROOT / "data/area/prabhag11.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])
w, s, e, n = area.bounds
params = {"bbox": f"{w:.5f},{s:.5f},{e:.5f},{n:.5f}", "limit": 500}

for attempt in range(4):
    try:
        r = requests.get(API, params=params, timeout=120, headers={"User-Agent": "pune-pg-webgis/0.1"})
        if r.status_code == 200:
            break
        print("HTTP", r.status_code, "retrying", file=sys.stderr)
    except requests.RequestException as ex:
        print(type(ex).__name__, "retrying", file=sys.stderr)
    time.sleep(20)
r.raise_for_status()
print("request:", r.url)
fc = r.json()
feats = fc.get("features", [])
inside = [f for f in feats if area.contains(Point(f["geometry"]["coordinates"]))]
print(f"listings in bbox: {len(feats)}   inside Prabhag 11: {len(inside)}")

by_type, by_source, unnamed = {}, {}, 0
for f in inside:
    p = f["properties"]
    by_type[p.get("category") or p.get("listing_type")] = by_type.get(p.get("category") or p.get("listing_type"), 0) + 1
    by_source[p.get("source") or p.get("source_label")] = by_source.get(p.get("source") or p.get("source_label"), 0) + 1
    if not p.get("name"):
        unnamed += 1
print("by type:", by_type)
print("by source:", by_source)
print("without name:", unnamed)
print("\nlistings inside the ward:")
for f in sorted(inside, key=lambda f: str(f["properties"].get("name"))):
    p = f["properties"]
    lon, lat = f["geometry"]["coordinates"]
    print(f"  {p.get('name')!s:45s} {p.get('category') or p.get('listing_type')!s:8s} {p.get('source') or p.get('source_label')!s:10s} {lat:.5f},{lon:.5f}")

out = ROOT / "data" / "raw"
out.mkdir(parents=True, exist_ok=True)
(out / "punestay_baseline.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": inside}), encoding="utf-8")
print("\nsaved data/raw/punestay_baseline.geojson (git-ignored)")
