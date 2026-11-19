# Work plan (deadline not yet announced; planned finish 10 December 2026)

Effort target about 30 h over three weeks, small commits every working session.

| Dates | Phase | Deliverables | Evidence |
|---|---|---|---|
| Wed 19 – Fri 21 Nov | **Phase 0** | repo skeleton, Compose stack healthy, four study notes, Killercoda labs (2 scenarios, screenshots), class-sheet registration | setup checkpoint screenshots, `/study` |
| Fri 21 – Mon 24 Nov | **Phase 1** | `analysis/01_download_and_load.ipynb`: OSMnx services + buildings + walking network (area + 2 km), cleaning, PostGIS load in 4326 + UTM 43N; `sql/` scripts | Q1, Q2, Q3 |
| Tue 25 – Wed 26 Nov | **Phase 2** | GeoServer workspace, PostGIS store, layers; DEM clipped and published (WMS + WCS); rule-based SLD | Q4, Q5 |
| Thu 27 Nov – Sun 30 Nov | **Phase 3** | `analysis/02_isochrones_h3.ipynb`: isochrones vs buffers, H3 res 8 and 9, WorldPop population, 30 random points, 3.6 km/h re-run; hex tables back in PostGIS | Q6, Q7, Q8 |
| Mon 1 – Wed 3 Dec | **Phase 4** | MapLibre client: OSM basemap, DEM WMS, hex vector tiles (data-driven colours), service pop-ups (pg_featureserv), layer switcher, legend, WFS-GeoJSON buildings toggle; DevTools measurements | Q9 |
| Thu 4 – Sun 7 Dec | **Phase 5** | multi-stage Dockerfile, tippecanoe + PMTiles, GitHub Actions to Pages, public URL in README; kind cluster with StatefulSet/PVC/Secret/Deployment/Services | Q10, Q11, Q12 |
| Mon 8 – Wed 10 Dec | **Buffer / bonus** | README polish, debugging log, viva rehearsal; pgRouting isochrone API only if everything else is green | B1–B3 (optional) |

Rules I follow: real data only; nothing in `.env` is committed; every file under 100 MB; every number in
ANSWERS.md can be reproduced live from a script or URL in this repository.
