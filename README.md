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
6. Build the local cache (about 4 minutes on 10 cores; written to the gitignored `cache/` folder):
   `uv run python -m opscope.ingest.build`
7. Run the dashboard: `uv run streamlit run app.py`

## Data

Uses official GRID esports data provided for the hackathon. The data is not included in this repository.

Map callout names and positions (`src/opscope/callouts.yaml`) come from the community API at [valorant-api.com](https://valorant-api.com), which uses the same coordinate system as GRID. Bomb-site centres (`src/opscope/sites.yaml`) are averaged from plant positions and contain no match data.

## Built with

PyCharm, Junie, JetBrains Air, Python, pandas, Plotly, Streamlit.

## License

MIT
