# OpScope — context for Claude Code

## What this is
Eli's entry in the **Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026** (Devpost: cloud9.devpost.com), **Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler**.
- **Deadline:** Jan 12, 2027, 11:00am PT. Judging Jan 27–Feb 3, 2027.
- Devpost draft project "OpScope" exists; story/details get written at the end.

## The product
An automated scouting tool for VALORANT coaches that cuts manual VOD review:
- **Operator Profiler:** who buys/holds the Operator or Odin (player/agent), how often, where they set up on defense (aggressive vs passive angles), split by round time (0–20s, 20–40s...), and whether possession shifts.
- **Utility heatmaps:** where abilities are cast. Priority: placeable utility (Cypher trips, KJ alarmbots, Vyse walls, Chamber trips) > recon > smokes > reactive stall > flashes.
- **Filters:** opponent, map, player, agent, comp, patch, side, weapon, ability.
- **Evidence:** every insight shows its sample size ("48 of 64 rounds").
- **Going further:** anti-strat suggestions for Cloud9; self-scouting Cloud9's own tendencies.
- Judges want at least one useful, data-backed insight for Cloud9, shown visually (not a chatbot).
- GRID gives the caster's position/time for abilities, not the landing spot. Inferring landing spots is allowed but not required.

## Judging (equal weight)
Technological implementation (incl. depth of JetBrains tool use), Design (complete product, not a proof of concept), Potential impact, Quality of idea, Presentation (a demo video under 3 min).

## Submission requirements
- Public GitHub repo with all source + run instructions + LICENSE at the root (MIT, done). Commit `.idea/` and `.junie/`.
- Judge-accessible build: the repo with install steps (the data can't be published, so judges clone the GRID starter themselves).
- Text description listing the JetBrains tools used and what each did; methodology write-up; public YouTube demo under 3 min.
- Bonus ($1k, "Best AI-Powered Workflow Story"): log AI usage in `notes/AI_WORKFLOW_LOG.md` as we go → becomes `AI_SHOWCASE.md`.
- Must use at least one JetBrains tool (PyCharm + Junie + JetBrains Air are set up; All Products Pack + AI Ultimate active until Jan 23, 2027). AI Ultimate credits are limited (~35/month): use them for showcase-worthy Junie work.

## Data (GRID) — hard rules
- Lives at `$STL_DATA_DIR` = `/Users/eli/hackathon/stl-hackathon-2026-grid-starter` (sparse checkout: val, val-ability-supplements, meta). Read its `AGENTS.md` and README for the format.
- **Never copy, commit, or redistribute the data.** No commercial use. Opt out of AI training on the data where possible.
- `val/series.csv` lists series; feeds are `events_{seriesId}_grid.jsonl.zst` (JSON Lines envelopes with `events`; the last event's `seriesState` holds the final box score). Ability supplements join to `player-used-ability` via `grid_event_id`.
- Caveats: some missing matches; rolled-back events on replayed maps; some series lack `team-won-series`; some VCT Americas 2025 positions sampled at 1 Hz; track teams by ID, not name; times are UTC.
- Stream with `compression.zstd`; never decompress to disk (VAL is ~160 GB uncompressed).
- Riot assets: use original art; check Riot's developer policies before using official minimaps.

## Stack
Python 3.14, uv, pandas, plotly, streamlit. Package in `src/opscope/` (`data.py` has the streaming helpers); `explore.py` is the data sanity check; `app.py` is the Streamlit entry point.

## Status (Nov 23, 2026)
- Roadmap: `notes/PLAN.md` (milestones M1–M6).
- **M1 (ingest) done except tests:** `uv run python -m opscope.ingest.build` turns all 857 series into `cache/v1/{games,rounds,loadouts,engagements,casts,snapshots}.parquet` in ~4 min; `opscope.load.load()` returns them as DataFrames. All round counts match `meta/games.csv`.
- Ingest facts learned the hard way:
  - GRID rollbacks (`!` actions) are common (13k in VAL). They undo events newest-first with new ids; `feed.py` keeps an undo stack keyed by (type, actor id, target id).
  - Restored games contain bookkeeping rounds; `rounds.played` filters them out.
  - Positions on GRID events are periodic samples (~1–4 m error). Supplement positions are better for casts.
  - Side per round comes from the round segment at freeze end, not from `games.csv`.
- Ability classes live in `taxonomy.py` and are applied at load time (no rebuild needed).- **M2 (Operator profiler) first version works:** `analytics/operator.py` (Scope → OperatorReport), `maps.py` (data-drawn backdrop, spawns, aggression), `ui/{minimap,cards,filters}.py`, page `views/operator.py`, wired in `app.py` via `st.navigation`. Theme in `.streamlit/config.toml`.
  - Real findings: OXY holds C9's Op in 93 of 96 defense Op rounds; C9 Ops 30 of 80 Haven defense rounds but only 2 of 134 on Lotus.
  - Known weakness: "setup spot" = first live position seen for the holder (events only), often late in the round. The plant snapshot isn't used yet.
- Still open: synthetic-fixture tests for `ingest/feed.py` (a Junie task); M2 polish (setup heat/density, plant-snapshot positions, opponent filter check, Odin view); then M3 utility heatmaps.

## Working with Eli
CS student (cybersecurity, math minor), strong in Python and C#. Explain data/format decisions briefly; keep PRs and commits small.
