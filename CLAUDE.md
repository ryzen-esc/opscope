# OpScope — context for Claude Code

Eli's entry in the **Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026** (Devpost: cloud9.devpost.com),
**Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler**.
**Deadline: Jan 12, 2027, 11:00am PT** (aim to submit by Jan 9). Judging Jan 27–Feb 3, 2027.
Public repo: **https://github.com/ryzen-esc/opscope**.

## Where things stand (updated Nov 23, 2026, evening)
- **All features and docs are done, reviewed and published.** 44 tests pass (`uv run pytest`).
- **Design pass in progress** (Nov 23). Done and committed locally, **10 commits NOT pushed yet** (incl. this CLAUDE.md update) (`main` is ahead of
  `origin/main`). Ask Eli before pushing.
  - **Eli is reviewing the new Briefing report.** Next proposed step (waiting on Eli): give the Operator and Utility pages
    the same "briefing" treatment (their right-hand rails still show a lot at once).
  - Not visually verified: the branded loading screen (`SPLASH_HTML`); data loads in <1 s so it barely shows.
- **Left (Eli's tasks, see `notes/SUBMISSION_CHECKLIST.md`):**
  - Eli's play-test.
  - Screenshots into `docs/screenshots/` (then add them to the README; there's a placeholder comment near its top).
    Take them after the design pass settles.
  - Demo video from `notes/DEMO_SCRIPT.md` (on-screen cues updated for the new layout), uploaded to YouTube as public.
  - Devpost submission from `notes/DEVPOST.md`.
  - Optional: more JetBrains AI use, then update the tool lists in README + DEVPOST.
- **Done:** AI training opt-out for both JetBrains AI and Claude; repo public; README clone URL set.
- **Before submitting:** run the final check. Fresh clone in the scratchpad → `uv sync` → `uv run pytest` → small build (`--series 2748746 --series 2972877`) → render all pages with `streamlit.testing.v1.AppTest`. Also re-check every number quoted in the docs against the app.

## The product (what judges see)
Streamlit app (`app.py` → pages in `views/`, page tabs in the top bar, filters in the sidebar):
- **Scouting report** (front page), a one-screen **briefing**: quick-pick teams (Cloud9 self-scout, NRG, Sentinels, G2,
  Cloud9 GC); dossier header (team, roster chips, record, attack/defense win rates); **"3 things to know about X"**
  (Cloud9: "3 habits most worth varying"), each with rate, advice, evidence bar and a "View the …" link; the rest of the
  game plan as one-line rows that expand on click; then **Details** tabs: all tendencies, map breakdown (plant sites,
  predictable utility, tendency counts per map), map pool. The Side filter is greyed out here (the report covers both sides).
- **Operator profiler:** Operator/Odin/Outlaw/Marshal. Map-first layout: one control bar (weapon, map, time in round,
  kill lines), map on the left with a key above it (dots = holder positions, ring→✕ lines = kills, filtered by the same
  time window), "At a glance" rail on the right (who holds it, rate vs typical team, full-buy win rates, first-shot timing),
  rate by map below. Amber note under 8 gun rounds, or when a map has none ("that absence is the finding").
- **Utility profiler:** casts by class and phase, habit spots (same spot within 4 m), aim arrows, and validated landing
  estimates for 12 damaging abilities. Same map-first layout; view toggle "Cast spot / Landing (est.)".
- **How it works:** five-step pipeline (read, correct, rebuild, compare, show) with live numbers, a labelled example of the
  evidence bar, then the method and its limits.

## Design (Nov 23 design pass)
- **Style:** "tactical dossier", chosen by Eli from mockups: dark navy (`#0b0f14`), cyan accent `#00AEEF` (= defense),
  red = attack, amber = "pay attention"; Chakra Petch headings, Inter body, JetBrains Mono numbers (Google Fonts via
  `.streamlit/config.toml`); cut-corner panels; reticle logo (`assets/opscope-icon.svg`).
- **Signature:** the **evidence bar** on every finding: the team's rate, its Wilson 95% range (shaded) and a grey tick for
  the typical team. Category labels shown to users: Gun choice / Utility habit / Plant site (internal: Operator/Utility/Attack).
- **Layout chosen by Eli:** "Briefing" (key insight first, details on demand), over tabbed / map board / ranked feed.
- **No Riot art, except traced minimaps.** Eli asked for official agent icons and VALORANT backgrounds, then dropped the
  idea: the hackathon rules bar third-party copyrighted material without permission and require compliance with Riot's
  developer policies, which allow game assets only from Riot's own sources in products registered on the Developer
  Portal. Don't re-add icons, splash art or logos without written permission.
  - **Minimaps (Eli's decision, Nov 23, after being told the risk):** map outlines are traced from the official minimap
    images (valorant-api.com `displayIcon`). `geometry.py` downloads them on first use into `cache/v1/minimaps/`
    (gitignored) and traces floor, walls, props and plant-site zones into vectors in `cache/v1/geometry/`. Never commit
    the images or the traced vectors. Offline, it falls back to outlines drawn from precise match positions.
- **Map frame:** GRID x/y map onto the official minimap with x and y swapped (`u = y·x_mult + x_add`,
  `v = x·y_mult + y_add`, constants in `src/opscope/minimaps.yaml`). The old plots (x right, y up) were mirrored. Every
  layer must go through `geometry.to_view()`, which also turns each map so attackers start at the bottom.
- **Code:** `ui/theme.py` (palette, Plotly template `opscope`, `chart()` which must be used instead of `st.plotly_chart`
  because Streamlit's chart theme overrides the template, `count_axis()` for whole-number axes); `ui/brand.py` (icon,
  wordmark, splash); `ui/cards.py` (all CSS, `evidence_bar`, `brief_card`, `plan_rows`, `dossier_header`, `page_header`,
  `insight_card`, `rate_card`, `map_key`, `pipeline`, `evidence_anatomy`); `ui/links.py` ("View the …" links: a button
  callback sets the target page's widget keys (`side`, `weapon`, `op_map`, `util_class`, `util_phase`, `util_map`,
  `report_map_{team_id}`) plus a pending page, and the report calls `follow_link()` at its top to `st.switch_page`);
  `ui/filters.py` (`sidebar(side_applies=)`, `quick_picks`); `ui/minimap.py` (smoothed floor + wall outlines, ATK/DEF
  badges, `add_sites` with A/B/C letters, kill lines with shooter ring).

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
- Committed derived files are aggregate only: `src/opscope/sites.yaml` (site centres), `src/opscope/callouts.yaml` (community callouts from valorant-api.com) and `src/opscope/minimaps.yaml` (public minimap transforms).
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
- **New web app (redesign in progress, Nov 23):** `present.py` builds each page's JSON (report, operator, utility, meta, team filters; positions/kills/casts carry view-frame `at`, time `t` (negative = buy phase) and a round index for the timeline). `api.py` serves it (Starlette, gzip; list filters repeat the param, `side` = attacker/defender/both; missing cache → 503 with setup steps). `server.py`: `uv run opscope` serves `web/` + the API on 127.0.0.1:8000. Preview config `opscope-web`. Plan: overview story → dashboard with a scrubbable timeline; Streamlit is retired once the new site covers everything.
- `geometry.py`: the official minimap frame (`to_minimap`, `to_view`), traced minimap layers (`map_geometry`: floor rings, props, site zones, spawns, sites, callouts) with a data-drawn fallback. `maps.py`: old data-drawn backdrop (Streamlit), spawns, aggression. `ui/`: minimap layers, cards, sidebar filters.
- **Positions only exist at events** (shots, hits, casts, plants), ±1–4 m. Always state coverage ("seen in k of n rounds").

## Gotchas
- `df.map` is the DataFrame method: always write `df["map"]`.
- Empty pandas frames: build boolean masks with an explicit `dtype=bool`.
- Streamlit multiselects keep stale values: key them by their context. `use_container_width` is deprecated; use `width="stretch"`.
- Library code under `src/` isn't hot-reloaded by Streamlit: restart the preview server after changing it.
- The preview server started from this app gets stopped when the app closes its Browser pane; if Eli says the page won't
  load, check `lsof -iTCP:8501` and restart it. Eli can also run `uv run streamlit run app.py` himself.
- Plotly needs `automargin` (set in the template) and maps use `constrain="domain"` so spawn badges never get clipped.
- Changing a widget's options can strand its session value; key widgets by their context (e.g. `report_map_{team_id}`,
  the Utility agents multiselect).
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

For design work, Eli likes to pick from 3–4 concrete options shown as mockups, then review the built result in Chrome and
send screenshots of anything confusing. His first-look feedback has caught real problems (kill lines not following the
time filter, empty-looking map panels, repeated findings, "too much information"), so treat "this is confusing" as a bug
report: find the cause, fix it, and make the page explain itself.
