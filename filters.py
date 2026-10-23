"""
Pure filter functions: DataFrame in, DataFrame out. No Streamlit, no plotting.
This is the file you own. Add new filters here, then wire a widget to them in app.py.

Convention: passing None (or an empty list) means "don't filter on this".

Two groups of filters:
  * tree filters     -> narrow the trees table directly
  * mission filters  -> narrow the missions table; plots_for_missions() then turns the
                        surviving missions into the plots they overlap, so mission
                        filters also affect the trees, plots, and map.
"""
import pandas as pd


# ------------------------------------------------------------- building blocks
def between(df: pd.DataFrame, col: str, lo, hi, keep_na: bool = True) -> pd.DataFrame:
    """Range filter. Many columns are mostly NaN (height is ~50% missing), so
    keep_na decides whether rows with no value survive a range filter."""
    in_range = df[col].between(lo, hi)
    return df[in_range | df[col].isna()] if keep_na else df[in_range]


def interval_between(df, col_min, col_max, lo, hi, keep_na: bool = True) -> pd.DataFrame:
    """For columns stored as a (min, max) pair, e.g. a mission that flew at 70 AND 80 m.
    A row passes if its [min, max] interval touches the selected [lo, hi] range."""
    hit = (df[col_min] <= hi) & (df[col_max] >= lo)
    return df[hit | df[col_min].isna()] if keep_na else df[hit]


def isin(df: pd.DataFrame, col: str, values) -> pd.DataFrame:
    return df[df[col].isin(values)] if values else df


# --------------------------------------------------------------- tree filters
def filter_trees(
    trees: pd.DataFrame,
    *,
    species=None,
    live_dead=None,
    projects=None,
    dbh=None,        # (lo, hi) or None
    height=None,     # (lo, hi) or None
    years=None,      # (lo, hi) or None  -- ground survey year
    keep_na: bool = True,
) -> pd.DataFrame:
    df = trees
    df = isin(df, "species_code", species)
    df = isin(df, "live_dead", live_dead)
    df = isin(df, "project_name", projects)
    if dbh:
        df = between(df, "dbh", *dbh, keep_na=keep_na)
    if height:
        df = between(df, "height", *height, keep_na=keep_na)
    if years:
        df = between(df, "survey_year", *years, keep_na=keep_na)
    return df


# ------------------------------------------------------------ mission filters
def filter_missions(
    missions: pd.DataFrame,
    *,
    dates=None,       # (start_date, end_date) or None  -- drone flight date
    front=None,       # (lo, hi) or None  -- front overlap %
    side=None,        # (lo, hi) or None  -- side overlap %
    altitude=None,    # (lo, hi) or None  -- nominal altitude above ground, m
    keep_na: bool = True,
) -> pd.DataFrame:
    df = missions
    if dates:
        df = between(df, "earliest_date_derived", pd.Timestamp(dates[0]), pd.Timestamp(dates[1]),
                     keep_na=keep_na)
    if front:
        df = interval_between(df, "overlap_front_nominal_min", "overlap_front_nominal_max",
                              *front, keep_na=keep_na)
    if side:
        df = interval_between(df, "overlap_side_nominal_min", "overlap_side_nominal_max",
                              *side, keep_na=keep_na)
    if altitude:
        df = interval_between(df, "altitude_agl_nominal_min", "altitude_agl_nominal_max",
                              *altitude, keep_na=keep_na)
    return df


def plots_for_missions(plot_missions: pd.DataFrame, mission_ids):
    """Plot ids overlapped by at least one of these missions."""
    return plot_missions.loc[plot_missions["mission_id"].isin(mission_ids), "plot_id"].unique()


# ------------------------------------------------------- propagate to layers
def plots_with_trees(plots, filtered_trees):
    """Only keep plots that still have at least one tree after filtering."""
    return plots[plots["plot_id"].isin(filtered_trees["plot_id"].unique())]


def missions_for_plots(missions, plot_missions, plot_ids):
    """Only keep missions that overlap at least one remaining plot."""
    ids = plot_missions.loc[plot_missions["plot_id"].isin(plot_ids), "mission_id"].unique()
    return missions[missions["mission_id"].isin(ids)]