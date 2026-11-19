"""Q9: three ways to ship the same buildings layer, measured like the DevTools Network tab (cache off).

For zoom 12, 14 and 16 and for each mode
  (a) tiled WMS PNG from GeoServer, (b) ONE WFS GeoJSON request, (c) MVT vector tiles from pg_tileserv,
a fresh headless-Chromium page (no cache) opens the local client at that zoom, ticks the layer's checkbox,
waits until MapLibre reports "idle", and records every network response belonging to that layer:
number of requests, kilobytes transferred (response body size), and seconds from the tick to idle.

    ..\\webgis\\.venv\\Scripts\\python.exe analysis\\measure_q9.py          (any Python with playwright + chromium)

Needs the Compose stack and the client on http://localhost:8088 (python -m http.server 8088 --directory client)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CLIENT = "http://localhost:8088/"
CENTER = [73.829, 18.552]
MODES = {  # checkbox group -> test that identifies this layer's requests (MapLibre may or may not %-encode the colon)
    "a) tiled WMS PNG (GeoServer)": ("bld-wms", lambda u: "GetMap" in u and "buildings" in u),
    "b) one WFS GeoJSON (GeoServer)": ("bld-wfs", lambda u: "GetFeature" in u and "buildings" in u),
    "c) MVT tiles (pg_tileserv)": ("bld-mvt", lambda u: "public.buildings/" in u),
}
ZOOMS = [12, 14, 16]
results = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for zoom in ZOOMS:
        for label, (group, needle) in MODES.items():
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            # cache disabled, like DevTools "Disable cache"
            cdp = ctx.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
            hits = []
            def on_response(resp, needle=needle, hits=hits):
                if needle(resp.url):
                    try:
                        body = len(resp.body())
                    except Exception:
                        body = 0
                    hits.append((resp.url, resp.status, body, time.perf_counter()))
            page.on("response", on_response)
            page.goto(CLIENT, wait_until="load")
            page.wait_for_function("window.map && map.loaded()", timeout=60000)
            page.evaluate(f"map.jumpTo({{center: {CENTER}, zoom: {zoom}}})")
            page.wait_for_function("map.loaded()", timeout=60000)
            time.sleep(0.5)
            hits.clear()
            t0 = time.perf_counter()
            page.evaluate(f"""() => {{ const cb = document.querySelector('input[data-group="{group}"]'); cb.checked = true; cb.dispatchEvent(new Event('change')); }}""")
            # wait for the layer to finish: MapLibre idle AND no new responses for 1.5 s (the WFS mode first
            # awaits one big fetch, so give it up to 60 s before the idle test starts)
            if group == "bld-wfs":
                page.wait_for_function("document.getElementById('stats').textContent.startsWith('WFS')", timeout=120000)
            page.wait_for_timeout(1500)
            last = len(hits)
            for _ in range(120):
                page.wait_for_timeout(500)
                idle = page.evaluate("map.loaded() && !map.areTilesLoaded ? true : map.areTilesLoaded()")
                if idle and len(hits) == last:
                    break
                last = len(hits)
            # "time to finish" = from ticking the box to the LAST response of this layer arriving
            elapsed = (max(h[3] for h in hits) - t0) if hits else 0.0
            kb = sum(h[2] for h in hits) / 1024
            results.append({"zoom": zoom, "mode": label, "requests": len(hits), "kb": round(kb, 1), "seconds": round(max(elapsed, 0), 2),
                            "statuses": sorted({h[1] for h in hits})})
            print(f"z{zoom}  {label:34s} requests={len(hits):4d}  KB={kb:9.1f}  time={max(elapsed,0):6.2f} s  statuses={sorted({h[1] for h in hits})}")
            ctx.close()
    browser.close()

out = ROOT / "docs" / "outputs" / "q9_measurements.json"
out.write_text(json.dumps(results, indent=2), encoding="utf-8")
print("saved", out.relative_to(ROOT).as_posix())
