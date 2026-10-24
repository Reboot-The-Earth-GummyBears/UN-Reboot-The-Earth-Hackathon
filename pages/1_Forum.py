import streamlit as st

import forum
from data_loader import load_all

st.set_page_config(page_title="OFO Forum", layout="wide")


@st.cache_data(show_spinner="Loading plot locations...")
def plot_info():
    D = load_all()  # same loader the map uses; we only keep the two small tables we need
    return sorted(D["plots"]["plot_id"]), D["plot_county"][["plot_id", "county_label"]]


PLOT_IDS, PLOT_COUNTY = plot_info()


# ------------------------------------------------------------ new-post form
DEFAULTS = {"f_name": "", "f_role": forum.ROLES[0], "f_group": "", "f_surveying": "",
            "f_plot": forum.NO_PLOT, "f_status": forum.STATUSES[0], "f_details": "", "f_contact": ""}
REQUIRED = [("your name", "f_name"), ("group", "f_group"),
            ("what you're surveying", "f_surveying"), ("details", "f_details")]


def submit_post():
    """Runs when the button is clicked. Validating here (not in the page body) lets us
    keep what the person typed if something is missing, and clear it only on success."""
    s = st.session_state
    missing = [label for label, key in REQUIRED if not s[key].strip()]
    if missing:
        s["flash"] = ("error", "Please fill in: " + ", ".join(missing))
        return
    forum.add_post(name=s.f_name, role=s.f_role, group=s.f_group, surveying=s.f_surveying,
                   plot_id=s.f_plot, status=s.f_status, details=s.f_details, contact=s.f_contact)
    for key, default in DEFAULTS.items():
        s[key] = default
    s["flash"] = ("success", "Posted! You can find it under 'Browse posts'.")


st.title("Survey forum")
st.caption("Let other groups know what you're working on, where, and how it's going.")

tab_browse, tab_new = st.tabs(["Browse posts", "Write a post"])

# ----------------------------------------------------------- write a post
with tab_new:
    with st.form("new_post"):
        c1, c2 = st.columns(2)
        c1.text_input("Your name *", key="f_name", max_chars=80)
        c2.selectbox("Who are you?", forum.ROLES, key="f_role")
        c1.text_input("Group / organization *", key="f_group", max_chars=120)
        c2.text_input("What are you surveying? *", key="f_surveying", max_chars=160,
                      placeholder="e.g. post-fire regeneration, conifer mortality")
        c1.selectbox("Plot", [forum.NO_PLOT] + PLOT_IDS, key="f_plot")
        c2.selectbox("Status of work", forum.STATUSES, key="f_status")
        st.text_area("Details *", key="f_details", max_chars=1500,
                     placeholder="What are you doing, what do you need, who should reach out?")
        st.text_input("Contact (optional, shown publicly)", key="f_contact", max_chars=120)
        st.form_submit_button("Post", on_click=submit_post)

    flash = st.session_state.pop("flash", None)
    if flash:
        (st.error if flash[0] == "error" else st.success)(flash[1])

# --------------------------------------------------------------- browse
with tab_browse:
    posts = forum.add_location(forum.load_posts(), PLOT_COUNTY)

    if not posts.empty:
        c_status, c_state, c_county = st.columns(3)
        status_pick = c_status.multiselect("Status", forum.STATUSES)
        # only offer places that actually have posts, so a filter never gives an empty list
        located = posts[posts["county_label"] != ""]
        state_pick = c_state.multiselect("State", sorted(located["state"].unique()))
        county_opts = located[located["state"].isin(state_pick)] if state_pick else located
        county_pick = c_county.multiselect("County", sorted(county_opts["county_label"].unique()))
        include_no_plot = st.checkbox(
            "Also show posts not tied to a plot", value=True,
            help="Only matters when a state or county is picked.")

        if status_pick:
            posts = posts[posts["status"].isin(status_pick)]
        posts = forum.filter_by_location(posts, state_pick, county_pick, include_no_plot)

    if posts.empty:
        st.info("No posts to show. Write one in the 'Write a post' tab, or loosen the filters.")
    else:
        st.caption(f"{len(posts)} post(s), newest first")
        for _, p in posts.iterrows():
            where = f" ({p['county_label']})" if p["county_label"] else ""
            with st.container(border=True):
                st.markdown(f"**{forum.md(p['name'])}** · {forum.md(p['role'])} · {forum.md(p['group'])}")
                st.markdown(f"Surveying: {forum.md(p['surveying'])}  \n"
                            f"Plot: {forum.md(p['plot_id']) or '—'}{forum.md(where)} · Status: **{p['status']}**")
                st.markdown(forum.md(p["details"]))
                if p["contact"]:
                    st.markdown(f"Contact: {forum.md(p['contact'])}")
                st.caption(f"Posted {p['posted_at_utc'].replace('T', ' ')} UTC")

        with st.expander("View as table / download"):
            st.dataframe(posts.drop(columns="post_id"), hide_index=True, width="stretch")
            st.download_button("Download CSV", posts.to_csv(index=False), "forum_posts.csv", "text/csv")