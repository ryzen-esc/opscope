# OpScope — agent guidelines

VALORANT scouting tool for Cloud9 coaches (Cloud9 x JetBrains "Sky's The Limit" hackathon, Category 1).

## Stack
- Python 3.14, uv, pandas, plotly, streamlit
- Code lives in `src/opscope/`; dashboard entry point is `app.py`

## Data rules (hard requirements)
- GRID data lives at `$STL_DATA_DIR` (set in `.env`). Never copy it into this repo or commit it.
- Read `$STL_DATA_DIR/AGENTS.md` for the data format before writing parsers.
- Stream `.zst` files with `compression.zstd`; never decompress to disk.
- Use team IDs, not team names, to track teams. Times are UTC.

## Product rules
- Every insight shown to coaches must display its sample size (e.g. "48 of 64 rounds").
- Show insights visually (heatmaps, charts, counts), not as chatbot text.
- Keep the UI usable by coaches with no technical background.
