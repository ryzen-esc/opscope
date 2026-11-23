"""OpScope dashboard. Run with: uv run streamlit run app.py"""
import streamlit as st

from opscope.ui import theme  # noqa: F401  (registers the Plotly template)
from opscope.ui.brand import ICON
from opscope.ui.cards import inject_css

st.set_page_config(page_title="OpScope", page_icon=ICON, layout="wide", initial_sidebar_state="expanded")
st.logo(ICON, size="large", icon_image=ICON)
inject_css()

SETUP_HELP = """
**OpScope needs the GRID data and a local cache before it can show anything.**

1. Clone the hackathon data repo next to this project (see the README):
   `git clone --filter=blob:none --sparse https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git`
2. Copy `.env.example` to `.env` and point `STL_DATA_DIR` at that clone.
3. Build the cache (about 4 minutes): `uv run python -m opscope.ingest.build`
4. Reload this page.
"""


@st.cache_resource(show_spinner="Loading 2,000+ pro maps…")
def dataset_summary() -> dict:
    from opscope.load import load
    d = load()
    started = d.games["started_at"].dropna().str[:10]
    return {"games": len(d.games), "series": d.games["series_id"].nunique(),
            "rounds": int(d.rounds["played"].sum()), "first": started.min(), "last": started.max()}


try:
    summary = dataset_summary()
except (FileNotFoundError, RuntimeError) as exc:  # no cache yet, or STL_DATA_DIR not set
    st.title("OpScope")
    st.warning(SETUP_HELP)
    st.caption(f"Details: {exc}")
    st.stop()

pages = [
    st.Page("views/report.py", title="Scouting report", icon=":material/assignment:", default=True),
    st.Page("views/operator.py", title="Operator profiler", icon=":material/my_location:"),
    st.Page("views/utility.py", title="Utility profiler", icon=":material/scatter_plot:"),
    st.Page("views/about.py", title="How it works", icon=":material/info:"),
]
st.session_state["data_summary"] = (
    f"Data: GRID official match data · {summary['series']:,} series · {summary['games']:,} maps · "
    f"{summary['rounds']:,} rounds · {summary['first']} to {summary['last']}")
st.navigation(pages, position="top").run()
