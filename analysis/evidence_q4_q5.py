"""Phase 2 evidence: Q4 (WMS axis order) and Q5 (WFS 2.0 filter in two formats).
Run after setup_geoserver.py.  Writes the exact URLs, raw key lines and images to docs/.

    .venv\\Scripts\\python.exe analysis\\evidence_q4_q5.py

Q4: read the services layer's EPSG:4326 BoundingBox from WMS 1.3.0 GetCapabilities, then send the SAME four
    numbers as BBOX to WMS 1.1.1 (SRS=, lon/lat order) and WMS 1.3.0 (CRS=, lat/lon order for EPSG:4326).
Q5: WFS 2.0 GetFeature with a CQL filter "named services inside the ward", as GML 3.2 and as GeoJSON."""
import json, re, sys
from pathlib import Path
from urllib.parse import urlencode
import requests
import xml.etree.ElementTree as ET
from dbconf import read_env

ROOT = Path(__file__).resolve().parents[1]
env = read_env()
GS = f"http://localhost:{env.get('GEOSERVER_PORT', '8080')}/geoserver"
WS = "punepg"
OUT = ROOT / "docs" / "outputs"
SHOTS = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)
log = []


def say(s=""):
    print(s)
    log.append(s)


# ---------------------------------------------------------------- Q4
say("=== Q4. The axis-order trap ===")
cap_url = f"{GS}/{WS}/wms?service=WMS&version=1.3.0&request=GetCapabilities"
say("GetCapabilities 1.3.0: " + cap_url)
cap = requests.get(cap_url, timeout=120).text
(OUT / "q4_getcapabilities_130.xml").write_text(cap, encoding="utf-8")
ns = {"wms": "http://www.opengis.net/wms"}
root = ET.fromstring(cap)
layer = next(l for l in root.iter("{http://www.opengis.net/wms}Layer") if l.findtext("wms:Name", namespaces=ns) in ("services", f"{WS}:services"))
bb = next(b for b in layer.findall("wms:BoundingBox", ns) if b.get("CRS") == "EPSG:4326")
minx, miny, maxx, maxy = (bb.get(k) for k in ("minx", "miny", "maxx", "maxy"))
say(f'services layer BoundingBox in the 1.3.0 capabilities: <BoundingBox CRS="EPSG:4326" minx="{minx}" miny="{miny}" maxx="{maxx}" maxy="{maxy}"/>')
say("  (in WMS 1.3.0 + EPSG:4326, minx/maxx are LATITUDES and miny/maxy are LONGITUDES, because EPSG:4326 is defined lat,lon)")
bbox = f"{minx},{miny},{maxx},{maxy}"

common = dict(service="WMS", request="GetMap", layers=f"{WS}:services,{WS}:area", styles="", format="image/png",
              width=600, height=600, transparent="false", bgcolor="0xFFFFFF")
u111 = f"{GS}/{WS}/wms?" + urlencode({**common, "version": "1.1.1", "srs": "EPSG:4326", "bbox": bbox})
u130 = f"{GS}/{WS}/wms?" + urlencode({**common, "version": "1.3.0", "crs": "EPSG:4326", "bbox": bbox})
for tag, u in (("111", u111), ("130", u130)):
    r = requests.get(u, timeout=120)
    (SHOTS / f"q4_getmap_{tag}.png").write_bytes(r.content)
    say(f"GetMap {tag}: {u}")
    say(f"  -> HTTP {r.status_code}, {r.headers.get('Content-Type')}, {len(r.content)} bytes, saved docs/screenshots/q4_getmap_{tag}.png")

# same numbers, swapped for 1.1.1 so both requests draw the same map (the fix)
bbox_lonlat = f"{miny},{minx},{maxy},{maxx}"
u111_fix = f"{GS}/{WS}/wms?" + urlencode({**common, "version": "1.1.1", "srs": "EPSG:4326", "bbox": bbox_lonlat})
r = requests.get(u111_fix, timeout=120)
(SHOTS / "q4_getmap_111_lonlat.png").write_bytes(r.content)
say(f"GetMap 1.1.1 with the box rewritten as lon/lat ({bbox_lonlat}): {u111_fix}")
say(f"  -> {len(r.content)} bytes, saved docs/screenshots/q4_getmap_111_lonlat.png")

# ---------------------------------------------------------------- Q5
say()
say("=== Q5. WFS 2.0 with a filter, two formats ===")
cql = "name IS NOT NULL AND inside_area = true"
base = dict(service="WFS", version="2.0.0", request="GetFeature", typeNames=f"{WS}:services", CQL_FILTER=cql)
hits_url = f"{GS}/{WS}/wfs?" + urlencode({**base, "resultType": "hits"})
hits = requests.get(hits_url, timeout=120).text
m = re.search(r'numberMatched="(\d+)"', hits)
say("resultType=hits: " + hits_url)
say(f"  -> numberMatched={m.group(1) if m else '?'}")

gml_url = f"{GS}/{WS}/wfs?" + urlencode({**base, "outputFormat": "application/gml+xml; version=3.2"})
geojson_url = f"{GS}/{WS}/wfs?" + urlencode({**base, "outputFormat": "application/json"})
g = requests.get(gml_url, timeout=120)
j = requests.get(geojson_url, timeout=120)
(OUT / "q5_services_named.gml").write_bytes(g.content)
(OUT / "q5_services_named.geojson").write_bytes(j.content)
say("GML 3.2:  " + gml_url)
say(f"  -> {len(g.content)/1024:.1f} KB, numberMatched={re.search(r'numberMatched=\"(\\d+)\"', g.text).group(1)}")
pos = re.search(r"<gml:pos[^>]*>([^<]+)</gml:pos>", g.text)
say(f"  first point <gml:pos>: {pos.group(1) if pos else '?'}   (lat lon: EPSG:4326 axis order in GML 3.2)")
say("GeoJSON:  " + geojson_url)
fc = j.json()
first = fc["features"][0]["geometry"]["coordinates"]
say(f"  -> {len(j.content)/1024:.1f} KB, numberMatched={fc.get('numberMatched')}, numberReturned={fc.get('numberReturned')}")
say(f"  first point coordinates: {first}   (lon, lat: GeoJSON always uses x,y = longitude,latitude)")
say(f"  first feature name: {fc['features'][0]['properties'].get('name')}")

(OUT / "q4_q5_evidence.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
print("\nsaved docs/outputs/q4_q5_evidence.txt")
