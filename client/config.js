// Where the map gets its data from.  Two modes, picked by the page's hostname:
//   "server": the Compose / kind stack on this laptop (GeoServer WMS/WFS, pg_tileserv MVT, pg_featureserv OGC API)
//   "static": the public GitHub Pages copy, where everything comes from ONE PMTiles file + small GeoJSON files
//             (no server runs; MapLibre reads tiles from the file with HTTP Range requests).
(function () {
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  const gs = "http://localhost:8080/geoserver/punepg";     // GeoServer workspace "punepg"
  const tiles = "http://localhost:7800";                   // pg_tileserv
  const feats = "http://localhost:9000";                   // pg_featureserv

  window.CONFIG = isLocal ? {
    mode: "server",
    wms: gs + "/wms",
    wfs: gs + "/wfs",
    hexTiles: (res) => `${tiles}/public.hex_r${res}/{z}/{x}/{y}.pbf`,
    hexSourceLayer: (res) => `public.hex_r${res}`,
    buildingsTiles: `${tiles}/public.buildings/{z}/{x}/{y}.pbf`,
    buildingsSourceLayer: "public.buildings",
    services: `${feats}/collections/public.services/items.json?limit=1000`,
    isochrones: `${feats}/collections/public.isochrones_15min/items.json?limit=1000`,
    buffers: `${feats}/collections/public.buffers_1200m/items.json?limit=1000`,
    area: `${feats}/collections/public.area/items.json`,
    // Q9 (b): all buildings as a single WFS GeoJSON request
    buildingsWfs: gs + "/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=punepg:buildings&outputFormat=application/json&srsName=EPSG:4326",
  } : {
    mode: "static",
    pmtiles: "data/punepg.pmtiles",                        // built by tippecanoe + pmtiles in the GitHub Action
    hexSourceLayer: (res) => `hex_r${res}`,
    buildingsSourceLayer: "buildings",
    services: "data/services.geojson",
    isochrones: "data/isochrones_15min.geojson",
    buffers: "data/buffers_1200m.geojson",
    area: "data/area.geojson",
  };

  window.CONFIG.center = [73.829, 18.557];                 // Prabhag 11 centroid
  window.CONFIG.zoom = 14;
})();
