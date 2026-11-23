# OpScope — context for Claude Code

Eli's entry in the **Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026** (Devpost: cloud9.devpost.com),
**Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler**.
**Deadline: Jan 12, 2027, 11:00am PT** (aim to submit by Jan 9). Judging Jan 27–Feb 3, 2027.
Public repo: **https://github.com/ryzen-esc/opscope**.

## Where things stand (updated Nov 23, 2026)
- **All features and docs are done, reviewed and published.** 44 tests pass (`uv run pytest`).
- **Left (Eli's tasks, see `notes/SUBMISSION_CHECKLIST.md`):**
  - Eli's play-test.
  - Screenshots into `docs/screenshots/` (then add them to the README; there's a placeholder comment near its top).
  - Demo video from `notes/DEMO_SCRIPT.md`, uploaded to YouTube as public.
  - Devpost submission from `notes/DEVPOST.md`.
  - Optional: more JetBrains AI use, then update the tool lists in README + DEVPOST.
- **Done:** AI training opt-out for both JetBrains AI and Claude; repo public; README clone URL set.
- **Before submitting:** run the final check. Fresh clone in the scratchpad → `uv sync` → `uv run pytest` → small build (`--series 2748746 --series 2972877`) → render all pages with `streamlit.testing.v1.AppTest`. Also re-check every number quoted in the docs against the app.

## The product (what judges see)
Streamlit app (`app.py` → pages in `views/`):
- **Scouting report** (front page): roster as of the team's last match; "Game plan vs X" (or a "Predictability check" for Cloud9 teams); ranked key tendencies; map pool; per-map breakdown (plant sites, predictable utility).
- **Operator profiler:** Operator/Odin/Outlaw/Marshal. Who holds it, rate per map/side vs the typical team, position density by time window, kill sightlines, first-shot timing, pickups, full-buy win rates, setup style.
- **Utility profiler:** casts by class and phase, habit spots (same spot within 4 m), aim arrows, and validated landing estimates for 12 damaging abilities.
- **How it works:** the method and its limits, with live pipeline numbers.

Judging (equal weight): technical implementation (incl. depth of JetBrains tool use), design (complete product), impact, idea, and presentation (demo under 3 min). Bonus $1k: "Best AI-Powered Workflow Story", covered by `AI_SHOWCASE.md` (+ the dated log in `notes/AI_WORKFLOW_LOG.md`).

## Docs in the repo (keep them consistent with the code)
- `README.md`: judge-facing (what it does, findings, run steps, JetBrains tools, credits).
- `METHODOLOGY.md`: full method + validation + limits. `views/about.py` is the in-app short version.
- `AI_SHOWCASE.md`: the AI workflow story, written in Eli's voice. `notes/AI_WORKFLOW_LOG.md`: add a row for each notable AI step.
- `notes/`: `PLAN.md` (original roadmap M1–M6), `DEVPOST.md`, `DEMO_SCRIPT.md`, `SUBMISSION_CHECKLIST.md`.
- **Figures quoted in the docs** (re-pull them if the data or method changes): C9 Op on Lotus defense 2 of 134 vs typical VCT 2025 team 8%; Haven 30 of 80 vs 19%; OXY 93 of 96 Op rounds; NRG Odin on Lotus defense 47 of 117 vs 11%; neT turret near Mid Boiler 25 of 26 vs typical Killjoy 64%; Viper wall typical = 100% (other 21 VCT 2025 Vipers); landing miss 21.3 m → 6.9 m on 171 held-out series; 13,255 rollbacks; 44 tests.

## Data (GRID): hard rules
- Lives at `$STL_DATA_DIR` = `/Users/eli/hackathon/stl-hackathon-2026-grid-starter` (sparse: val, val-ability-supplements, meta), outside the repo. Read its `AGENTS.md`/README for the format.
- **Never copy, commit or redistribute the data** (or decompressed copies, extracts, caches). Stream `.zst` with `compression.zstd`; never decompress to disk. No real data in tests or Junie prompts (tests use synthetic fixtures).
- Before every commit/push: `git diff --cached --name-only | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$|cache/'` must print nothing. Never `git add` the cache.
- Committed derived files are aggregate only: `src/opscope/sites.yaml` (site centres) and `src/opscope/callouts.yaml` (community callouts from valorant-api.com).
- Track teams/players by **ID**, never by name. Times are UTC.

## How the code works (`src/opscope/`)
- `data.py`: streaming readers. `ingest/feed.py`: `SeriesParser`, one pass per series.
  - **GRID rollbacks** (`!` actions, 13k in VAL) undo events newest-first with new IDs. Handled with an undo stack keyed by (type, actor, target).
  - A cancelled map start drops its rows; restored maps' bookkeeping rounds are excluded via `rounds.played`.
  - Side per round comes from the round segment at freeze end.
- `ingest/supplement.py` joins precise cast positions. `ingest/build.py` builds the parallel cache → `cache/v1/*.parquet` (~4 min). The report merges per series across runs, then precomputes baselines (`cache/v1/baselines/`).
- `load.py`: `load()` → DataFrames with `map, patch, tier, event, season, cohort, started_at` attached. `cohort` = tier-season (`vct-2025`, `gc-2025`, `gc-2026`); `peer_group()` names it in sentences.
- `analytics/`:
  - `operator.py`: Scope, `team_rounds()`, `league_scope`, `season_weighted_rate`, OperatorReport.
  - `utility.py`: habits via `repeat_spots`, 4 m, counted in rounds on the agent.
  - `insights.py`: gun/plant/habit insights, ranked by `surprise` = gap between the team's Wilson 95% interval and the comparison rate.
  - `antistrat.py`: game plan + predictability check; skips former players.
  - `landing.py`: validated landing model. `roster.py`: rosters per event and departed flags. `stats.py`: Wilson, `typical_rate`.
- **Comparison rule:** a team is compared with the **typical other team** (median of per-team rates, 16+ rounds, at least 4 teams, else pooled) in the **same tier and season**. Multi-season teams are compared season by season, weighted by rounds. The habit baseline = median same-spot share of **other teams'** players, following the Patch/Event filters.
- `zones.py`: bomb sites (k-means on 28,952 plants) + `nearest_callout` (a site centre within 8 m wins, else the nearest callout within 25 m). valorant-api.com uses the **same x/y as GRID**.
- `maps.py`: data-drawn backdrop (no Riot art), spawns, aggression. `ui/`: minimap layers, cards, sidebar filters.
- **Positions only exist at events** (shots, hits, casts, plants), ±1–4 m. Always state coverage ("seen in k of n rounds").

## Gotchas
- `df.map` is the DataFrame method: always write `df["map"]`.
- Empty pandas frames: build boolean masks with an explicit `dtype=bool`.
- Streamlit multiselects keep stale values: key them by their context. `use_container_width` is deprecated; use `width="stretch"`.
- Library code under `src/` isn't hot-reloaded by Streamlit: restart the preview server after changing it.
- The preview launch config lives at `/Users/eli/hackathon/.claude/launch.json` (name `opscope`, port 8501). PyCharm's "OpScope app" run config uses port 8502.

## Tools and workflow
- **Stack:** Python 3.14, uv, pandas 3, plotly, streamlit, pyarrow, pytest. PyCharm project files are committed (`.idea/`: src = source root, cache excluded; shared run configs in `.run/`). Junie guidelines are in `.junie/guidelines.md`.
- **JetBrains AI Ultimate** is active until Jan 22, 2027, with detailed data collection **off** (decline any consent prompt). Junie (Code mode) edits and runs code; AI Assistant "Chat" mode can't touch files.
- **Division of labour:** JetBrains AI drafts small, well-specified showcase tasks (tests, commit messages, docs); Claude Code reviews and fixes them critically; core analytics stay with Claude. Log both honestly in `notes/AI_WORKFLOW_LOG.md`.
- **Git:**
  - Commit identity for this repo is `Eli Claros <80992499+ryzen-esc@users.noreply.github.com>` (already set in the local git config). Keep the school email out of commits.
  - `gh` is logged in as `ryzen-esc`.
  - Ask Eli before pushing anything new or making public changes, unless he has asked for it.
  - A local branch `backup-before-email-rewrite` holds the old-email history. **Never push it.**

## Working with Eli
CS student (cybersecurity, math minor), strong in Python and C#, plays VALORANT, and his game knowledge has caught real mistakes (turrets do deal damage; fair comparisons across tiers and rosters). Explain data and format decisions briefly, check claims against the data before stating them, and keep commits focused.
