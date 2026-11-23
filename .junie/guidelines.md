# OpScope — agent guidelines

VALORANT scouting tool for Cloud9 coaches (Cloud9 x JetBrains "Sky's The Limit" hackathon, Category 1).

## Stack
- Python 3.14, uv, pandas 3 (pyarrow-backed strings), plotly, streamlit; tests with pytest (`uv run pytest`)
- Dashboard: `app.py` (st.navigation) → pages in `views/`. Shared run configs live in `.run/`.
- Roadmap: `notes/PLAN.md`. Current status: `CLAUDE.md`.

## Code map (`src/opscope/`)
- `data.py`: streaming readers (`iter_envelopes`, `iter_jsonl`, `load_meta`).
- `ingest/feed.py`: `SeriesParser` turns one GRID feed into rows (games, rounds, loadouts, engagements, casts, snapshots). It handles GRID rollbacks (`!` actions) with an undo stack keyed by (type, actor id, target id).
- `ingest/supplement.py`: joins precise cast positions on `grid_event_id`. `ingest/build.py`: parallel build into `cache/v1/*.parquet`.
- `load.py`: `load()` returns a `Dataset` of DataFrames. `taxonomy.py`: weapon groups and ability → utility class.
- `analytics/`: `operator.py` (Scope → OperatorReport), `stats.py` (Wilson interval, "k of n" text).
- `maps.py`: data-drawn backdrop, spawns, aggression. `ui/`: minimap, cards, filters.

## Testing rules
- Tests use **synthetic** GRID envelopes built in `tests/fixtures.py`. Never put real data (or excerpts) in tests or prompts.
- Feed the parser `(occurredAt, event)` pairs: `parse_envelopes(series_id, pairs)` from `opscope.ingest.feed`.
- Full-state events (`includesFullState: true`) carry `seriesState.games[].teams[].players[]` with `inventory.items[].id`,
  `character.id`, `position {x,y}`, `alive`, `money`, `loadoutValue`, and `games[].segments[-1].teams[].side`.

## Data rules (hard requirements)
- GRID data lives at `$STL_DATA_DIR` (set in `.env`). Never copy it into this repo or commit it.
- Read `$STL_DATA_DIR/AGENTS.md` for the data format before writing parsers.
- Stream `.zst` files with `compression.zstd`; never decompress to disk.
- Use team IDs, not team names, to track teams. Times are UTC.

## Product rules
- Every insight shown to coaches must display its sample size (e.g. "48 of 64 rounds").
- Show insights visually (heatmaps, charts, counts), not as chatbot text.
- Keep the UI usable by coaches with no technical background.
