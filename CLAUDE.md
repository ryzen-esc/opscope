# OpScope — context for Claude Code

Eli's entry in the **Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026** (Devpost: cloud9.devpost.com),
**Category 1: VALORANT Tactical Scouting, Utility Placement & Operator Profiler**.
**Deadline: Jan 12, 2027, 11:00am PT** (aim to submit by Jan 9). Judging Jan 27–Feb 3, 2027.
Public repo: **https://github.com/ryzen-esc/opscope**.

## Where things stand (checkpoint: Nov 24, 2026)
- **Redesign in progress: a new web app replaces the Streamlit UI.** Analytics and numbers are unchanged, except one
  approved fix (Nov 24): `stats.wilson` is exact at k = 0 / k = n, which removed fake "0 of n vs typical 0%" findings
  (C9 unaffected; doc figures unchanged). 79 tests pass (`uv run pytest`). Everything up to the Nov 23 checkpoint is
  pushed; the Nov 24 review fixes (every commit after `ac0cce2`) are local only. Ask Eli before pushing anything new.
- **Plan** (approved by Eli; full text in `/Users/eli/.claude/plans/a-look-good-as-expressive-riddle-of-d17ce326-734c-4f59-8f9c-47ddc1d32f21.md`):
  1. ✅ Accurate maps (official minimap frame + traced minimaps). 2. ✅ JSON API + local server. 3. ✅ Overview story.
  4. ✅ Dashboard + Briefing tab. 5. ✅ Operator tab + round clock. 6. ✅ Utility tab.
  7. **Next:** Map pool tab (still a "soon" placeholder), How it works page (port `views/about.py`: pipeline numbers from
     `/api/meta`, evidence-bar anatomy, method, limits; the nav link is a placeholder), polish (loading/empty states, view
     transitions, narrower screens, keyboard help).
  8. Retire Streamlit: remove `app.py`, `views/`, Streamlit-only `ui/` code, `.streamlit/`, the dependency and
     `tests/test_app.py`; update `.run/` configs, README run steps (`uv run opscope`), METHODOLOGY references,
     `notes/DEMO_SCRIPT.md`, `SUBMISSION_CHECKLIST.md`, AI_SHOWCASE/DEVPOST tool lists, and this file. Then the final check.
- **Eli's review style:** he reviews each step in Chrome (`http://127.0.0.1:8000/…`) and sends screenshots of anything
  confusing. Every question so far was a real gap (see "Lessons" below); answer from the data, then offer the fix.
- **Left for Eli (`notes/SUBMISSION_CHECKLIST.md`):** play-test, screenshots (after the redesign), demo video from
  `notes/DEMO_SCRIPT.md` (needs rewriting for the new app), Devpost from `notes/DEVPOST.md`.
- **Before submitting:** fresh clone in the scratchpad → `uv sync` → `uv run pytest` → small build
  (`--series 2748746 --series 2972877`) → `uv run opscope` renders every view; re-check every number quoted in the docs.

## The product: new web app (what judges will see)
`uv run opscope` (`server.py`) serves `web/` and the JSON API on **127.0.0.1:8000** only and opens a browser. Preview
config `opscope-web` in `/Users/eli/hackathon/.claude/launch.json`. Plain HTML/CSS/ES modules, no build step; Lenis
(MIT) vendored in `web/vendor/`. State lives in the URL (`?team=79&view=dashboard&tab=operator&map=haven&side=defender…`).
- **Overview** (`web/js/overview.js`): hero dossier (name, record/win rates counting up, roster, most-played map drawing
  in, quick picks), then the top 3 game-plan items told over a sticky map that flies to each spot with its evidence bar,
  then plan items 4–8 as rows (they open that finding in the dashboard), then "Open the dashboard". Items are labelled
  "Plan 01…" to match the dashboard's PLAN tags.
- **Dashboard** (`dashboard.js` frame): tabs Briefing · Operator · Utility · Map pool (keys 1–4), map chips (badge = tendencies
  / gun rounds / casts per tab), a "Show" side toggle, a Filters drawer (opponents/event/patch: these recompute the numbers;
  a banner says so), left rail, centre map, floating card/live panel, bottom strip/timeline.
  - **Briefing** (`briefing.js`): every tendency, numbered by **rank** (`#1` = most unusual and best supported; ranks don't
    change when filtering); `PLAN 0N` tag = its number in the overview. Selecting (click/↑↓) flies the map and opens an
    evidence card with the game-plan advice (self-scout: tip only) and a link to the Operator/Utility tab with filters set.
    Findings with no single spot say so. Bottom strip: plant share per site vs the **typical team** (same as the findings).
  - **Operator** (`operator.js`): weapon switch, rate vs typical, rate by map (click to switch), who holds it, first-shot
    timing, full-buy wins with/without (95% ranges), survived (per distinct gun round), early setup on the selected map
    (`maps[m].aggression`: percentile = share of other teams' setups the median is further forward than, flipped for
    attack since aggression runs 0 = defender spawn to 1 = attacker spawn; None on both sides or < 8 setups). Map + **round clock** (`timeline.js`: play/drag/←→, 1×/2×/4×,
    Build up / Moment = last 5 s). A **dot is one recorded moment of the holder**: they dealt damage, took damage or used
    an ability (GRID has no missed shots or movement), with whatever was in hand; same-tick events are merged and listed
    (a trade shows both). Kill lines = kills with the gun (ring = shooter, ✕ = victim). The map **overlays every round by
    time in round**: each dot names its round ("Round 1 of 6 here · map round 5 vs X, date · lost"), hover lights the round
    up with a path, "Watch one round" / click plays a single round with a list of what GRID recorded; ‹ › or [ ] step.
    Amber notes: 0 gun rounds ("that absence is the finding") or < 8.
  - **Utility** (`utility.js`): type (traps default, recon, smokes, stalls, flashes, all), phase, Cast spot / Landing (est.),
    aim lines (on by default for thrown utility), habit rings (4 m spots; each ring is sized to hold every cast counted, ①②③, click to zoom), **player chips** (whole roster
    that played the map; players with none of that utility greyed "no smokes here"; names in "Who uses what" also filter),
    legend toggles (top 8 abilities coloured, rest grouped grey). Clock starts at −0:30 (buy phase ~28.5 s; earlier casts
    sit at the start, real time in the tooltip). Same round labels / hover / watch-one-round as Operator.
  - **Map pool**: placeholder ("soon").
- The **Streamlit app** (`app.py`, `views/`, `ui/`) still exists and works until step 8; don't spend effort on it.

## Lessons from Eli's reviews (keep doing these)
- Maps were mirrored: GRID x/y map to the minimap with axes swapped. Fixed with the valorant-api transform (see Design).
- Explain what a mark means on the page itself: rank vs plan numbers, filters vs view controls, "no single spot",
  what a dot is, why dots at the same time come from different rounds, why only 3 players show.
- Verify claims in the raw data before answering (e.g. the "kill + took damage" dot was a real trade at 0:08.9).

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
- **New web app look:** same dark tactical palette (`--def #00aeef`, `--atk #f2545b`, `--amb #f5b43c`), Big Shoulders
  Display headings, Inter body, JetBrains Mono numbers (Google Fonts). Time in round uses a cool ramp (light blue → purple),
  so red only means attack and kills. Evidence bar = `web/js/evidence.js`; map renderer = `web/js/map.js` (`drawMap`,
  `focus` with camera clamped inside the map, `pulse`, `highlightSite`, `findingAt`).
- **Legacy Streamlit code (until step 8):** `ui/theme.py` (palette, Plotly template `opscope`, `chart()` which must be used instead of `st.plotly_chart`
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
- **Figures quoted in the docs** (re-pull them if the data or method changes): C9 Op on Lotus defense 2 of 134 vs typical VCT 2025 team 8%; Haven 30 of 80 vs 19%; OXY 93 of 96 Op rounds; NRG Odin on Lotus defense 47 of 117 vs 11%; neT turret near Mid Boiler 25 of 26 vs typical Killjoy 64%; Viper wall typical = 100% (other 21 VCT 2025 Vipers); landing miss 21.3 m → 6.9 m on 171 held-out series; 13,255 rollbacks; 56 tests (now 79: update the docs in step 8).

## Data (GRID): hard rules
- Lives at `$STL_DATA_DIR` = `/Users/eli/hackathon/stl-hackathon-2026-grid-starter` (sparse: val, val-ability-supplements, meta), outside the repo. Read its `AGENTS.md`/README for the format.
- **Never copy, commit or redistribute the data** (or decompressed copies, extracts, caches). Stream `.zst` with `compression.zstd`; never decompress to disk. No real data in tests or Junie prompts (tests use synthetic fixtures).
- Before every commit/push: `git diff --cached --name-only | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb|png)$|cache/'` must print nothing. Never `git add` the cache.
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
- **New web app (redesign in progress, Nov 23):** `present.py` builds each page's JSON (report, operator, utility, meta, team filters; positions/kills/casts carry view-frame `at`, time `t` (negative = buy phase) and a round index for the timeline). `api.py` serves it (Starlette, gzip; list filters repeat the param, `side` = attacker/defender/both, default defender; missing cache → 503 with setup steps; `TrustedHostMiddleware`
answers only Host 127.0.0.1/localhost, against DNS rebinding, so tests use `base_url="http://127.0.0.1"`). Plan items
carry `index` = their finding's position in `insights` (findings can share map/side/category/k/n). `server.py`: `uv run opscope` serves `web/` + the API on 127.0.0.1:8000. Preview config `opscope-web`. Plan: overview story → dashboard with a scrubbable timeline; Streamlit is retired once the new site covers everything.
- `geometry.py`: the official minimap frame (`to_minimap`, `to_view`), traced minimap layers (`map_geometry`: floor rings, props, site zones, spawns, sites, callouts) with a data-drawn fallback. `maps.py`: old data-drawn backdrop (Streamlit), spawns, aggression. `ui/`: minimap layers, cards, sidebar filters.
- **Positions only exist at events** (dealing damage, taking damage, ability casts, plants; GRID has no missed shots or movement), ±1–4 m. Always state coverage ("seen in k of n rounds").

## Gotchas
- `df.map` is the DataFrame method: always write `df["map"]`.
- Web front end (`web/css/app.css`): every class is global. Names already used for page-level layout (`.bar` = top nav, `.soon` = full-screen placeholder, `.story` = overview scroll layout, `.stage`, `.step`, `.row`) have clashed three times with small components: grep the CSS before naming a class.
- Empty pandas frames: build boolean masks with an explicit `dtype=bool`.
- Streamlit multiselects keep stale values: key them by their context. `use_container_width` is deprecated; use `width="stretch"`.
- Library code under `src/` isn't hot-reloaded by Streamlit: restart the preview server after changing it.
- New web app: `uv run opscope` has no auto-reload. After changing `src/` (e.g. `present.py`, `api.py`), restart it
  (preview: `preview_stop` + `preview_start opscope-web`). Front-end files need only a reload (the server sends
  `Cache-Control: no-cache`). Payloads are `lru_cache`d per scope inside the process.
- Map geometry is cached as JSON in `cache/v1/geometry/` keyed by `GEOMETRY_VERSION`; bump it when the tracing or the
  payload changes. Minimap PNGs are in `cache/v1/minimaps/` (gitignored, never commit).
- Testing the front end from the preview pane: the pane is usually hidden, so animations stall; finish them with
  `document.getAnimations().forEach(a => a.finish())` before screenshots. Lenis fights `window.scrollTo`; real wheel
  scrolling works. Dispatch synthetic key events on `document.body`, not `document`.
- The preview server started from this app gets stopped when the app closes its Browser pane; if Eli says the page won't
  load, check `lsof -iTCP:8501` and restart it. Eli can also run `uv run streamlit run app.py` himself.
- Plotly needs `automargin` (set in the template) and maps use `constrain="domain"` so spawn badges never get clipped.
- Changing a widget's options can strand its session value; key widgets by their context (e.g. `report_map_{team_id}`,
  the Utility agents multiselect).
- The preview launch config lives at `/Users/eli/hackathon/.claude/launch.json` (name `opscope`, port 8501). PyCharm's "OpScope app" run config uses port 8502.

## Tools and workflow
- **Stack:** Python 3.14, uv, pandas 3, pyarrow, starlette + uvicorn (web app), pillow (minimap tracing), pytest + httpx2; plotly/streamlit until step 8. PyCharm project files are committed (`.idea/`: src = source root, cache excluded; shared run configs in `.run/`). Junie guidelines are in `.junie/guidelines.md`.
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
