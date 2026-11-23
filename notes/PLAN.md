# OpScope — project plan

> **Original plan from Nov 23, 2026, kept for history.** Everything here was built (some designs changed, e.g. site names came from map callouts instead of manual labelling). Current status: `CLAUDE.md`.

## Context
OpScope is a hackathon entry for Cloud9 x JetBrains "Sky's The Limit" 2026, Category 1. Deadline: **Jan 12, 2027, 11am PT**. Today the repo is only a scaffold: a placeholder Streamlit page, `data.py` streaming helpers and `explore.py`.

**The goal:** a polished Streamlit scouting tool for Cloud9 coaches:
- an Operator profiler and utility heatmaps
- an opponent scouting report
- self-scouting of Cloud9

Every insight is visual and shows its sample size.

**Decisions made:**
- Load all 857 VAL series, default to **Cloud9 (team 79, VCT Americas 2025)**, and also support **Cloud9 GC (3429, GC NA 2026)**. The two rosters are kept as separate eras.
- The map backdrop is **drawn from the data**: a density layer of every recorded position on that map. No Riot art.
- **Streamlit**, polished, with Plotly charts.
- Full scope, sequenced so the core lands first and stretch goals come last. Pace the work to fit Max plan usage: no large multi-agent runs.

## What the data supports (verified on real feeds)
- **Loadouts.** At `round-ended-freezetime` (a full state) every player has `inventory.items`, `character`, `position`, `money` and `loadoutValue`. This is where Op, Odin, Outlaw and Marshal ownership per round comes from.
  - The `game-ended-round` full state has round-end inventories. Survivors keep their guns, so we can see Op carry-overs and saves.
- **No movement stream in GRID.** Positions only appear on the actor and target of damage, kill, ability, plant and defuse events, and they're **periodic samples** (median error about 1 m, p90 about 3–4 m).
  - So: bin at 3 m or more, and never infer an exact angle from a single point.
- **The plant full state** has all 10 positions, which gives a second snapshot per round.
- **Weapons.** Damage events: `actor.stateDelta.round.damageDealtSources[].source.name`. Kill events: `weaponKills`.
  - Spike pickups and drops are the only item events, so a **possession shift is inferred**: Op holders at freeze end vs round end, plus Op damage from a player who didn't own one.
- **Round time** = `occurredAt` − freeze-end. The game clock events aren't usable.
  - Buy-phase casts (negative time) matter: turrets, nanoswarms, alarmbots. Keep them, tagged `phase='buy'`.
  - The round-1 freeze can last 9+ minutes. Flag rounds that run long as `pause_suspect`.
- **Side per round:** read `segments[-1].teams[].side` at freeze end. Don't use the `games.csv` sides, which are the final round's side.
- **Map coordinates** are consistent across events (Lotus bounds are identical in 2025 and 2026). Spawns can be found from freeze-start positions.
- **Supplement.** It gives a precise 3D cast position and view vector. Drop `in_grid=false` casts, which are mostly between rounds.
  - All VCT Americas 2025 series (all of C9's VCT data) were recorded at 1 Hz, so cast positions there are less precise.
- **Volume** across 28 C9 series: C9 had an Op at freeze end in 102 rounds (OXY on Jett, 62 on defense), C9 GC in 78 (marceline). Opponents: MIBR 26, G2 24, EG 18, NRG 12, plus NRG's Odin in 29.

## Architecture
```
src/opscope/
  data.py                 (existing) streaming helpers: load_series, series_file, iter_events
  taxonomy.py             ability → util_class (trap / recon / smoke / stall / flash / other); weapon groups
  maps.py                 spawns per map, data-drawn backdrop, zones/*.yaml + point-in-polygon
  ingest/feed.py          one GRID series → tidy rows
  ingest/supplement.py    joins casts on grid_event_id
  ingest/build.py         parallel build to cache/v{N}/{table}/{series}.parquet; skips series already built; writes ingest_report.json
  analytics/operator.py   possession, holders, time buckets, setups, sightlines, aggression, shifts, win rate
  analytics/utility.py    heatmap aggregates, buy-phase setups, timing
  analytics/baseline.py   league baselines per map/side/time bucket
  analytics/insights.py   insight cards: n-of-N, Wilson interval, vs-league delta, hide when n < 8
  ui/minimap.py           Plotly map: backdrop + density + sightlines + points
  ui/cards.py             insight card component, sample-size badge
app.py + pages/           Scouting report (opponent or self) · Operator profiler · Utility · About/Methodology
tests/                    pytest with synthetic fixtures only (never real data)
```

**Cached tables** (all IDs are strings, times in float seconds from freeze end):
- `games`: series, game, map, patch, teams, winner, session_valid, tier (vct/gc), low_rate, bounds
- `rounds`: game, round_num, freeze-end/won/end times, atk/def team, winner, win_type, plant_t, pause_suspect, buy type per side (eco/force/full from loadoutValue)
- `loadouts` (player × round): agent, primary at freeze end and at round end, alive at end, money, loadout value
- `engagements`: event id, game, round, t, kind (dmg/kill), actor/target id, team, side, weapon, damage, actor and target x/y
- `casts`: event id, game, round, t, phase, player, team, side, agent, ability, slot, util_class, x/y/z, view, position source, quality
- `snapshots`: game, round, moment (freeze start/end, plant), player, alive, x/y

**Validity rules:**
- Keep only `game_id`s listed in `meta/games.csv` with `session_valid`.
- Check that rounds per game = sum of the two scores.
- Exclude the merged-map games (series 2890334 and 2890361).
- Count any `!` rollback events in the ingest report.

## Milestones
| # | Dates | Deliverable |
|---|---|---|
| M1 | Nov 24–30 | **Ingest and cache.** taxonomy.py, ingest/*, synthetic fixtures + tests, full corpus build (about 2–3 min in parallel), ingest_report. Add `pyarrow` and a pytest dev group to pyproject. Open in PyCharm so `.idea/` exists and gets committed. |
| M2 | Dec 1–9 | **Operator profiler** (the core "wow" insight): holder share by player/agent/side; time buckets 0–20/20–40/40–60/60+ s; setup spots (earliest live position, with coverage "seen in X of Y"); **sightline lines** shooter → victim; aggression = d_def/(d_def+d_atk) ranked against the league; possession shifts and Op saves; win rate on full buys only. The minimap component and data-drawn backdrop land here. |
| M3 | Dec 10–17 | **Utility heatmaps**: priority on placeable utility, then recon, smokes, stall, flashes; buy-phase setup map per site; cast position + aim arrow; filters by ability, agent, player, side, time bucket. |
| M4 | Dec 18–28 | **Scouting report page** (pick opponent or C9 → top insight cards with n-of-N, Wilson CI and league delta) using global filters (team, opponent, map, player, agent, patch, side, weapon, ability, event). Named zones YAML for the maps C9 plays most (Lotus, Haven, Pearl, Icebox, Ascent, Fracture, Corrode) so cards say "A Main", not coordinates. |
| M5 | Dec 29–Jan 4 | **Anti-strat suggestions** (rule-based off insights, e.g. "NRG's Odin holds B Main in 9 of 12 defense rounds → default A") and polish (theme, empty states, loading, performance). Stretch: estimated landing spots for short throws (alarmbot, turret, nanoswarm, trapwire). |
| M6 | Jan 5–9 | README run steps, METHODOLOGY.md, `notes/AI_WORKFLOW_LOG.md` → AI_SHOWCASE.md, Devpost text (JetBrains tools + what each did), demo video under 3 min. Submit by Jan 9; Jan 10–12 is buffer. |

**JetBrains / Junie showcase** (about 35 credits a month):
1. Synthetic fixture generator + ingest tests (M1)
2. The insight-card engine, built test-first (M4)
3. Zone YAML + labelling helper page (M4)
4. The minimap component (M2)

Log every notable AI session as we go (prompt, diff, test result). Keep licensed data out of Junie prompts; `.junie/guidelines.md` already states the rules.

## M1 in detail (first implementation step after approval)
1. `pyproject.toml`: add `pyarrow`, plus `[dependency-groups] dev = ["pytest"]`; run `uv sync`.
2. `taxonomy.py`: ability id → util_class for every `player-used-ability` target id in the corpus (pull the distinct ids from the cache once it's built, then fill in the mapping); weapon groups.
3. `ingest/feed.py`: walk a series once, tracking the current game and round. Emit rounds, loadouts and snapshots from the full-state events, and engagements and casts from player events. Reuse `iter_events` from `data.py`, but it needs to yield the envelope's `occurredAt` too: change it to yield `(occurred_at, event)`, or add `iter_envelopes`.
4. `ingest/supplement.py`: read `{sid}.jsonl.zst`, keep `in_grid`, index by `grid_event_id`, overwrite the cast position and view. Use whichever frame is close for `gap_exceeded` casts.
5. `ingest/build.py`: `ProcessPoolExecutor` over series.csv, writing parquet per series to `cache/v1/...`, then `ingest_report.json` (counts, validity failures, rollbacks). CLI: `uv run python -m opscope.ingest.build [--series ID] [--force]`.
6. `opscope.load` helper: reads the cache into pandas, joined with `meta/` names.
7. `tests/`: synthetic envelope builder; tests for side per round, round time incl. buy phase, Op detection at freeze and round end, supplement join, validity filtering.
8. Before every commit, check that no data is staged: `git diff --cached --name-only | grep -Ei '\.(zst|jsonl|parquet)$'`.

## Verification
- `uv run pytest`: all ingest tests pass on synthetic fixtures.
- `uv run python -m opscope.ingest.build` finishes on all 857 series. ingest_report shows no unexpected failures, and the rounds per game match `meta/games.csv` scores.
- Spot check against known numbers: C9 Op at freeze end = 102 rounds, OXY on Jett = 62 defense rounds; C9 GC = 78.
- After each milestone: `uv run streamlit run app.py`, check the page in the browser pane (filters, sample-size badges, both C9 eras), and take a screenshot for the log.
- Before each push: `git ls-files | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$'` prints nothing.
