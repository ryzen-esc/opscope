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
  - Positions are sparse: only events carry them, and the median first sighting of an Op holder is 32 s in. So the map shows a blurred density (3 m bins) of *all* holder positions, filtered by time bucket. "Early setup" = first position within 30 s, and coverage is always reported (e.g. 14 of 30 rounds).
  - Checked: opponent filter, Odin (NRG: s0m Omen / brawk Sova), C9 GC (marceline), attack side and empty scopes. Empty frames need explicit bool dtypes in pandas 3.
- **Tests:** `tests/` holds synthetic-fixture pytest tests for ingest (Junie drafted them, Claude reviewed and extended them); `uv run pytest` gives 8 passing. Rollback tests were mutation-checked.
- **PyCharm:** `.idea/` committed (src = source root, cache excluded); shared run configs in `.run/`. JetBrains AI Ultimate is active with data collection off. Workflow: JetBrains AI drafts small, well-specified tasks; Claude reviews and fixes; log both in `notes/AI_WORKFLOW_LOG.md`.
- **M3 (Utility profiler) first version works:** `analytics/utility.py` (UtilityScope → UtilityReport, with `repeat_spots` greedy 4 m clustering that counts rounds, not casts), page `views/utility.py`, and the minimap gained ability-colored points, aim arrows and numbered habit rings.
  - Real findings: neT's Viper puts Toxic Screen in the same spot in 70 of 71 Lotus defense rounds; neT's Deadlock sensor in 24 of 34.
  - Habit denominators are "rounds the player was on that agent" (from loadouts), not rounds they used the ability.
  - Gotcha: `df.map` is the DataFrame method, so always write `df["map"]`. Streamlit multiselects keep stale selections, so key them by their context.
- **M4 (Scouting report) first version works**, and it's now the app's front page (`views/report.py`): headline cards, ranked "Key tendencies", map pool, and a per-map breakdown (sites, plant split vs league, predictable utility).
  - `analytics/insights.py`: Insight objects from three sources (gun usage vs league, plant site vs league, utility habits vs a league habit baseline). Ranked by `surprise` = gap between the team's 95% Wilson interval and the league rate.
  - Lesson: habits need a league baseline. Without one, "Viper wall in the same spot 70/71" topped every report, but that's a standard lineup.
  - `zones.py` + `sites.yaml`: bomb sites found by k-means on planter positions (2 per map, 3 on Haven/Lotus). Names (A/B/C) come from matching each centre to the nearest "Site" callout from valorant-api.com (`/v1/maps` → `callouts`). That API uses **the same x/y as GRID** (identity transform; all matches within 20 m, next site 40+ m away). The same callouts (A Main, Mid Courtyard, …) could name any position. The YAML holds only centres, so it's safe to commit.
  - The first report load for a team takes ~3–12 s (league habit baselines), then it's cached.
- **Callouts:** `callouts.yaml` (346 named points on 16 maps, refreshed with `python -m opscope.zones --callouts`). `zones.nearest_callout(map, x, y)` names any position: within 8 m of a plant-derived site centre it's "A Site", else the nearest callout point (within 25 m). The letter is reliable; the exact area is a best guess near borders, because a callout is one point per area. Used in habit insights ("near B Main"), utility ring labels, report map labels, and Operator hover text plus an area summary.
- **M5 (anti-strat) works:** `analytics/antistrat.py` turns insights into suggestions. Opponent mode is "Game plan vs X", written from your side (their defense = your attack). Self-scout mode (C9 teams) is a "Predictability check". Rule-based; each suggestion cites its insight and sample. One suggestion per (map, side, category) so a single map can't fill the list. Gun insights now name where the gun sits early ("near B Site").
- **Speed:** league habit baselines are saved to `cache/v1/baselines/*.json` (computed by `--warm`, or automatically at the end of `ingest.build`, which clears stale ones). A C9 report went from 12 s to about 2 s cold.
- **Polish:** `views/about.py` ("How it works") explains method and limits, with live pipeline numbers from `ingest_report.json`. Keep its claims in sync when the method changes. `app.py` shows setup steps instead of crashing when the cache or `STL_DATA_DIR` is missing (covered by a headless `AppTest`). The sidebar footer shows the data scope. Stat values shrink with the window (no mid-word wraps).
- **Landing spots:** `analytics/landing.py`. Ground truth = victims of each damaging cast (23k casts paired to later damage by the same player and ability). Utility lands along the aim (sideways miss 2–3 m), so the model is the median distance along the aim per ability and 5° pitch bin. Held-out series: **6.9 m** typical miss vs **21.3 m** for the cast spot, 8.1 m for a fixed distance. Only the 12 damaging abilities it improves get estimates; smokes, alarmbots and cameras stay at the cast spot (nothing to validate against). Cached with its validation numbers in `cache/v1/baselines/landing_model_v1.json` (warmed by the build). Shown via the Utility page's "Where it lands (est.)" toggle (habits are then found on landings) and documented with the per-ability table on How it works.
- **M6 drafts done:** `README.md` (judge-facing), `METHODOLOGY.md`, `AI_SHOWCASE.md` (bonus prize, in Eli's voice), `notes/DEVPOST.md`, `notes/DEMO_SCRIPT.md`, `notes/SUBMISSION_CHECKLIST.md`. The judge path (fresh clone → `uv sync` → tests → build → all pages render) was verified. Numbers in the docs come from the current build; re-check them if the data or method changes.
- Left for Eli: screenshots, demo video, deciding further JetBrains AI use (update the tool lists), the Claude privacy opt-out, making the repo public, Devpost. Never push or publish without Eli's go-ahead.

## Working with Eli
CS student (cybersecurity, math minor), strong in Python and C#. Explain data/format decisions briefly; keep PRs and commits small.
