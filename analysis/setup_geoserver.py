"""Phase 2: publish the PostGIS layers and the DEM through GeoServer, using its REST API so the
whole setup is repeatable (and can be re-done live at the viva).

    .venv\\Scripts\\python.exe analysis\\setup_geoserver.py

What it creates (all idempotent: existing items are left alone or updated):
  workspace  punepg
  datastore  punepg:postgis      -> PostGIS over the Compose network (host "db", port 5432, not the host port!)
  layers     punepg:area, punepg:services, punepg:buildings   (WMS + WFS)
  style      punepg:services     <- sld/services.sld, set as default style of the services layer
  coverage   punepg:dem          <- /opt/dem/dem_prabhag11.tif (mounted read-only by docker-compose.yml) (WMS + WCS)
Credentials come from .env; nothing is printed."""
import sys, time
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from dbconf import read_env

ROOT = Path(__file__).resolve().parents[1]
env = read_env()
GS = f"http://localhost:{env.get('GEOSERVER_PORT', '8080')}/geoserver"
REST = GS + "/rest"
AUTH = HTTPBasicAuth(env["GEOSERVER_ADMIN_USER"], env["GEOSERVER_ADMIN_PASSWORD"])
WS = "punepg"
STORE = "postgis"
JSON = {"Content-Type": "application/json", "Accept": "application/json"}


def exists(path):
    return requests.get(REST + path, auth=AUTH, headers=JSON, timeout=60).status_code == 200


def post(path, payload, **kw):
    r = requests.post(REST + path, json=payload, auth=AUTH, headers=JSON, timeout=120, **kw)
    if r.status_code not in (200, 201):
        sys.exit(f"POST {path} -> {r.status_code}: {r.text[:400]}")
    return r


def put(path, data=None, json=None, content_type=None):
    headers = dict(JSON)
    if content_type:
        headers["Content-Type"] = content_type
    r = requests.put(REST + path, data=data, json=json, auth=AUTH, headers=headers, timeout=120)
    if r.status_code not in (200, 201):
        sys.exit(f"PUT {path} -> {r.status_code}: {r.text[:400]}")
    return r


# 0. wait for GeoServer
for _ in range(30):
    try:
        if requests.get(REST + "/about/version.json", auth=AUTH, timeout=10).status_code == 200:
            break
    except requests.RequestException:
        pass
    time.sleep(5)
else:
    sys.exit("GeoServer is not answering on " + GS)

# 1. workspace
if not exists(f"/workspaces/{WS}.json"):
    post("/workspaces", {"workspace": {"name": WS}})
    print("created workspace", WS)
else:
    print("workspace exists", WS)

# 2. PostGIS datastore. Inside the Compose network GeoServer reaches the database as host "db" on 5432.
if not exists(f"/workspaces/{WS}/datastores/{STORE}.json"):
    post(f"/workspaces/{WS}/datastores", {"dataStore": {
        "name": STORE, "type": "PostGIS", "enabled": True,
        "connectionParameters": {"entry": [
            {"@key": "dbtype", "$": "postgis"},
            {"@key": "host", "$": "db"},
            {"@key": "port", "$": "5432"},
            {"@key": "database", "$": env["POSTGRES_DB"]},
            {"@key": "schema", "$": "public"},
            {"@key": "user", "$": env["POSTGRES_USER"]},
            {"@key": "passwd", "$": env["POSTGRES_PASSWORD"]},
            {"@key": "Expose primary keys", "$": "true"},
            {"@key": "validate connections", "$": "true"},
            {"@key": "max connections", "$": "10"},
        ]}}})
    print("created datastore", STORE)
else:
    print("datastore exists", STORE)

# 3. feature types (layers). Published from the gs_* VIEWS (sql/05_geoserver_views.sql), which expose only the
#    EPSG:4326 geometry: with both geom and geom_utm visible, GeoServer mixed degrees and metres in the bounding box.
for table, title in [("area", "Prabhag 11 study area"), ("services", "PGs and hostels (OSM)"), ("buildings", "Building footprints (OSM)")]:
    path = f"/workspaces/{WS}/datastores/{STORE}/featuretypes/{table}.json"
    if exists(path):
        current = requests.get(REST + path, auth=AUTH, headers=JSON, timeout=60).json()["featureType"]
        if current.get("nativeName") == f"gs_{table}":
            print("layer exists", table)
            continue
        requests.delete(REST + path, params={"recurse": "true"}, auth=AUTH, timeout=60)   # re-publish from the view
        print("removed old layer", table)
    post(f"/workspaces/{WS}/datastores/{STORE}/featuretypes", {"featureType": {
        "name": table, "nativeName": f"gs_{table}", "title": title, "srs": "EPSG:4326", "enabled": True,
        "projectionPolicy": "FORCE_DECLARED"}})
    print("published layer", table, "from view gs_" + table)

# 4. style from sld/services.sld, attached to the services layer
sld = (ROOT / "sld" / "services.sld").read_text(encoding="utf-8")
if not exists(f"/workspaces/{WS}/styles/services.json"):
    r = requests.post(REST + f"/workspaces/{WS}/styles", data=sld.encode("utf-8"), auth=AUTH,
                      headers={"Content-Type": "application/vnd.ogc.sld+xml"}, params={"name": "services"}, timeout=120)
    if r.status_code not in (200, 201):
        sys.exit(f"style upload -> {r.status_code}: {r.text[:400]}")
    print("uploaded style services")
else:
    put(f"/workspaces/{WS}/styles/services", data=sld.encode("utf-8"), content_type="application/vnd.ogc.sld+xml")
    print("updated style services")
put(f"/layers/{WS}:services", json={"layer": {"defaultStyle": {"name": f"{WS}:services"}}})
print("services layer now uses style punepg:services")

# 5. DEM coverage store from the file mounted at /opt/dem inside the GeoServer container
if not exists(f"/workspaces/{WS}/coveragestores/dem.json"):
    post(f"/workspaces/{WS}/coveragestores", {"coverageStore": {
        "name": "dem", "type": "GeoTIFF", "enabled": True, "workspace": {"name": WS},
        "url": "file:///opt/dem/dem_prabhag11.tif"}})
    print("created coverage store dem")
else:
    print("coverage store exists dem")
if not exists(f"/workspaces/{WS}/coveragestores/dem/coverages/dem.json"):
    post(f"/workspaces/{WS}/coveragestores/dem/coverages", {"coverage": {
        "name": "dem", "nativeName": "dem_prabhag11", "title": "Copernicus GLO-30 DEM, Prabhag 11 + 2 km (m)",
        "srs": "EPSG:4326", "enabled": True}})
    print("published coverage dem (WMS + WCS)")
else:
    print("coverage exists dem")

# 6. summary
layers = requests.get(REST + f"/workspaces/{WS}/layers.json", auth=AUTH, headers=JSON, timeout=60).json()
names = [l["name"] for l in layers.get("layers", {}).get("layer", [])]
print("layers in workspace", WS, ":", names)
print("WMS GetCapabilities:", f"{GS}/{WS}/wms?service=WMS&version=1.3.0&request=GetCapabilities")
print("Layer preview:      ", f"{GS}/web/wicket/bookmarkable/org.geoserver.web.demo.MapPreviewPage")
