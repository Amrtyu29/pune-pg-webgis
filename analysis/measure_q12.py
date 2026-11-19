"""Q12: on the PUBLIC GitHub Pages site, open the map at zoom 14 with cache disabled and record the
PMTiles requests: the Range request header, the response status (206 Partial Content) and the KB
transferred for the whole view, plus the totals for every request type on the page.

    ..\\webgis\\.venv\\Scripts\\python.exe analysis\\measure_q12.py [url]
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "https://amrtyu29.github.io/pune-pg-webgis/"
CENTER = [73.829, 18.552]
ZOOM = 14

rows = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})

    def on_response(resp):
        req = resp.request
        try:
            size = len(resp.body())
        except Exception:
            size = 0
        rows.append({"url": resp.url, "status": resp.status, "range": req.headers.get("range"),
                     "content_range": resp.headers.get("content-range"), "bytes": size,
                     "type": req.resource_type})
    page.on("response", on_response)
    page.goto(URL, wait_until="load")
    page.wait_for_function("window.map && map.loaded()", timeout=90000)
    page.evaluate(f"map.jumpTo({{center: {CENTER}, zoom: {ZOOM}}})")
    page.wait_for_timeout(1500)
    for _ in range(60):
        page.wait_for_timeout(500)
        if page.evaluate("map.areTilesLoaded() && map.loaded()"):
            break
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ROOT / "docs" / "screenshots" / "q12_pages_zoom14.png"))
    browser.close()

pm = [r for r in rows if r["url"].endswith(".pmtiles")]
other = [r for r in rows if not r["url"].endswith(".pmtiles")]
print(f"page: {URL}  zoom {ZOOM}")
print(f"PMTiles requests: {len(pm)}, {sum(r['bytes'] for r in pm)/1024:.1f} KB; statuses {sorted({r['status'] for r in pm})}")
for r in pm[:5]:
    print(f"  GET {r['url'].split('/')[-1]}  Range: {r['range']}  ->  {r['status']}  Content-Range: {r['content_range']}  ({r['bytes']} bytes)")
by_type = {}
for r in other:
    k = r["type"]
    by_type.setdefault(k, [0, 0])
    by_type[k][0] += 1
    by_type[k][1] += r["bytes"]
print("other requests by type (count, KB):", {k: (v[0], round(v[1] / 1024, 1)) for k, v in by_type.items()})
osm = [r for r in other if "tile.openstreetmap.org" in r["url"]]
print(f"OSM basemap tiles: {len(osm)}, {sum(r['bytes'] for r in osm)/1024:.1f} KB")
print(f"TOTAL for the view: {len(rows)} requests, {sum(r['bytes'] for r in rows)/1024:.1f} KB")
(ROOT / "docs" / "outputs" / "q12_pages_requests.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("saved docs/outputs/q12_pages_requests.json and docs/screenshots/q12_pages_zoom14.png")
