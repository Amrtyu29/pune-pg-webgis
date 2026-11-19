"""Registration check: how many PG / hostel features does OpenStreetMap hold INSIDE the
study-area polygon (not just its bounding box)?  Run before registering in the class sheet.

    .venv\\Scripts\\python.exe analysis\\check_feature_count.py

It asks the Overpass API with a "poly:" filter built from data/area/prabhag11.geojson, removes
duplicates (same name within 25 m), and prints the count plus the overpass turbo query you can
paste to reproduce it.  No personal data is sent: only a generic User-Agent."""
import json, math, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "data" / "area" / "prabhag11.geojson"
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
HEADERS = {"User-Agent": "pune-pg-webgis-assignment/0.1"}

# The tags that mean "PG or hostel" in OSM.  Pune mappers use several, so we union them and
# also catch names that say PG / Paying Guest / Hostel but carry a generic tag (e.g. building=yes).
TAG_FILTERS = [
    '["tourism"="hostel"]',
    '["tourism"="guest_house"]',
    '["building"="dormitory"]',
    '["amenity"="dormitory"]',
    '["name"~"[Hh]ostel|[Pp]aying [Gg]uest|(^|[^A-Za-z])PG([^A-Za-z]|$)"]',
]

def polygon_string():
    gj = json.loads(AREA.read_text(encoding="utf-8"))
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    return " ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in ring)   # Overpass wants "lat lon lat lon ..."

def haversine_m(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def main():
    poly = polygon_string()
    body = "\n".join(f'  nwr{f}(poly:"{poly}");' for f in TAG_FILTERS)
    query = f"[out:json][timeout:120];\n(\n{body}\n);\nout center tags;"
    (ROOT / "sql").mkdir(exist_ok=True)
    (ROOT / "analysis" / "overpass_registration_query.txt").write_text(query, encoding="utf-8")

    for url in MIRRORS * 2:
        r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=180)
        if r.status_code == 200:
            break
        print(f"{url}: HTTP {r.status_code}, retrying", file=sys.stderr)
        time.sleep(15)
    r.raise_for_status()
    els = r.json()["elements"]

    pts, dropped = [], []
    for e in els:
        lat, lon = (e["lat"], e["lon"]) if "lat" in e else (e["center"]["lat"], e["center"]["lon"])
        t = e.get("tags", {})
        row = {"id": f'{e["type"]}/{e["id"]}', "lat": lat, "lon": lon, "name": t.get("name"),
               "tourism": t.get("tourism"), "building": t.get("building"), "amenity": t.get("amenity")}
        # The name regex also catches streets called "... Hostel Road" and a "hostel mess" canteen.
        # Those are not places to stay, so they are dropped here (the cleaning step of Phase 1 does the same).
        if "highway" in t or t.get("amenity") in ("fast_food", "restaurant", "cafe"):
            dropped.append(row)
            continue
        pts.append(row)

    def norm(name):   # "Boys Hostel - NO 9" and "Boys Hostel No,9" are the same building
        return "".join(ch for ch in (name or "").lower() if ch.isalnum())

    kept = []
    for p in pts:
        if not any(p["name"] and norm(p["name"]) == norm(k["name"]) and haversine_m((p["lat"], p["lon"]), (k["lat"], k["lon"])) < 30 for k in kept):
            kept.append(p)

    print(f"raw elements: {len(els)}   dropped (roads / canteens): {len(dropped)}   after removing duplicates: {len(kept)}")
    for d in dropped:
        print(f"   dropped {d['id']:18s} {d['name']}")
    print(f"named: {sum(1 for p in kept if p['name'])}   unnamed: {sum(1 for p in kept if not p['name'])}")
    print("\nby tag:")
    for key in ("tourism", "building", "amenity"):
        vals = {}
        for p in kept:
            if p[key]:
                vals[p[key]] = vals.get(p[key], 0) + 1
        print(f"  {key}: {vals}")
    print("\nfeatures:")
    for p in sorted(kept, key=lambda x: (x["name"] or "~")):
        print(f"  {p['id']:18s} {p['lat']:.5f},{p['lon']:.5f}  {p['name'] or '(no name)'}")
    print("\nThe exact query is saved in analysis/overpass_registration_query.txt (paste into overpass-turbo.eu).")

if __name__ == "__main__":
    main()
