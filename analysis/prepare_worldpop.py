"""Phase 3 input: population. Clips the WorldPop India 2020 "constrained" 100 m population-count
raster to the study area plus a 2 km margin and writes data/worldpop/worldpop_prabhag11.tif.

    .venv\\Scripts\\python.exe analysis\\prepare_worldpop.py

Source: WorldPop (www.worldpop.org, School of Geography and Environmental Science, University of
Southampton), "India 100 m population, constrained, 2020", file ind_ppp_2020_constrained.tif,
DOI 10.5258/SOTON/WP00684, licence CC BY 4.0.  Each pixel holds an estimated number of people.
The national file is 531 MB and data.worldpop.org does NOT support HTTP range requests (GDAL says
"Range downloading not supported by this server!"), so it is downloaded once into data/raw/ (git-ignored)
and clipped from there.  Only the 100-odd KB clip is committed."""
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.mask import mask

ROOT = Path(__file__).resolve().parents[1]
URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/IND/"
       "ind_ppp_2020_constrained.tif")
OUT = ROOT / "data" / "worldpop" / "worldpop_prabhag11.tif"
UTM = 32643

area = gpd.read_file(ROOT / "data" / "area" / "prabhag11.geojson").set_crs(4326, allow_override=True)
clip_poly = area.to_crs(UTM).buffer(2000).to_crs(4326).iloc[0]

RAW = ROOT / "data" / "raw" / "ind_ppp_2020_constrained.tif"
if not RAW.exists():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    print("downloading", URL, "(531 MB, once) ...")
    with requests.get(URL, stream=True, timeout=120, headers={"User-Agent": "pune-pg-webgis/0.1"}) as r:
        r.raise_for_status()
        done = 0
        with open(RAW, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if done % (50 << 20) < (1 << 20):
                    print(f"  {done / 1e6:.0f} MB", flush=True)
    print("downloaded", RAW.stat().st_size / 1e6, "MB")

with rasterio.open(RAW) as src:
    print("source:", src.crs, "res", src.res, "size", src.width, "x", src.height, "nodata", src.nodata, "dtype", src.dtypes[0])
    data, transform = mask(src, [clip_poly.__geo_interface__], crop=True, nodata=src.nodata)
    profile = src.profile.copy()
    nodata = src.nodata

profile.update(height=data.shape[1], width=data.shape[2], transform=transform, driver="GTiff",
               compress="deflate", tiled=True, blockxsize=256, blockysize=256, nodata=nodata)
OUT.parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(OUT, "w", **profile) as dst:
    dst.write(data)
    dst.update_tags(SOURCE="WorldPop India 2020 constrained 100 m, ind_ppp_2020_constrained.tif, DOI 10.5258/SOTON/WP00684",
                    LICENSE="CC BY 4.0", CLIP="PMC Prabhag 11 Bopodi-SPPU + 2 km margin", UNITS="people per pixel")

band = data[0].astype("float64")
valid = band[band != nodata] if nodata is not None else band[~np.isnan(band)]
print(f"written {OUT.relative_to(ROOT).as_posix()}: {data.shape[2]} x {data.shape[1]} px, {OUT.stat().st_size/1024:.0f} KB")
print(f"people in the clip window (ward + 2 km): {valid.sum():,.0f}   max per pixel {valid.max():.1f}")

# population inside the ward itself (exact polygon), for the record
with rasterio.open(OUT) as src:
    inside, _ = mask(src, [area.geometry.iloc[0].__geo_interface__], crop=True, nodata=nodata)
    b = inside[0].astype("float64")
    v = b[b != nodata] if nodata is not None else b[~np.isnan(b)]
    print(f"people inside Prabhag 11 (WorldPop 2020 estimate): {v.sum():,.0f}")
