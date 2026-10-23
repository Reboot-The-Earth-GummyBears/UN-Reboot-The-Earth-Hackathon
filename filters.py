"""
Add new filters here, then wire a widget to them in app.py.

Convention: passing None (or an empty list) means "don't filter on this".
"""
import pandas as pd


def between(df: pd.DataFrame, col: str, lo, hi, keep_na: bool = True) -> pd.DataFrame:
    """Range filter. Many columns are mostly NaN (height is ~50% missing), so
    keep_na decides whether rows with no value survive a range filter."""
    in_range = df[col].between(lo, hi)
    return df[in_range | df[col].isna()] if keep_na else df[in_range]


def isin(df: pd.DataFrame, col: str, values) -> pd.DataFrame:
    return df[df[col].isin(values)] if values else df


def filter_trees(
    trees: pd.DataFrame,
    *,
    species=None,
    live_dead=None,
    projects=None,
    dbh=None,        # (lo, hi) or None
    height=None,     # (lo, hi) or None
    years=None,      # (lo, hi) or None
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


def plots_with_trees(plots, filtered_trees):
    """Only keep plots that still have at least one tree after filtering."""
    return plots[plots["plot_id"].isin(filtered_trees["plot_id"].unique())]


def missions_for_plots(missions, plot_missions, plot_ids):
    """Only keep missions that overlap at least one remaining plot."""
    ids = plot_missions.loc[plot_missions["plot_id"].isin(plot_ids), "mission_id"].unique()
    return missions[missions["mission_id"].isin(ids)]