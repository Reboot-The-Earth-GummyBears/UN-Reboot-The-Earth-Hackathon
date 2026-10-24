"""
Load + clean the three OFO gpkg files. No Streamlit in here, so you can
test it from a notebook:  from data_loader import load_all; d = load_all()

Returns a dict:
  trees         pandas DataFrame  (one row per tree, with lon/lat and a few plot columns)
  plots         GeoDataFrame      (plot polygons)
  missions      GeoDataFrame      (drone mission footprints, simplified for drawing)
  plot_missions DataFrame         (plot_id, mission_id) -- which missions overlap which plots
  counties_all    GeoDataFrame    (all US counties from Census)
  counties_pan    GeoDataFrame    (counties in PAN_STATES — for the pan-to-county menu)
  plot_county     DataFrame       (plot_id, county_label) -- OFO plots only
"""
from pathlib import Path
import re

import geopandas as gpd
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

# OFO ground plots in this catalog fall in these states only (CA-heavy).
PAN_STATES = ("CA", "OR", "WA")


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

WHP_ORDER = ["Very low", "Low", "Moderate", "High", "Very high", "Non-burnable", "Water", "Unrated"]

def load_whp_table() -> pd.DataFrame:
    """plot_id -> hazard class, made by prep_whp.py. If that hasn't been run, the app
    still works and every plot is just 'Unrated'."""
    f = DATA_DIR / "plot_whp.csv"
    if not f.exists():
        return pd.DataFrame({"plot_id": pd.Series(dtype=str), "whp_class": pd.Series(dtype="Int64"),
                             "whp_label": pd.Series(dtype=str)})
    return pd.read_csv(f, dtype={"plot_id": str, "whp_class": "Int64"})  # str keeps '0070' intact

def load_plots() -> gpd.GeoDataFrame:
    plots = gpd.read_file(_find("*plots*.gpkg")).to_crs(4326)
    plots["survey_year"] = plots["survey_date"].map(_survey_year).astype("Int64")
    plots["top_species_list"] = plots["top_species"].map(_species_codes)
    plots = plots.merge(load_whp_table(), on="plot_id", how="left")
    plots["whp_label"] = plots["whp_label"].fillna("Unrated")
    return plots


def load_trees(plots: gpd.GeoDataFrame) -> pd.DataFrame:
    gdf = gpd.read_file(_find("*trees*.gpkg")).to_crs(4326)
    gdf["lon"], gdf["lat"] = gdf.geometry.x, gdf.geometry.y
    trees = pd.DataFrame(gdf.drop(columns="geometry"))

    trees["live_dead"] = trees["live_dead"].fillna("unknown")
    trees["species_code"] = trees["species_code"].fillna("unknown")

    # bring a few plot-level columns onto every tree so tree filters can use them
    plot_cols = plots[["plot_id", "project_name", "survey_year", "plot_area_ha", "whp_label"]]
    trees = trees.merge(plot_cols, on="plot_id", how="left")
    return trees


def _numeric_bounds(series: pd.Series):
    """'80' -> (80, 80);  '80, 70' -> (70, 80);  blank -> (NaN, NaN).
    A few missions list two values (e.g. two flight altitudes), so we keep min and max."""
    parts = series.str.split(",", expand=True).apply(pd.to_numeric, errors="coerce")
    return parts.min(axis=1), parts.max(axis=1)


def load_missions() -> gpd.GeoDataFrame:
    m = gpd.read_file(_find("*drone-missions*.gpkg")).to_crs(4326)
    # these arrive as text; each becomes <col>_min / <col>_max for the filters
    for col in ["altitude_agl_nominal", "overlap_front_nominal", "overlap_side_nominal"]:
        m[col + "_min"], m[col + "_max"] = _numeric_bounds(m[col])
    return m


def link_plots_to_missions(plots, missions) -> pd.DataFrame:
    """Spatial join done ONCE. Filters then just use the plot_id/mission_id pairs."""
    j = gpd.sjoin(
        plots[["plot_id", "geometry"]],
        missions[["mission_id", "geometry"]],
        predicate="intersects",
    )
    return j[["plot_id", "mission_id"]].drop_duplicates().reset_index(drop=True)


def load_counties(plots):
    c = gpd.read_file(_find("cb_2025_us_county_5m.zip")).to_crs(4326)
    # newer Census files have STUSPS; older ones only have STATEFP codes
    if "STUSPS" not in c.columns:
        codes = {"04": "AZ", "06": "CA", "08": "CO", "16": "ID", "30": "MT", "32": "NV",
                 "35": "NM", "41": "OR", "49": "UT", "53": "WA", "56": "WY"}
        c["STUSPS"] = c["STATEFP"].map(codes).fillna(c["STATEFP"])
    c["county_label"] = c["NAMELSAD"] + ", " + c["STUSPS"]

    # one county per plot, using the plot's center point (avoids double-counting border plots)
    pts = gpd.GeoDataFrame(plots[["plot_id"]], geometry=plots.representative_point(), crs=plots.crs)
    j = gpd.sjoin(pts, c[["county_label", "geometry"]], predicate="within")
    plot_county = j[["plot_id", "county_label"]]
    return c, plot_county

def load_all() -> dict:
    plots = load_plots()
    trees = load_trees(plots)
    missions = load_missions()
    plot_missions = link_plots_to_missions(plots, missions)
    counties_all, plot_county = load_counties(plots)
    counties_pan = counties_all[counties_all["STUSPS"].isin(PAN_STATES)].copy()
    # simplify AFTER the join: ~50 m tolerance, only for drawing, keeps the browser light
    missions["geometry"] = missions.geometry.simplify(0.0005, preserve_topology=True)
    return dict(
        trees=trees,
        plots=plots,
        missions=missions,
        plot_missions=plot_missions,
        counties_all=counties_all,
        counties_pan=counties_pan,
        plot_county=plot_county,
    )


if __name__ == "__main__":
    d = load_all()
    for k, v in d.items():
        print(k, v.shape)