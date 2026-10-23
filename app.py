import json

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import filters
from data_loader import load_all

st.set_page_config(page_title="OFO Explorer", layout="wide")

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

# ----------------------------------------------------------------- sidebar
st.sidebar.header("Filters")

species = st.sidebar.multiselect("Species", sorted(trees["species_code"].unique()))
live_dead = st.sidebar.multiselect("Live / dead", sorted(trees["live_dead"].unique()))
projects = st.sidebar.multiselect("Project", sorted(trees["project_name"].dropna().unique()))


def range_slider(label, col):
    lo, hi = float(trees[col].min()), float(trees[col].max())
    val = st.sidebar.slider(label, lo, hi, (lo, hi))
    return None if val == (lo, hi) else val  # untouched slider = no filter


dbh = range_slider("DBH (cm)", "dbh")
height = range_slider("Height (m)", "height")

y_lo, y_hi = int(trees["survey_year"].min()), int(trees["survey_year"].max())
years = st.sidebar.slider("Survey year", y_lo, y_hi, (y_lo, y_hi))
years = None if years == (y_lo, y_hi) else years

keep_na = st.sidebar.checkbox("Keep trees with missing values", value=True,
                              help="Applies to the DBH / height / year range filters.")

st.sidebar.header("Layers")
show_plots = st.sidebar.checkbox("Plot boundaries", value=True)
show_missions = st.sidebar.checkbox("Drone missions", value=True)

# ------------------------------------------------------- apply filters ONCE
f_trees = filters.filter_trees(
    trees, species=species, live_dead=live_dead, projects=projects,
    dbh=dbh, height=height, years=years, keep_na=keep_na,
)
f_plots = filters.plots_with_trees(plots, f_trees)
f_missions = filters.missions_for_plots(missions, D["plot_missions"], f_plots["plot_id"])

# ----------------------------------------------------------------- header
st.title("OFO ground reference explorer")
c1, c2, c3 = st.columns(3)
c1.metric("Trees", f"{len(f_trees):,}", f"of {len(trees):,}", delta_color="off")
c2.metric("Plots", f"{len(f_plots):,}", f"of {len(plots):,}", delta_color="off")
c3.metric("Drone missions", f"{len(f_missions):,}", f"of {len(missions):,}", delta_color="off")

if f_trees.empty:
    st.warning("No trees match the current filters.")
    st.stop()

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

drawn = f_trees if len(f_trees) <= MAX_POINTS_DRAWN else f_trees.sample(MAX_POINTS_DRAWN, random_state=0)
fig.add_trace(go.Scattermap(
    lat=drawn["lat"], lon=drawn["lon"], mode="markers",
    marker=dict(size=5, color="#16a34a"), name="Trees",
    text=drawn["species_code"] + " | dbh " + drawn["dbh"].round(1).astype(str)
         + " | plot " + drawn["plot_id"],
    hoverinfo="text",
))

span = max(np.ptp(f_trees["lon"]), np.ptp(f_trees["lat"]))
fig.update_layout(
    map_style="open-street-map",
    map_center=dict(lat=float(f_trees["lat"].mean()), lon=float(f_trees["lon"].mean())),
    map_zoom=float(np.clip(8 - np.log2(span + 1e-6), 3, 12)),
    margin=dict(l=0, r=0, t=0, b=0), height=600,
    legend=dict(orientation="h", y=0.01, x=0.01, bgcolor="rgba(255,255,255,0.7)"),
)
st.plotly_chart(fig, width="stretch")
if len(f_trees) > MAX_POINTS_DRAWN:
    st.caption(f"Map shows a random {MAX_POINTS_DRAWN:,} of {len(f_trees):,} trees. "
               "The table below has all of them.")

# ------------------------------------------------- tables (same filtered dfs)
tab_trees, tab_plots, tab_missions = st.tabs(["Trees", "Plots", "Missions"])
with tab_trees:
    st.dataframe(f_trees, width="stretch", hide_index=True)
with tab_plots:
    st.dataframe(f_plots.drop(columns=["geometry", "license"]), width="stretch", hide_index=True)
with tab_missions:
    st.dataframe(f_missions.drop(columns="geometry"), width="stretch", hide_index=True)