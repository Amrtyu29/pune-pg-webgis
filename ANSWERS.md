# ANSWERS

**Area:** Prabhag 11 "Bopodi – Savitribai Phule Pune University", Pune Municipal Corporation (2022 delimitation), about 7.1 km², urban city ward.
**Service type:** other — PGs and hostels. OSM tags counted: `tourism=hostel`, `tourism=guest_house`, `building=dormitory`, `amenity=dormitory`, plus any feature whose `name` contains *PG*, *Paying Guest* or *Hostel* (roads and canteens that merely carry "hostel" in the name are removed in cleaning).
**UTM zone:** 43N, EPSG:32643 (area centre 18.557° N, 73.829° E; zone = floor((73.829 + 180) / 6) + 1 = 43).
**Walking threshold:** 15 minutes = 1,200 m at 4.8 km/h (urban ward). Sensitivity run at 3.6 km/h in Q8.
**Earlier project (baseline for Q3, Q6, Q9):** PuneStay, https://github.com/Amrtyu29/punestay — straight-line search with `ST_DWithin(geom::geography, …)` on a FastAPI + PostGIS backend, Leaflet client loading one GeoJSON per request.

Every answer below gives the exact SQL or URL, the raw output (or its key lines), screenshots where asked (relative links into `docs/screenshots/`), and a short explanation.

---

## Setup checkpoint

_Screenshot of `docker compose ps` with four healthy containers and the GeoServer admin page: `docs/screenshots/setup_compose_ps.png`, `docs/screenshots/setup_geoserver_admin.png`._

## Phase 1 — From API data to your own database

### Q1. One area, four areas
_pending_

### Q2. Indexes and query plans
_pending_

### Q3. Data quality vs the earlier source
_pending_

## Phase 2 — Publish your own OGC services

### Q4. The axis-order trap
_pending_

### Q5. WFS with a filter, two formats
_pending_

## Phase 3 — Was the earlier "nearest" right?

### Q6. Straight line vs street network
_pending_

### Q7. Coverage and the MAUP
_pending_

### Q8. Who is the model for?
_pending_

## Phase 4 — Map client and performance

### Q9. Three ways to ship the same map
_pending_

## Phase 5 — Deploy it, for free

### Q10. Image size
_pending_

### Q11. Self-healing and state
_pending_

### Q12. Static vs server deployment
_pending_

## Bonus (if attempted)

### B1. Latency
### B2. Two engines, one question
### B3. Hull choice
