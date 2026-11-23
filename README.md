# OpScope

VALORANT Operator & utility scouting for Cloud9 coaches. Built for the Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026 (Category 1).

## Setup

1. Install Python 3.14 and [uv](https://docs.astral.sh/uv/).
2. Clone the GRID starter data **next to** this repo (not inside it):
   ```bash
   git clone --filter=blob:none --sparse https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git
   cd stl-hackathon-2026-grid-starter
   git sparse-checkout set val val-ability-supplements meta
   ```
3. Copy `.env.example` to `.env` and set `STL_DATA_DIR` to that clone.
4. Install dependencies: `uv sync`
5. Check the data loads: `uv run python explore.py`
6. Run the dashboard: `uv run streamlit run app.py`

## Data

Uses official GRID esports data provided for the hackathon. The data is not included in this repository.

## Built with

PyCharm, Junie, JetBrains Air, Python, pandas, Plotly, Streamlit.

## License

MIT
