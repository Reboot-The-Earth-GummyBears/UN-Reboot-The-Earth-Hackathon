"""
Load + clean the three OFO gpkg files. No Streamlit in here, so you can
test it from a notebook:  from data_loader import load_all; d = load_all()

Returns a dict:
  trees         pandas DataFrame  (one row per tree, with lon/lat and a few plot columns)
  plots         GeoDataFrame      (plot polygons)
  missions      GeoDataFrame      (drone mission footprints, simplified for drawing)
  plot_missions DataFrame         (plot_id, mission_id) -- which missions overlap which plots
"""
from pathlib import Path
import re

import geopandas as gpd
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


def _find(pattern: str) -> Path:
    """Glob so a re-downloaded file like trees_1.gpkg still works."""
    # skip 0-byte files (failed downloads) and take the newest match
    hits = [p for p in DATA_DIR.glob(pattern) if p.stat().st_size > 0]
    if not hits:
        raise FileNotFoundError(f"No non-empty file matching {pattern!r} in {DATA_DIR}")
    return max(hits, key=lambda p: p.stat().st_mtime)


def _survey_year(v):
    """survey_date is a float that is sometimes YYYY, YYYYMM, or YYYYMMDD."""
    if pd.isna(v):
        return pd.NA
    return int(str(int(v))[:4])


def _species_codes(s):
    """'ABCO (49%), CADE27 (29%)' -> ['ABCO', 'CADE27']"""
    if not isinstance(s, str):
        return []
    return re.findall(r"([A-Z0-9]+)\s*\(", s)


def load_plots() -> gpd.GeoDataFrame:
    plots = gpd.read_file(_find("*plots*.gpkg")).to_crs(4326)
    plots["survey_year"] = plots["survey_date"].map(_survey_year).astype("Int64")
    plots["top_species_list"] = plots["top_species"].map(_species_codes)
    return plots


def load_trees(plots: gpd.GeoDataFrame) -> pd.DataFrame:
    gdf = gpd.read_file(_find("*trees*.gpkg")).to_crs(4326)
    gdf["lon"], gdf["lat"] = gdf.geometry.x, gdf.geometry.y
    trees = pd.DataFrame(gdf.drop(columns="geometry"))

    trees["live_dead"] = trees["live_dead"].fillna("unknown")
    trees["species_code"] = trees["species_code"].fillna("unknown")

    # bring a few plot-level columns onto every tree so tree filters can use them
    plot_cols = plots[["plot_id", "project_name", "survey_year", "plot_area_ha"]]
    trees = trees.merge(plot_cols, on="plot_id", how="left")
    return trees


def load_missions() -> gpd.GeoDataFrame:
    m = gpd.read_file(_find("*drone-missions*.gpkg")).to_crs(4326)
    for col in ["altitude_agl_nominal", "base_alt"]:
        # note: altitude_agl_nominal sometimes holds "80, 70" -> becomes NaN here
        m[col + "_num"] = pd.to_numeric(m[col], errors="coerce")
    return m


def link_plots_to_missions(plots, missions) -> pd.DataFrame:
    """Spatial join done ONCE. Filters then just use the plot_id/mission_id pairs."""
    j = gpd.sjoin(
        plots[["plot_id", "geometry"]],
        missions[["mission_id", "geometry"]],
        predicate="intersects",
    )
    return j[["plot_id", "mission_id"]].drop_duplicates().reset_index(drop=True)


def load_all() -> dict:
    plots = load_plots()
    trees = load_trees(plots)
    missions = load_missions()
    plot_missions = link_plots_to_missions(plots, missions)
    # simplify AFTER the join: ~50 m tolerance, only for drawing, keeps the browser light
    missions["geometry"] = missions.geometry.simplify(0.0005, preserve_topology=True)
    return dict(trees=trees, plots=plots, missions=missions, plot_missions=plot_missions)


if __name__ == "__main__":
    d = load_all()
    for k, v in d.items():
        print(k, v.shape)