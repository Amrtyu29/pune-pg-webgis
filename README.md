# Pune PG & hostel access — a Web GIS for Prabhag 11 (Bopodi – Savitribai Phule Pune University)

**Public map:** **https://amrtyu29.github.io/pune-pg-webgis/** (serverless: GitHub Pages + one PMTiles file, deployed by
[GitHub Actions](https://github.com/Amrtyu29/pune-pg-webgis/actions/workflows/deploy-pages.yml) on every push)

WebGIS assignment "From Nearby Services to a Deployed Map", M.Sc. Data Science and Spatial Analytics,
Symbiosis Institute of Geoinformatics. Guide: Dr. Veena Parihar. Student: Aarshad Rathod.

This repository rebuilds my earlier nearby-services project **PuneStay**
(https://github.com/Amrtyu29/punestay, live at https://punestay.onrender.com) as a provider-and-analyst
Web GIS. The planning question: **which residents of Prabhag 11 cannot reach a PG or hostel on foot
within 15 minutes, and why?**

| Registration item | Value |
|---|---|
| Area | Prabhag 11 "Bopodi – Savitribai Phule Pune University", Pune Municipal Corporation (2022 delimitation), 7.1 km² |
| Area type | city ward (urban), walking threshold **15 min = 1.2 km at 4.8 km/h** |
| Service type | other: **PGs and hostels** (OSM `tourism=hostel`, `tourism=guest_house`, `building=dormitory`, `amenity=dormitory`, and names containing *PG / Paying Guest / Hostel*) |
| OSM feature count | see `ANSWERS.md` (cleaned count from `analysis/check_feature_count.py`) |
| UTM zone | 43N, **EPSG:32643** (centre 18.557° N, 73.829° E) |
| Earlier project | https://github.com/Amrtyu29/punestay |

## Repository layout

```
README.md            this file: public URL, setup, sources, debugging log
ANSWERS.md           Q1–Q12 (+ bonus) with evidence
docker-compose.yml   PostGIS, GeoServer, pg_tileserv, pg_featureserv on one network
.env.example         variable names only (copy to .env, which is git-ignored)
study/               four one-page study notes with diagrams + lab proof screenshots
sql/                 every SQL script run against PostGIS
sld/                 GeoServer styles
analysis/            notebooks and scripts for Phases 1 and 3
client/              MapLibre GL JS app + Dockerfile
k8s/                 Kubernetes manifests for kind
.github/workflows/   GitHub Actions deployment to GitHub Pages
data/area/           the study-area polygon (small, committed); raw downloads are git-ignored
docs/screenshots/    evidence screenshots linked from ANSWERS.md
```

## Setup (Windows laptop, 16 GB RAM)

1. **Docker Desktop** with the WSL 2 backend (if the engine says "WSL update required", run `wsl --update` and restart Docker Desktop).
2. Copy `.env.example` to `.env` and fill in a database user, password, database name and a GeoServer admin password.
3. Start the stack and wait until all four containers are `healthy` (GeoServer needs about a minute):

   ```powershell
   docker compose up -d
   docker compose ps
   ```

   | Service | URL on the host |
   |---|---|
   | PostGIS | `localhost:5434` (container port 5432) |
   | GeoServer | http://localhost:8080/geoserver |
   | pg_tileserv | http://localhost:7800 |
   | pg_featureserv | http://localhost:9000 |

4. **Python 3.12** virtual environment for the notebooks:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r analysis\requirements.txt
   ```

5. **Phase 1 – data.** Run `analysis/01_download_and_load.ipynb` top to bottom (Jupyter, kernel = the `.venv`). It downloads OSM data
   with OSMnx (cached in `data/raw/`), cleans it and loads `area`, `services`, `buildings`, `walk_nodes`, `walk_edges` into PostGIS, then
   runs `sql/01_utm_copies.sql`. Evidence SQL: `.venv\Scripts\python.exe analysis\run_sql.py sql\02_q1_area_four_ways.sql` (and 03, 04).
6. **Phase 2 – OGC services.** `analysis\prepare_dem.py` (clips the Copernicus DEM; the result is already committed), then
   `analysis\run_sql.py sql\05_geoserver_views.sql` and `analysis\setup_geoserver.py` (REST: workspace, store, layers, SLD, DEM coverage).
   Q4/Q5 evidence: `analysis\evidence_q4_q5.py`.
7. **Phase 3 – analysis.** `analysis\prepare_worldpop.py` (downloads the 531 MB WorldPop India raster once, clip already committed), then run
   `analysis/02_isochrones_h3.ipynb` top to bottom. It writes `hex_r8`, `hex_r9`, `isochrones_15min`, `buffers_1200m`, `q6_random_points`,
   `worldpop_pixels` back to PostGIS; pg_tileserv and pg_featureserv pick the new tables up automatically.
8. **Phase 4 – client.** `powershell -ExecutionPolicy Bypass -File client\fetch-vendor.ps1` once (MapLibre + PMTiles bundles), then
   `.venv\Scripts\python.exe -m http.server 8088 --directory client` → http://localhost:8088 (the page detects `localhost` and uses the
   Compose services). Q9 numbers: `analysis\measure_q9.py` (needs `pip install playwright && playwright install chromium`).
9. **Phase 5A – public site.** `analysis\export_static.py` exports the layers to `client/data/`; every push to `main` runs
   `.github/workflows/deploy-pages.yml` (tippecanoe → `punepg.pmtiles` → GitHub Pages). Q12 numbers: `analysis\measure_q12.py`.
10. **Phase 5B – kind.** `powershell -ExecutionPolicy Bypass -File k8s\deploy.ps1` (cluster, image, Secret from `.env`, manifests), then
    `kubectl -n punepg port-forward svc/client 8089:80` → http://localhost:8089. Q11 experiment: `k8s\q11_selfheal.ps1 -Label pvc|emptydir`.

## Sources and citations

* **Study-area polygon:** PMC "Final Prabhag Rachna 2022" ward maps, digitised by SeerMaps Technologies for
  Nikhil VJ, published under the MIT licence at https://github.com/answerquest/pune-2022-wards (OpenStreetMap
  has no PMC ward boundaries, so this official-map tracing is used instead of an OSM admin boundary).
* **OpenStreetMap** data © OpenStreetMap contributors, ODbL, downloaded with OSMnx (Boeing, 2017) and checked with the Overpass API.
* **Population:** WorldPop, India 2020 constrained 100 m (`ind_ppp_2020_constrained.tif`), CC BY 4.0, DOI 10.5258/SOTON/WP00684.
* **Elevation:** Copernicus DEM GLO-30 (ESA / Airbus, 30 m), tile `Copernicus_DSM_COG_10_N18_00_E073_00_DEM` from the
  AWS Open Data bucket `copernicus-dem-30m`, clipped to the ward + 2 km by `analysis/prepare_dem.py` into
  `data/dem/dem_prabhag11.tif` (166 KB, committed). Chosen over SRTM because it needs no account or API key.
* **Software:** PostgreSQL 16 + PostGIS 3.5 (`postgis/postgis`), GeoServer 2.27 (`docker.osgeo.org/geoserver`), pg_tileserv and pg_featureserv (CrunchyData, `pramsey/*` images), OSMnx, GeoPandas, h3-py, MapLibre GL JS, tippecanoe, PMTiles, kind, kubectl.
* **Tutorials and references used:** OGC WMS 1.1.1 / 1.3.0 and WFS 2.0 specifications, PostGIS manual (spatial indexes, geography), GeoServer user manual (SLD cookbook), H3 docs, OSMnx docs, Docker "Get started" guide, Kubernetes Basics tutorial, Protomaps PMTiles docs.
* AI assistance: Claude (Anthropic) was used as a coding and study partner; every line was reviewed and can be explained and modified at the viva.

## Debugging log

* **2026-11-19 — Docker engine would not start.** `docker info` hung and Docker Desktop stayed on "starting".
  `%LOCALAPPDATA%\Docker\log\host\com.docker.backend.exe.log` showed
  `engine linux/wsl failed to start: checking preconditions: WSL update required`.
  Cause: WSL 2.0.14 was older than Docker Desktop 4.95 requires. Fix: `wsl --update` (to 3.0.5), restart Docker Desktop;
  the engine came up in 44 s.
* **2026-11-19 — pg_tileserv kept restarting.** `docker logs pg_tileserv` ended every few seconds with
  `level=fatal msg="ERROR: function postgis_full_version() does not exist (SQLSTATE 42883)"` although the image
  is `postgis/postgis`. Cause: my Compose file bind-mounted the whole `./sql/init` folder onto
  `/docker-entrypoint-initdb.d`, which *hides* the image's own `10_postgis.sh`, so the database was created
  without the PostGIS extension. Fix: mount my script as a single file inside that folder and add
  `CREATE EXTENSION postgis` to it; `docker compose down -v` to wipe the half-initialised volume, then `up -d`.
* **2026-11-19 — GeoServer bounding box mixed degrees and metres.** After publishing the `services` table, the WMS 1.3.0
  capabilities showed `<BoundingBox CRS="EPSG:4326" minx="18.51" miny="73.80" maxx="2053095.6" maxy="378856.2"/>` and the first
  Q4 GetMap requests returned near-empty images. Cause: the table has two geometry columns (`geom` in 4326 and `geom_utm` in 32643)
  and GeoServer computed the extent over both. Fix: `sql/05_geoserver_views.sql` creates `gs_area`, `gs_services`, `gs_buildings`
  views that expose only the 4326 geometry, and `analysis/setup_geoserver.py` publishes the views (it deletes and re-creates the layers).
* **2026-11-19 — OSMnx 2.x renamed its index columns.** My de-duplication step `drop_duplicates(["element_type","osmid"])` silently
  reduced 33 tag-based features to 1, because OSMnx 2 returns the index as `element` / `id`. The notebook printed
  "inside Prabhag 11: 12" instead of 19; the SQL list of services showed empty `element_type` / `osmid` for the survivor, which gave it away.
  Fix: rename the columns right after `reset_index()`.
* **2026-11-19 — Phase 3 notebook: `GeoSeries.distance(GeometryArray)` raises `TypeError`.** GeoPandas 1.2 only accepts an aligned
  GeoSeries there; element-wise distance between two plain geometry arrays is `shapely.distance(a, b)`.
* **2026-11-19 — WorldPop refuses HTTP range requests.** `rasterio.open("/vsicurl/…ind_ppp_2020_constrained.tif")` failed with
  `Range downloading not supported by this server!`, so the 531 MB national raster is downloaded once to `data/raw/` (git-ignored) and
  clipped locally; the 19 KB clip is committed.
* **2026-11-19 — No healthcheck possible for pg_tileserv / pg_featureserv with curl.** The `pramsey/*` images have
  no `curl` or `wget` (`which curl` exits 127), so `docker compose ps` could never report them healthy. Their
  `/bin/sh` is bash, so the healthcheck opens a raw TCP socket with bash's `/dev/tcp/127.0.0.1/7800` instead.
