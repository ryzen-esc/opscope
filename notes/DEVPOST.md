# Devpost draft: OpScope

> Paste each section into the matching Devpost field. Numbers come from the current build; re-check them if the data or method changes.

**Tagline:** Scouting reports for VALORANT coaches. Every tendency comes with the rounds behind it and the league rate beside it.

## Inspiration
Scouting a VALORANT opponent means hours of VOD review to answer simple questions: who holds the Op on their Haven defense, where does their Killjoy put her nanoswarm, which site do they finish on? GRID's event data records all of it. It just needed to be turned into answers a coach can trust at a glance.

## What it does
OpScope reads every recorded event from 2,079 pro maps (3.5M events) and builds:
- **Scouting report:** pick an opponent and get a **game plan**. These are counters to their most unusual tendencies, written from your side ("Expect Odin spam near A Door when you attack Lotus: they bring an Odin in 47 of 117 defense rounds; typical VCT 2025 team: 11%"). Then ranked key tendencies, the map pool, and a per-map breakdown of plant sites and predictable utility. Pick Cloud9 and it becomes a **predictability check**: what opponents scouting Cloud9 would see.
- **Operator profiler:** who buys the Op/Odin/Outlaw/Marshal, how often vs the league, where the holder sits by time in the round, kill sightlines, timing, pickups, and full-buy win rates.
- **Utility profiler:** where traps, recon, smokes, stalls and flashes go, before or during the round. **Habit spots** a player reuses round after round, and **validated landing estimates** for damaging utility.

Every number shows its sample ("30 of 80 rounds"). Teams are compared only with teams in the same tier and season, and tendencies appear only when the team's 95% range clears that rate. Players who later left the roster are flagged, and map areas are named the way players say them ("near B Main").

## How we built it
- **Pipeline:** Python 3.14 streams the compressed GRID feeds (never decompressed to disk) into a parquet cache in about 4 minutes. The parser replays GRID's 13,255 rollback events, so every map matches its official score.
- **Analytics** (pandas):
  - league comparisons with Wilson intervals
  - habit clustering with a per-ability league baseline
  - bomb sites from clustering 28,952 plant positions
  - area names from community callouts, verified to share GRID's coordinates
  - a landing-spot model validated on held-out matches
- **UI:** Streamlit + Plotly, with a minimap drawn from 1.4M recorded positions (no Riot art).
- **Tests:** 40, using synthetic events, including mutation-checked rollback tests and a headless render of every page.
- **Tools:** built in **PyCharm** with **Junie**, **JetBrains AI Assistant** and **Claude Code**. See "JetBrains tools" below and AI_SHOWCASE.md.

## Challenges we ran into
- **Silent data errors:** 35 maps came out one round long until we found that GRID corrects itself with rollback events (undo newest-first, new IDs).
- **Sparse positions:** positions only exist when a player shoots, gets hit or uses an ability, so every map view states how many rounds it covers.
- **Fair comparisons:** VCT 2025 and Game Changers 2026 play different metas, and rosters change mid-season. Comparisons are now within tier and season, and tendencies of departed players are flagged.
- **"True but useless" insights:** a Viper wall placed in the same spot in 70 of 71 rounds is standard play. Habits had to be compared with the league too.
- **No landing data:** we built ground truth from who damaging utility hurt, and only ship estimates where that check exists.

## Accomplishments that we're proud of
- Landing estimates cut the typical miss from **21.3 m to 6.9 m** on 171 held-out matches.
- Bomb-site names matched to official callouts on all 13 maps, each within 20 m, with the next site 40+ m away.
- Real, specific findings, e.g. Cloud9 ran an Op in 30 of 80 Haven defense rounds but 2 of 134 on Lotus.
- A methodology page in the app that says plainly what the data can't do.

## What we learned
Validation is the feature. Every time we checked output against something independent (official scores, held-out matches, a second data source, a player's knowledge), it caught a mistake that looked fine.

## What's next for OpScope
- Round-by-round timelines (first contact, rotations)
- Composition-aware filters
- Exporting a one-page PDF game plan for match day
- Live updates as new matches arrive

## JetBrains tools used (required)
- **PyCharm Professional:** the IDE for the whole project. The project setup (`src` as source root, the data cache excluded from indexing), shared run configurations in `.run/` (app, cache build, tests), and the pytest runner.
- **Junie:** drafted the synthetic GRID test fixtures and the first ingest test suite in Code mode, and fixed its own failing import; the draft was then reviewed and extended.
- **JetBrains AI Assistant:** set up with detailed data collection off, as the data license requires. *(Eli: add anything else you use it for before submitting, e.g. commit messages or docs.)*
- *(Eli: add JetBrains Air only if you actually use it.)*

**Built with:** python, pandas, plotly, streamlit, pyarrow, pycharm, junie, jetbrains-ai-assistant, claude-code
