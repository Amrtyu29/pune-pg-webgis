/* MapLibre GL JS client for the Prabhag 11 PG/hostel access map.
 * Layers: OSM raster basemap, DEM (WMS), H3 hexagons as vector tiles with data-driven colours,
 * isochrones and buffers, services with pop-ups, ward boundary, and three ways of loading buildings
 * (tiled WMS PNG, MVT, one WFS GeoJSON) for the Q9 performance test.
 * Bonus (server mode only): a click asks the pgRouting API for a live isochrone and the nearest services.
 * CONFIG (config.js) decides whether data comes from the local server stack or from a PMTiles file. */

const C = window.CONFIG;
document.getElementById("mode").textContent = C.mode === "server" ? "live: PostGIS · GeoServer · pg_tileserv · pg_featureserv · pgRouting API" : "static: GitHub Pages + PMTiles";

// --- colour scales -------------------------------------------------------------------------------
// Distance classes follow the walking thresholds: 900 m (15 min at 3.6 km/h), 1,200 m (15 min at 4.8 km/h).
const SCALES = {
  net_dist_m: { title: "Walking distance to nearest PG/hostel", unit: "m",
    stops: [[0, "#1a9850"], [600, "#91cf60"], [900, "#d9ef8b"], [1200, "#fee08b"], [1800, "#fc8d59"], [2400, "#d73027"]] },
  sl_dist_m:  { title: "Straight-line distance to nearest PG/hostel", unit: "m",
    stops: [[0, "#1a9850"], [600, "#91cf60"], [900, "#d9ef8b"], [1200, "#fee08b"], [1800, "#fc8d59"], [2400, "#d73027"]] },
  pop:        { title: "Population per cell (WorldPop 2020)", unit: "people",
    stops: [[0, "#f7fbff"], [50, "#deebf7"], [200, "#9ecae1"], [500, "#4292c6"], [1000, "#08519c"], [2000, "#08306b"]] },
};

// A MapLibre "step" expression: colour depends on the feature's attribute value (data-driven styling).
function stepExpr(attr) {
  const s = SCALES[attr].stops;
  const e = ["step", ["coalesce", ["to-number", ["get", attr]], 99999], s[0][1]];
  for (let i = 1; i < s.length; i++) e.push(s[i][0], s[i][1]);
  return e;
}

// --- map -------------------------------------------------------------------------------------------
if (C.mode === "static") {
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
}

const map = new maplibregl.Map({
  container: "map",
  center: C.center, zoom: C.zoom,
  style: {
    version: 8,
    sources: {
      osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256,
             attribution: "© OpenStreetMap contributors" },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  },
});
map.addControl(new maplibregl.NavigationControl(), "top-left");
map.addControl(new maplibregl.ScaleControl({ maxWidth: 150, unit: "metric" }), "bottom-left");

const GROUPS = {};      // group name -> [layer ids], for the layer switcher
function reg(group, id) { (GROUPS[group] = GROUPS[group] || []).push(id); }

map.on("load", async () => {
  // DEM as WMS from GeoServer (server mode only; the static site has no raster server)
  if (C.mode === "server") {
    map.addSource("dem", { type: "raster", tileSize: 256,
      tiles: [C.wms + "?service=WMS&version=1.3.0&request=GetMap&layers=punepg:dem&styles=&crs=EPSG:3857&bbox={bbox-epsg-3857}&width=256&height=256&format=image/png&transparent=true"] });
    map.addLayer({ id: "dem", type: "raster", source: "dem", paint: { "raster-opacity": 0.6 }, layout: { visibility: "none" } });
    reg("dem", "dem");

    // Q9 (a): buildings as tiled WMS PNG
    map.addSource("bld-wms", { type: "raster", tileSize: 256,
      tiles: [C.wms + "?service=WMS&version=1.3.0&request=GetMap&layers=punepg:buildings&styles=&crs=EPSG:3857&bbox={bbox-epsg-3857}&width=256&height=256&format=image/png&transparent=true"] });
    map.addLayer({ id: "bld-wms", type: "raster", source: "bld-wms", layout: { visibility: "none" } });
    reg("bld-wms", "bld-wms");
  }

  // H3 hexagons as vector tiles (MVT): pg_tileserv locally, PMTiles on GitHub Pages
  for (const res of [8, 9]) {
    const src = `hex${res}`;
    map.addSource(src, C.mode === "server"
      ? { type: "vector", tiles: [C.hexTiles(res)], minzoom: 10, maxzoom: 16 }
      : { type: "vector", url: "pmtiles://" + C.pmtiles });
    map.addLayer({ id: `${src}-fill`, type: "fill", source: src, "source-layer": C.hexSourceLayer(res),
      paint: { "fill-color": stepExpr("net_dist_m"), "fill-opacity": 0.55 }, layout: { visibility: res === 9 ? "visible" : "none" } });
    map.addLayer({ id: `${src}-line`, type: "line", source: src, "source-layer": C.hexSourceLayer(res),
      paint: { "line-color": "#fff", "line-width": 0.5 }, layout: { visibility: res === 9 ? "visible" : "none" } });
    reg("hex", `${src}-fill`); reg("hex", `${src}-line`);
    map.on("click", `${src}-fill`, (e) => {
      if (liveEnabled()) return;          // while the live tool is on, a click means "isochrone here", not "cell pop-up"
      const p = e.features[0].properties;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(
        `<b>H3 ${p.h3}</b> (res ${res})<br>walking distance: <b>${fmt(p.net_dist_m)} m</b><br>straight line: ${fmt(p.sl_dist_m)} m` +
        `<br>population: ${fmt(p.pop)}<br>within 15 min: ${p.covered_net_15 === true || p.covered_net_15 === "true" ? "yes" : "no"}`).addTo(map);
    });
  }

  // Q9 (c): buildings as MVT
  map.addSource("bld-mvt", C.mode === "server"
    ? { type: "vector", tiles: [C.buildingsTiles], minzoom: 12, maxzoom: 18 }
    : { type: "vector", url: "pmtiles://" + C.pmtiles });
  map.addLayer({ id: "bld-mvt", type: "fill", source: "bld-mvt", "source-layer": C.buildingsSourceLayer,
    paint: { "fill-color": "#7f7f7f", "fill-opacity": 0.5, "fill-outline-color": "#444" }, layout: { visibility: "none" } });
  reg("bld-mvt", "bld-mvt");

  // Q9 (b): buildings as ONE WFS GeoJSON request (loaded only when the box is ticked, so the Network tab shows it clearly)
  map.addSource("bld-wfs", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "bld-wfs", type: "fill", source: "bld-wfs", paint: { "fill-color": "#e7298a", "fill-opacity": 0.45 }, layout: { visibility: "none" } });
  reg("bld-wfs", "bld-wfs");

  // small GeoJSON layers: buffers, isochrones, ward, services (pg_featureserv locally, files on Pages)
  map.addSource("buf", { type: "geojson", data: C.buffers });
  map.addLayer({ id: "buf-fill", type: "fill", source: "buf", paint: { "fill-color": "#fdae6b", "fill-opacity": 0.25 }, layout: { visibility: "none" } });
  map.addLayer({ id: "buf-line", type: "line", source: "buf", paint: { "line-color": "#e6550d", "line-width": 1, "line-dasharray": [2, 2] }, layout: { visibility: "none" } });
  reg("buf", "buf-fill"); reg("buf", "buf-line");

  map.addSource("iso", { type: "geojson", data: C.isochrones });
  map.addLayer({ id: "iso-fill", type: "fill", source: "iso", paint: { "fill-color": "#3182bd", "fill-opacity": 0.18 } });
  map.addLayer({ id: "iso-line", type: "line", source: "iso", paint: { "line-color": "#08519c", "line-width": 1 } });
  reg("iso", "iso-fill"); reg("iso", "iso-line");

  map.addSource("area", { type: "geojson", data: C.area });
  map.addLayer({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#000", "line-width": 2.5 } });
  reg("area", "area-line");

  map.addSource("services", { type: "geojson", data: C.services });
  map.addLayer({ id: "services", type: "circle", source: "services",
    paint: { "circle-radius": ["case", ["==", ["get", "inside_area"], true], 7, 5],
             "circle-color": ["case", ["!", ["has", "name"]], "#ffffff", ["==", ["get", "service_type"], "pg"], "#e6550d", "#3182bd"],
             "circle-stroke-color": ["case", ["!", ["has", "name"]], "#555", "#fff"], "circle-stroke-width": 1.5 } });
  reg("services", "services");
  map.on("click", "services", (e) => {
    const p = e.features[0].properties;
    const [lng, lat] = e.features[0].geometry.coordinates;
    new maplibregl.Popup().setLngLat([lng, lat]).setHTML(
      `<b>${p.name || "(no name in OSM)"}</b><br>type: ${p.service_type}<br>OSM: <a href="https://www.openstreetmap.org/${p.element_type}/${p.osmid}" target="_blank">${p.element_type}/${p.osmid}</a>` +
      `<br>${p.inside_area === true || p.inside_area === "true" ? "inside Prabhag 11" : "in the 2 km margin"}<br>${lat.toFixed(5)}, ${lng.toFixed(5)}`).addTo(map);
  });
  map.on("mouseenter", "services", () => map.getCanvas().style.cursor = "pointer");
  map.on("mouseleave", "services", () => map.getCanvas().style.cursor = "");

  // Bonus: three empty GeoJSON sources that the live tool fills after each click
  // (the clicked point, the isochrone polygon from /isochrone, the k nearest services from /nearest)
  map.addSource("live-iso", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "live-iso-fill", type: "fill", source: "live-iso", paint: { "fill-color": "#d62728", "fill-opacity": 0.22 } });
  map.addLayer({ id: "live-iso-line", type: "line", source: "live-iso", paint: { "line-color": "#d62728", "line-width": 2 } });
  map.addSource("live-nearest", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "live-nearest", type: "circle", source: "live-nearest",
    paint: { "circle-radius": 11, "circle-color": "#ffffff", "circle-opacity": 0, "circle-stroke-color": "#d62728", "circle-stroke-width": 3 } });
  map.addSource("live-click", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "live-click", type: "circle", source: "live-click",
    paint: { "circle-radius": 6, "circle-color": "#d62728", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
  map.on("click", (e) => { if (!liveEnabled()) return; lastClick = e.lngLat; runLive(); });
  wireLive();

  wireControls();
  drawLegend("net_dist_m");
  try {
    const r = await fetch(C.services); const fc = await r.json();
    const inside = fc.features.filter(f => f.properties.inside_area === true || f.properties.inside_area === "true").length;
    document.getElementById("stats").textContent = `${fc.features.length} PGs/hostels loaded (${inside} inside the ward).`;
  } catch (e) { console.warn("services not loaded", e); }
});

function fmt(v) { const n = Number(v); return Number.isFinite(n) ? Math.round(n).toLocaleString("en-IN") : "no street access"; }

// --- Bonus: live walking isochrone from the FastAPI + pgRouting service ------------------------------------
const EMPTY = { type: "FeatureCollection", features: [] };
let lastClick = null;                                     // the last clicked lng/lat, so the slider can re-query it
function liveEnabled() { return !!C.api && document.getElementById("live-on").checked; }

function wireLive() {
  const on = document.getElementById("live-on"), slider = document.getElementById("minutes"),
        label = document.getElementById("minutes-val"), out = document.getElementById("live-out");
  if (!C.api) {                                           // static site (GitHub Pages): no server, so no live queries
    on.checked = false; on.disabled = true; slider.disabled = true;
    out.innerHTML = "The live isochrone needs the pgRouting API, which only runs in the local Compose stack " +
      "(<code>docker compose up -d</code>, then open http://localhost:8088). GitHub Pages serves static files only; " +
      "the blue 15-minute isochrones on this page were precomputed in Phase 3.";
    return;
  }
  slider.addEventListener("input", () => { label.textContent = slider.value; });   // live number while dragging
  slider.addEventListener("change", () => { if (lastClick) runLive(); });          // released: re-query the last click
  on.addEventListener("change", () => {
    if (!on.checked) { for (const s of ["live-iso", "live-nearest", "live-click"]) map.getSource(s).setData(EMPTY); out.textContent = "Live tool off."; }
    else out.textContent = "Click anywhere on the map.";
  });
}

async function runLive() {
  const minutes = Number(document.getElementById("minutes").value);
  const out = document.getElementById("live-out");
  const { lng, lat } = lastClick;
  out.textContent = `querying the API for ${minutes} min…`;
  const t0 = performance.now();
  try {
    // both requests at once; the browser waits for the slower one
    const [isoR, nearR] = await Promise.all([
      fetch(`${C.api}/isochrone?lon=${lng.toFixed(6)}&lat=${lat.toFixed(6)}&minutes=${minutes}`),
      fetch(`${C.api}/nearest?lon=${lng.toFixed(6)}&lat=${lat.toFixed(6)}&k=5`),
    ]);
    if (!isoR.ok) throw new Error(`${isoR.status} ${(await isoR.json()).detail || ""}`);
    if (!nearR.ok) throw new Error(`${nearR.status} ${(await nearR.json()).detail || ""}`);
    const iso = await isoR.json(), near = await nearR.json();
    const roundTrip = Math.round(performance.now() - t0);
    map.getSource("live-iso").setData(iso);
    map.getSource("live-nearest").setData(near);
    map.getSource("live-click").setData({ type: "Feature", geometry: { type: "Point", coordinates: [lng, lat] }, properties: {} });
    const p = iso.properties;
    const list = near.features.map(f => {
      const q = f.properties, far = q.minutes > minutes;
      return `<li class="${far ? "far" : ""}"><b>${q.name || "(no name in OSM)"}</b> · ${q.minutes} min (${fmt(q.walk_m)} m)${far ? " · beyond the isochrone" : ""}</li>`;
    }).join("");
    out.innerHTML = `<b>${minutes} min on foot</b> = ${fmt(p.distance_m)} m along the streets from the nearest node (${fmt(p.snap_m)} m from the click). ` +
      `Reached <b>${p.reached_nodes}</b> nodes; concave hull ${(p.area_m2 / 1e6).toFixed(2)} km².<br>` +
      `Server: database ${isoR.headers.get("X-DB-Time-ms")} ms, API total ${isoR.headers.get("X-Total-Time-ms")} ms · ` +
      `/nearest ${nearR.headers.get("X-Total-Time-ms")} ms · browser round trip for both: <b>${roundTrip} ms</b>.` +
      `<div style="margin-top:4px"><b>Nearest 5 by walking time</b> (click→street + path + street→door):</div><ol>${list}</ol>`;
  } catch (err) {
    out.textContent = `API error: ${err.message}. Is the api container up? (docker compose ps)`;
  }
}

// --- controls ---------------------------------------------------------------------------------------
function setGroup(group, on) {
  for (const id of GROUPS[group] || []) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}
function wireControls() {
  document.querySelectorAll("#panel input[type=checkbox][data-group]").forEach(cb => {
    cb.addEventListener("change", async () => {
      const g = cb.dataset.group;
      if (g === "hex") { setHexRes(); return; }
      if (g === "bld-wfs" && cb.checked && C.buildingsWfs) {
        console.time("WFS GeoJSON buildings");
        const r = await fetch(C.buildingsWfs); const fc = await r.json();   // ONE request for every footprint
        console.timeEnd("WFS GeoJSON buildings");
        map.getSource("bld-wfs").setData(fc);
        document.getElementById("stats").textContent = `WFS GeoJSON: ${fc.features.length.toLocaleString()} buildings in one response.`;
      }
      setGroup(g, cb.checked);
    });
  });
  document.getElementById("hexres").addEventListener("change", setHexRes);
  document.getElementById("hexattr").addEventListener("change", () => {
    const attr = document.getElementById("hexattr").value;
    for (const res of [8, 9]) map.setPaintProperty(`hex${res}-fill`, "fill-color", stepExpr(attr));
    drawLegend(attr);
  });
}
function setHexRes() {
  const on = document.querySelector('input[data-group="hex"]').checked;
  const res = document.getElementById("hexres").value;
  for (const r of [8, 9]) for (const id of [`hex${r}-fill`, `hex${r}-line`])
    map.setLayoutProperty(id, "visibility", on && String(r) === res ? "visible" : "none");
}
function drawLegend(attr) {
  const s = SCALES[attr];
  let html = `<div class="small"><b>${s.title}</b></div>`;
  s.stops.forEach(([v, c], i) => {
    const next = s.stops[i + 1];
    html += `<div class="row"><span class="sw" style="background:${c}"></span>${v.toLocaleString()}${next ? " – " + next[0].toLocaleString() : "+"} ${s.unit}</div>`;
  });
  html += `<div class="row" style="margin-top:6px"><span class="dot" style="background:#3182bd"></span>hostel / guest house</div>
           <div class="row"><span class="dot" style="background:#e6550d"></span>PG (paying guest)</div>
           <div class="row"><span class="dot" style="background:#fff"></span>no name in OSM</div>
           <div class="row"><span class="sw" style="background:#3182bd33;border-color:#08519c"></span>15-min walking isochrone</div>
           <div class="row"><span class="sw" style="background:#fdae6b55;border-color:#e6550d;border-style:dashed"></span>1,200 m buffer</div>
           <div class="row"><span class="sw" style="background:#d6272838;border-color:#d62728"></span>live isochrone from your click (pgRouting)</div>`;
  document.getElementById("legend").innerHTML = html;
}
