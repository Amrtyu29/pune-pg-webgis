"""Phase 2: elevation layer. Reads the Copernicus GLO-30 DEM (30 m, open data, no API key) for the
1x1 degree tile covering Pune straight from the public AWS bucket, clips it to the study area plus a
2 km margin, and writes data/dem/dem_prabhag11.tif, the GeoTIFF GeoServer serves by WMS and WCS.

    .venv\\Scripts\\python.exe analysis\\prepare_dem.py

Why Copernicus and not SRTM: the brief allows "SRTM 30 m DEM or Bhuvan CartoDEM"; SRTM needs a NASA
Earthdata or OpenTopography account, while Copernicus GLO-30 is the same resolution, newer (TanDEM-X,
2011-2015), and downloadable with a plain HTTP range request.  Source and licence are written into the
GeoTIFF tags and in README.md.
Tile: Copernicus_DSM_COG_10_N18_00_E073_00_DEM (lat 18-19 N, lon 73-74 E).  The study area
(18.53-18.58 N, 73.81-73.85 E) sits fully inside it."""
from pathlib import Path
import json

import geopandas as gpd
import rasterio
from rasterio.mask import mask

ROOT = Path(__file__).resolve().parents[1]
TILE = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N18_00_E073_00_DEM/"
        "Copernicus_DSM_COG_10_N18_00_E073_00_DEM.tif")
OUT = ROOT / "data" / "dem" / "dem_prabhag11.tif"
UTM = 32643

area = gpd.read_file(ROOT / "data" / "area" / "prabhag11.geojson").set_crs(4326, allow_override=True)
clip_poly = area.to_crs(UTM).buffer(2000).to_crs(4326).iloc[0]     # area + 2 km, back in the DEM's CRS (4326)

# /vsicurl/ lets GDAL read only the byte ranges it needs from the Cloud-Optimised GeoTIFF
with rasterio.open("/vsicurl/" + TILE) as src:
    print("source:", src.crs, src.res, src.width, "x", src.height, "nodata", src.nodata)
    NODATA = -9999.0                      # the source tile has no nodata value; pixels outside the clip get this
    data, transform = mask(src, [clip_poly.__geo_interface__], crop=True, nodata=NODATA)
    profile = src.profile.copy()

profile.update(height=data.shape[1], width=data.shape[2], transform=transform, driver="GTiff",
               compress="deflate", tiled=True, blockxsize=256, blockysize=256, nodata=NODATA)
OUT.parent.mkdir(parents=True, exist_ok=True)
with rasterio.open(OUT, "w", **profile) as dst:
    dst.write(data)
    dst.update_tags(SOURCE="Copernicus DEM GLO-30 (ESA/Airbus), tile N18_00_E073_00, via AWS Open Data",
                    LICENSE="Copernicus DEM licence (free use with attribution)",
                    CLIP="PMC Prabhag 11 Bopodi-SPPU + 2 km margin", UNITS="metres above EGM2008 geoid")
band = data[0]
valid = band[band != profile["nodata"]]
print(f"written {OUT.relative_to(ROOT).as_posix()}: {data.shape[2]} x {data.shape[1]} px, "
      f"{OUT.stat().st_size/1024:.0f} KB, elevation {valid.min():.0f}-{valid.max():.0f} m (mean {valid.mean():.0f} m)")
