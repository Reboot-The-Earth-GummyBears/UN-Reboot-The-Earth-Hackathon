import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import filters
from data_loader import load_all

st.set_page_config(page_title="OFO Explorer", layout="wide")

MISSION_TABLE_COLS = [
    "mission_id", "project_name", "earliest_date_derived", "altitude_agl_nominal",
    "overlap_front_nominal", "overlap_side_nominal", "flight_pattern", "sensor_name",
    "image_count_derived", "area_derived", "contributor_names",
]
MAX_POINTS_DRAWN = 40_000  # keep the browser responsive; the table always shows everything


@st.cache_data(show_spinner="Loading gpkg files...")
def get_data():
    d = load_all()
    # GeoJSON is built once. Filtering only changes which ids get drawn.
    # Only id + geometry go in the GeoJSON (smaller, and avoids un-serializable columns)
    d["plots_geojson"] = json.loads(d["plots"][["plot_id", "geometry"]].to_json())
    d["missions_geojson"] = json.loads(d["missions"][["mission_id", "geometry"]].to_json())
    return d


D = get_data()
trees, plots, missions = D["trees"], D["plots"], D["missions"]

st.sidebar.header("Map")
st.sidebar.caption("Ground plots in this dataset are only in California, Oregon, and Washington.")
pan_county = st.sidebar.selectbox(
    "Pan to county",
    [None] + sorted(D["counties_pan"]["county_label"]),
    format_func=lambda x: "Data extent (default)" if x is None else x,
)
filter_to_county = st.sidebar.checkbox(
    "Limit trees, plots, and missions to this county",
    value=False,
    disabled=pan_county is None,
    help="When off, the county choice only moves the map. When on, tables and layers "
         "show only OFO data in that county (may be empty).",
)

# ----------------------------------------------------------------- sidebar
st.sidebar.header("Tree filters")

species = st.sidebar.multiselect("Species", sorted(trees["species_code"].unique()))
live_dead = st.sidebar.multiselect("Live / dead", sorted(trees["live_dead"].unique()))
projects = st.sidebar.multiselect("Project", sorted(trees["project_name"].dropna().unique()))


def range_slider(label, lo, hi, step=None):
    lo, hi = float(lo), float(hi)
    val = st.sidebar.slider(label, lo, hi, (lo, hi), step=step)
    return None if val == (lo, hi) else val  # untouched slider = no filter


dbh = range_slider("DBH (cm)", trees["dbh"].min(), trees["dbh"].max())
height = range_slider("Height (m)", trees["height"].min(), trees["height"].max())

y_lo, y_hi = int(trees["survey_year"].min()), int(trees["survey_year"].max())
years = st.sidebar.slider("Ground survey year", y_lo, y_hi, (y_lo, y_hi))
years = None if years == (y_lo, y_hi) else years

st.sidebar.header("Drone mission filters")
st.sidebar.caption("These also narrow the plots and trees to those covered by a matching mission.")

d_lo = missions["earliest_date_derived"].min().date()
d_hi = missions["earliest_date_derived"].max().date()
picked = st.sidebar.date_input("Flight date", (d_lo, d_hi), min_value=d_lo, max_value=d_hi)
# date_input returns 1 date while the user is mid-selection; only filter once both are picked
dates = tuple(picked) if len(picked) == 2 and tuple(picked) != (d_lo, d_hi) else None

front = range_slider("Front overlap (%)", missions["overlap_front_nominal_min"].min(),
                     missions["overlap_front_nominal_max"].max(), step=1.0)
side = range_slider("Side overlap (%)", missions["overlap_side_nominal_min"].min(),
                    missions["overlap_side_nominal_max"].max(), step=1.0)
altitude = range_slider("Altitude above ground (m)", missions["altitude_agl_nominal_min"].min(),
                        missions["altitude_agl_nominal_max"].max(), step=1.0)

keep_na = st.sidebar.checkbox("Keep rows with missing values", value=True,
                              help="Applies to every range filter. E.g. ~half the trees have no "
                                   "height, and ~50 missions have no listed altitude.")

st.sidebar.header("Layers")
show_plots = st.sidebar.checkbox("Plot boundaries", value=True)
show_missions = st.sidebar.checkbox("Drone missions", value=True)

# ------------------------------------------------------- apply filters ONCE
# 1) mission filters -> surviving missions
f_missions_attr = filters.filter_missions(
    missions, dates=dates, front=front, side=side, altitude=altitude, keep_na=keep_na)
mission_filter_active = any(x is not None for x in (dates, front, side, altitude))

# 2) if any mission filter is on, only trees in plots overlapped by a surviving mission remain
base_trees = trees
if mission_filter_active:
    ok_plots = filters.plots_for_missions(D["plot_missions"], f_missions_attr["mission_id"])
    base_trees = trees[trees["plot_id"].isin(ok_plots)]
if filter_to_county and pan_county:
    base_trees = base_trees[base_trees["plot_id"].isin(
        filters.plots_in_county(D["plot_county"], pan_county))]

# 3) tree filters
f_trees = filters.filter_trees(
    base_trees, species=species, live_dead=live_dead, projects=projects,
    dbh=dbh, height=height, years=years, keep_na=keep_na,
)

# 4) plots and missions follow the trees that are left
f_plots = filters.plots_with_trees(plots, f_trees)
f_missions = filters.missions_for_plots(f_missions_attr, D["plot_missions"], f_plots["plot_id"])

# ----------------------------------------------------------------- header
st.title("OFO ground reference explorer")
n_linked = D["plot_missions"]["mission_id"].nunique()   # missions that overlap a ground plot (312)
n_unlinked = len(missions) - n_linked                   # missions with no nearby tree data (375)

c1, c2, c3 = st.columns(3)
c1.metric("Trees", f"{len(f_trees):,}", f"of {len(trees):,}", delta_color="off")
c2.metric("Plots", f"{len(f_plots):,}", f"of {len(plots):,}", delta_color="off")
c3.metric("Drone missions", f"{len(f_missions):,}", f"of {n_linked:,} near ground plots", delta_color="off")

st.caption(
    f"Only drone missions that overlap a ground-reference plot are shown ({n_linked:,} of "
    f"{len(missions):,}). The other {n_unlinked:,} have no tree data nearby, so the tree and "
    "plot filters can't connect to them."
)

if f_trees.empty:
    st.warning("No trees match the current filters.")

# -------------------------------------------------------------------- map
def polygon_layer(geojson, ids, key, color, name):
    return go.Choroplethmap(
        geojson=geojson, featureidkey=f"properties.{key}",
        locations=list(ids), z=[1] * len(ids),
        colorscale=[[0, color], [1, color]], showscale=False,
        marker_opacity=0.35, marker_line_width=1, marker_line_color=color,
        name=name, hoverinfo="location",
    )


fig = go.Figure()
if show_missions and len(f_missions):
    fig.add_trace(polygon_layer(D["missions_geojson"], f_missions["mission_id"],
                                "mission_id", "#3b82f6", "Missions"))
if show_plots and len(f_plots):
    fig.add_trace(polygon_layer(D["plots_geojson"], f_plots["plot_id"],
                                "plot_id", "#f59e0b", "Plots"))

if not f_trees.empty:
    drawn = f_trees if len(f_trees) <= MAX_POINTS_DRAWN else f_trees.sample(MAX_POINTS_DRAWN, random_state=0)
    fig.add_trace(go.Scattermap(
        lat=drawn["lat"], lon=drawn["lon"], mode="markers",
        marker=dict(size=5, color="#16a34a"), name="Trees",
        text=drawn["species_code"] + " | dbh " + drawn["dbh"].round(1).astype(str)
             + " | plot " + drawn["plot_id"],
        hoverinfo="text",
    ))

if pan_county:
    minx, miny, maxx, maxy = D["counties_pan"].loc[
        D["counties_pan"]["county_label"] == pan_county].total_bounds
    center = dict(lat=(miny + maxy) / 2, lon=(minx + maxx) / 2)
    span = max(maxx - minx, maxy - miny)
elif not f_trees.empty:
    center = dict(lat=float(f_trees["lat"].mean()), lon=float(f_trees["lon"].mean()))
    span = max(np.ptp(f_trees["lon"]), np.ptp(f_trees["lat"]))
else:
    center = dict(lat=float(trees["lat"].mean()), lon=float(trees["lon"].mean()))
    span = max(np.ptp(trees["lon"]), np.ptp(trees["lat"]))
fig.update_layout(
    map_style="open-street-map",
    map_center=center,
    map_zoom=float(np.clip(8 - np.log2(span + 1e-6), 3, 12)),
    margin=dict(l=0, r=0, t=0, b=0), height=600,
    legend=dict(orientation="h", y=0.01, x=0.01, bgcolor="rgba(255,255,255,0.7)"),
)
st.plotly_chart(fig, width="stretch")
if not f_trees.empty and len(f_trees) > MAX_POINTS_DRAWN:
    st.caption(f"Map shows a random {MAX_POINTS_DRAWN:,} of {len(f_trees):,} trees. "
               "The table below has all of them.")

# ------------------------------------------------- tables (same filtered dfs)
tab_trees, tab_plots, tab_missions = st.tabs(["Trees", "Plots", "Missions"])
with tab_trees:
    st.dataframe(f_trees, width="stretch", hide_index=True)
with tab_plots:
    st.dataframe(f_plots.drop(columns=["geometry", "license"]), width="stretch", hide_index=True)
with tab_missions:
    all_cols = st.checkbox("Show all 79 columns", value=False)
    cols = [c for c in MISSION_TABLE_COLS if c in f_missions.columns]
    show = f_missions.drop(columns="geometry") if all_cols else f_missions[cols]
    st.dataframe(show, width="stretch", hide_index=True)