"""
Run ONCE (needs rasterio):   python prep_whp.py path/to/whp2023_cls_conus.tif

Writes small files into data/ that the app reads, so the app itself never opens the
huge GeoTIFF (and teammates don't need rasterio to run the app):
  plot_whp.csv      plot_id -> hazard class for every ground plot
  whp_overlay.png   colored, shrunken, map-ready picture of the region
  whp_overlay.json  the lon/lat corners that picture must be pinned to
"""
import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject, transform

from data_loader import DATA_DIR, _find

NODATA = 255
LABELS = {1: "Very low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very high",
          6: "Non-burnable", 7: "Water"}
# yellow -> red (ColorBrewer YlOrRd). Classes 6, 7 and no-data stay transparent.
COLORS = {1: (255, 255, 178), 2: (254, 204, 92), 3: (253, 141, 60),
          4: (240, 59, 32), 5: (189, 0, 38)}
PAD_DEG = 1.0     # margin around the plots, in degrees
RES_M = 1500      # overlay pixel size in meters. Smaller = sharper but a bigger PNG.


def main(tif):
    plots = gpd.read_file(_find("*plots*.gpkg")).to_crs(4326)

    with rasterio.open(tif) as src:
        # ---- 1) hazard class under each plot's center point
        pts = plots.representative_point().to_crs(src.crs)
        vals = np.array([v[0] for v in src.sample(zip(pts.x, pts.y))])
        cls = pd.Series(vals).astype("Int64").mask(vals == NODATA)
        table = pd.DataFrame({"plot_id": plots["plot_id"].values, "whp_class": cls.values})
        table["whp_label"] = table["whp_class"].map(LABELS).fillna("Unrated")
        table.to_csv(DATA_DIR / "plot_whp.csv", index=False)
        print("plots per class:\n", table["whp_label"].value_counts().to_string())

        # ---- 2) colored overlay picture, in Web Mercator so it lines up with the map tiles
        w, s, e, n = plots.total_bounds
        w, e, s, n = w - PAD_DEG, e + PAD_DEG, s - PAD_DEG, n + PAD_DEG
        (x0, x1), (y0, y1) = transform("EPSG:4326", "EPSG:3857", [w, e], [s, n])
        width, height = int(round((x1 - x0) / RES_M)), int(round((y1 - y0) / RES_M))
        dst = np.full((height, width), NODATA, np.uint8)
        reproject(
            source=rasterio.band(src, 1), destination=dst,
            src_transform=src.transform, src_crs=src.crs, src_nodata=NODATA,
            dst_transform=from_bounds(x0, y0, x1, y1, width, height), dst_crs="EPSG:3857",
            dst_nodata=NODATA, resampling=Resampling.mode,
        )

    # Palette PNG (index 0 = transparent, 1-5 = hazard colors): far smaller than a full RGBA image
    idx = np.where(np.isin(dst, list(COLORS)), dst, 0).astype(np.uint8)
    img = Image.frombytes("P", (width, height), idx.tobytes())
    palette = [0, 0, 0] * 256
    for k, rgb in COLORS.items():
        palette[3 * k:3 * k + 3] = list(rgb)
    img.putpalette(palette)
    out = DATA_DIR / "whp_overlay.png"
    img.save(out, optimize=True, transparency=0)
    (DATA_DIR / "whp_overlay.json").write_text(
        json.dumps(dict(west=w, east=e, south=s, north=n)))
    print(f"overlay: {width}x{height}px, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python prep_whp.py path/to/whp2023_cls_conus.tif")
    main(sys.argv[1])