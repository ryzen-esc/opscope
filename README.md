# OpScope

**Scouting reports for VALORANT coaches, built from every recorded event of 2,079 pro maps.**
Built for the Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026, Category 1 (Tactical Scouting, Utility Placement & Operator Profiler).

Coaches spend hours scrubbing VODs to answer questions like *"Who holds the Op on their Haven defense, and where?"* or *"Where does their Killjoy put her nanoswarm?"*. OpScope answers them in seconds, and every answer shows its evidence: **"30 of 80 defense rounds"**, compared with other teams in the same tier and season.

<!-- Screenshots: add docs/screenshots/report.png, operator.png, utility.png (see notes/SUBMISSION_CHECKLIST.md) -->

## What it does

| Page | What a coach gets |
|---|---|
| **Scouting report** | Pick an opponent and get a **game plan**: counters to their most unusual tendencies, each citing its sample. Then ranked key tendencies, the map pool, and a per-map breakdown of where they plant and which utility they place predictably. Pick Cloud9 and the same page becomes a **predictability check**: what an opponent scouting Cloud9 would see. |
| **Operator profiler** | Who buys the Operator (or Odin, Outlaw, Marshal), how often per map and side vs the league, where the holder sits by time in the round, kill sightlines, when it first fires, whether it changes hands, and full-buy win rate with and without it. |
| **Utility profiler** | Where traps, recon, smokes, stalls and flashes are cast, before or during the round. **Habit spots** are utility a player puts in the same place round after round. For mollies, nanoswarms and other damaging utility, it shows a **validated estimate of where it lands**. |
| **How it works** | The method and its limits, in plain language, with live pipeline numbers. |

Filters for team, opponent, map, side, patch and event apply everywhere. Each team is compared only with teams in its own **tier and season** (e.g. VCT 2025), and the report shows the team's latest roster in the data, marking tendencies of players who later left. Map areas are named the way players say them ("near B Main", "C Site").

### A few things it found

- **Cloud9 (VCT Americas 2025)** ran an Operator in **30 of 80** Haven defense rounds but only **2 of 134** on Lotus, their most-played map (typical VCT 2025 team: 8% on Lotus). OXY held it in 93 of their 96 Op rounds.
- **NRG** brought an **Odin** in **47 of 117** Lotus defense rounds, against 11% for the typical VCT 2025 team. It was usually s0m on Omen (41 of 47), and early in the round the gun was seen near **A Door** in 32 of the 45 rounds where its holder showed up.
- Habits are compared with other players. neT's Viper wall goes up from the same spot in 70 of 71 rounds, but so does the typical Viper's (a standard lineup), so OpScope doesn't flag it. It does flag neT's Killjoy turret near Mid Boiler on Icebox defense: the same spot in 25 of 26 rounds, where the typical VCT 2025 Killjoy is at 64%.

## Run it

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/). The match data is licensed for the hackathon and **is not in this repository**; you clone it yourself next to this project.

```bash
git clone <this repo> opscope
git clone --filter=blob:none --sparse https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git
cd stl-hackathon-2026-grid-starter && git sparse-checkout set val val-ability-supplements meta && cd ..
cd opscope
cp .env.example .env                       # set STL_DATA_DIR to the data clone's full path
uv sync
uv run python -m opscope.ingest.build      # ~4 min on 10 cores: builds the local cache in cache/ (gitignored)
uv run streamlit run app.py                # opens http://localhost:8501
```

If you open the app before building the cache, it shows these steps instead of an error.

**Tests:** `uv run pytest` (44 tests). They use synthetic GRID events; the page smoke test is skipped when no cache exists.

In **PyCharm**, the shared run configurations in `.run/` (OpScope app, Build cache, Tests, Explore data) appear automatically.

## How it's built

```
src/opscope/
  ingest/      stream each GRID series (zstd, never decompressed to disk) into parquet tables;
               replays GRID's rollback events so every map matches its official score
  analytics/   operator · utility · insights (league comparison + ranking) · antistrat · landing
  zones.py     bomb sites from 29k plant positions; area names from map callouts
  ui/          data-drawn minimap (no Riot art), cards, shared filters
views/         Streamlit pages
tests/         pytest, synthetic fixtures only
```

The full method, validation numbers and limits are in **[METHODOLOGY.md](METHODOLOGY.md)**. How the AI tools were used is in **[AI_SHOWCASE.md](AI_SHOWCASE.md)**.

## JetBrains tools

- **PyCharm Professional:** the IDE for the whole project. The project setup (`.idea/`: `src` as source root, the cache excluded from indexing), shared run configurations (`.run/`), and the pytest runner.
- **Junie:** drafted the synthetic GRID fixtures and the first ingest test suite in Code mode, and fixed its own failing import. The draft was then reviewed and extended (see AI_SHOWCASE.md).
- **JetBrains AI Assistant:** set up with detailed data collection **off**, as the data license requires.

## Data and credits

Uses official GRID esports data provided for the hackathon (© GRID eSports GmbH and Riot Games, Inc.; ability supplement © Cloud9 Esports, Inc.). The data is not included or redistributed.
Map callout names and positions (`src/opscope/callouts.yaml`) come from the community API at [valorant-api.com](https://valorant-api.com), which uses the same coordinate system as GRID. Bomb-site centres (`src/opscope/sites.yaml`) are averaged from plant positions and contain no match data.
Maps are drawn from recorded player positions; no Riot art is used. OpScope is not endorsed by Riot Games.

Built with Python, pandas, Plotly and Streamlit, using PyCharm, Junie, JetBrains AI Assistant and Claude Code.

## License

MIT
