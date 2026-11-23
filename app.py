"""OpScope dashboard. Run with: uv run streamlit run app.py"""
import streamlit as st

from opscope.ui.cards import inject_css

st.set_page_config(page_title="OpScope", page_icon="🎯", layout="wide")
inject_css()

pages = [
    st.Page("views/operator.py", title="Operator profiler", icon=":material/my_location:", default=True),
    st.Page("views/utility.py", title="Utility profiler", icon=":material/scatter_plot:"),
]
st.sidebar.markdown("## OpScope")
st.sidebar.caption("VALORANT scouting for Cloud9")
st.navigation(pages).run()
