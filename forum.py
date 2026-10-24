"""
Forum storage + helpers. Posts live in a CSV so they survive reruns and restarts.
Proof of concept: no accounts, no moderation, fine for a demo but not for real traffic.

If you ever change COLUMNS, delete data/forum_posts.csv so the old file doesn't mismatch.
"""
import re
import uuid
from datetime import datetime, timezone

import pandas as pd

from data_loader import DATA_DIR

POSTS_FILE = DATA_DIR / "forum_posts.csv"
COLUMNS = ["post_id", "posted_at_utc", "name", "role", "group", "surveying",
           "plot_id", "status", "details", "contact"]

ROLES = ["Student", "Researcher", "Land manager", "Agency staff", "Volunteer", "Other"]
STATUSES = ["Planning", "In progress", "Finished", "Looking for collaborators"]
NO_PLOT = "(not about a specific plot)"


def load_posts() -> pd.DataFrame:
    """All posts, newest first. Everything is read as text so plot ids like '0070'
    keep their leading zero and empty fields stay empty strings."""
    if not POSTS_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(POSTS_FILE, dtype=str, keep_default_na=False)
    return df.sort_values("posted_at_utc", ascending=False).reset_index(drop=True)


def add_post(*, name, role, group, surveying, plot_id, status, details, contact="") -> str:
    """Append one post. Appending (instead of rewriting the file) keeps two people
    posting at the same moment from wiping each other out."""
    row = dict(
        post_id=uuid.uuid4().hex[:8],
        posted_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        name=name.strip(), role=role, group=group.strip(), surveying=surveying.strip(),
        plot_id="" if plot_id == NO_PLOT else plot_id,
        status=status, details=details.strip(), contact=contact.strip(),
    )
    DATA_DIR.mkdir(exist_ok=True)
    pd.DataFrame([row], columns=COLUMNS).to_csv(
        POSTS_FILE, mode="a", header=not POSTS_FILE.exists(), index=False)
    return row["post_id"]


def md(text: str) -> str:
    """Escape user text before showing it with st.markdown, so people can't inject
    links, images, or formatting. Newlines are kept as line breaks."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<$])", r"\\\1", text).replace("\n", "  \n")


def add_location(posts: pd.DataFrame, plot_county: pd.DataFrame) -> pd.DataFrame:
    """Adds county_label ('Butte County, CA') and state ('CA') to every post by looking up
    its plot_id. Posts with no plot, or a plot we can't place in a county, get ''."""
    out = posts.merge(plot_county[["plot_id", "county_label"]].drop_duplicates("plot_id"),
                      on="plot_id", how="left")
    out["county_label"] = out["county_label"].fillna("")
    out["state"] = out["county_label"].str.rsplit(", ", n=1).str[-1].where(out["county_label"] != "", "")
    return out


def filter_by_location(posts, states=None, counties=None, include_no_plot=True) -> pd.DataFrame:
    """No location picked -> everything. Otherwise keep posts in the picked states/counties,
    plus (if include_no_plot) posts that have no location, since they aren't 'elsewhere'."""
    if not (states or counties):
        return posts
    has_loc = posts["county_label"] != ""
    match = pd.Series(True, index=posts.index)
    if states:
        match &= posts["state"].isin(states)
    if counties:
        match &= posts["county_label"].isin(counties)
    return posts[(has_loc & match) | (~has_loc & include_no_plot)]