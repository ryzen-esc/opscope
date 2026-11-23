# AI-powered workflow: how OpScope was built

OpScope was built by one person working with three AI tools, each in its own role:

| Tool | Role |
|---|---|
| **Claude Code** (in the Claude desktop app, with a built-in browser) | The main engineer. It planned the project, wrote the data pipeline and analytics, and checked its own work by running code against the real data, writing tests, and opening every page in a browser. |
| **Junie** (PyCharm, Code mode) | Drafted well-specified pieces: the synthetic test fixtures and the first ingest test suite. |
| **JetBrains AI Assistant** (PyCharm) | IDE-side help, set up with detailed data collection off. |
| **Me** | Direction, VALORANT knowledge, and review: choosing what to build, challenging claims, and steering toward what a coach needs. |

The rule that made it work: **AI drafts, something independent checks.** That check was the real data, a test, a held-out set of matches, a second source, or me.

## The workflow, in the moments that mattered

### 1. Plan from measurements, not assumptions
Before writing code, Claude Code read the data docs and probed real match feeds. It worked out where gun ownership lives (end-of-buy-phase inventories), that positions only exist on events, and that weapon pickups aren't recorded. A separate review agent then checked the architecture against the data. The plan in `notes/PLAN.md` was built on measured numbers, e.g. Cloud9 had an Operator in 102 rounds. That number later became the first regression check for the pipeline.

### 2. A validation check caught a silent data bug
The first full build of all 857 series completed without errors, but 35 maps had one round more than their official score. Tracing it showed that GRID corrects itself mid-feed with **rollback events** that undo earlier events newest-first, under new IDs, and there were 13,255 of them. Claude Code added an undo stack, and every map then matched its official score. Without checking the output against official results, every stat would have been quietly off.

### 3. Junie drafts, review extends
In PyCharm, Junie (Code mode) wrote the synthetic GRID fixtures and 5 tests for the parser, hit an import error and fixed it itself. Claude Code then reviewed the suite:
- **Mutation testing:** it deliberately broke the parser three ways to confirm the tests would catch each one.
- **The missing case:** it found that the suite didn't test the case behind the real bug, a round rolled back and then **replayed**. It added that test plus supplement edge cases.

A first try in AI Assistant's *Chat* mode also taught a lesson: Chat mode can't touch files, so file-changing work belongs in Junie.

### 4. "True" isn't the same as "useful"
The first scouting report ranked "neT's Viper wall goes up in the same spot in 70 of 71 rounds" above everything else. It's true, but every Viper does that: it's a standard lineup, and the typical Viper places it in the same spot 100% of the time. The fix was a league baseline for **habits**, not just rates. Now a habit only shows up when a player is more predictable than others with the same ability on the same map. The top NRG finding became something a coach can actually use: *Odin on Lotus defense in 47 of 117 rounds, against 11% for the typical VCT 2025 team.*

### 5. A human idea, checked by a machine
The data can't tell bomb site A from B. I suggested looking it up online. Claude Code found that the community API valorant-api.com lists map callouts with coordinates, then **tested** whether those coordinates match GRID's: all 8 axis flips and swaps, on all 13 maps. The plain, unchanged coordinates won everywhere, and each site matched within 20 m, with the next site 40+ m away. Only then was it used, for both site names and area names like "near B Main". A later test that compared the two sources caught a subtle labelling error ("B Boat House" for a site centre), which was fixed before it reached the UI.

### 6. Validate estimates or don't ship them
GRID doesn't record where utility lands. Claude Code built ground truth from players damaged by mollies and nanoswarms (23,405 casts) and found that utility lands 17–24 m along the aim, so the cast spots shown until then were ~20 m from the landings. A simple per-ability model cut the typical miss **from 21.3 m to 6.9 m on 171 held-out matches**. Estimates only appear for the 12 abilities where that check exists.

### 7. Asking "is the data fair?"
I asked whether the patch and roster differences in the data mattered. Checking showed two real problems:
- **Mixed tiers:** the "league" mixed VCT 2025 with mostly Game Changers 2026, which plays a different meta. The Lotus Op rate is 10% in VCT but 17% in Game Changers, so Cloud9's difference had been overstated.
- **Mixed rosters:** team tendencies blended rosters. NRG's game plan cited FNS, who had left before Stage 2.

Before changing anything, we confirmed both fixes stay within the provided data. Now each team is compared only with its own tier and season, and tendencies of players who later left are marked and kept out of the game plan. A follow-up made the comparison the **typical team** (the median of each team's own rate) instead of all rounds pooled, so one extreme team can't move it. Measuring that also disproved one of my own explanations: I had said a 33% Odin rate on Corrode was "mostly NRG", but the typical VCT 2025 team was at 32%. It was the meta, not one team.

### 8. The human catches the AI
Claude Code told me turrets deal no damage. I knew that was wrong and checked a search to be sure. The data agreed with me: 1,890 turret damage events. Turrets still had to be excluded, but for a better reason, which is now documented: a turret's victims stand ~23 m from the turret, so they can't locate it. Writing the in-app methodology page caught two more overclaims the same way ("±1 m precision" was never measured, and "replayed maps" were really "cancelled map starts").

## Keeping licensed data safe with AI tools

- **No data in the repo:** the data stays in its own clone, outside the project. The cache and every derived table are gitignored, and staged files are checked before every commit.
- **Synthetic tests:** tests and Junie prompts use **synthetic** events only; Junie's guidelines (`.junie/guidelines.md`) forbid real data in tests or prompts.
- **Opt-outs:** JetBrains AI's detailed data collection is off, as the data license requires for AI tools.
- **Community data:** only aggregate positions (site centres) and community callouts are committed. Both contain no match data.

## What I'd tell another team

- **Give the AI a way to be wrong out loud.** Validation against official scores, held-out matches, mutation-checked tests, a browser check of every page. Each one caught something that looked fine.
- **Draft with one agent, review with another.** Junie's tests were a fast start; the review made them meaningful.
- **Your domain knowledge is the scarcest input.** The two best corrections came from knowing the game.

The full dated log is in `notes/AI_WORKFLOW_LOG.md`.
