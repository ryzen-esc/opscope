# Submission checklist (deadline Jan 12, 2027, 11:00am PT; aim for Jan 9)

## Things only Eli can do
- [ ] **Screenshots** for the README: save to `docs/screenshots/`, then replace the comment near the top of `README.md` with the images.
  - `report.png`: Scouting report, NRG, Game plan visible
  - `operator.png`: Operator profiler, Cloud9 VCT, Haven defense
  - `utility.png`: Utility profiler, Lotus defense, landing view
- [ ] **Demo video** (under 3 min) following `notes/DEMO_SCRIPT.md`. Upload to YouTube as **Public**, and paste the link into Devpost.
- [ ] **JetBrains tools:** decide what else to use them for (e.g. AI Assistant commit messages, a docs draft) and update the "JetBrains tools" lists in `README.md` and `notes/DEVPOST.md`. Mention JetBrains Air only if it's actually used.
- [x] **AI training opt-out:** done for both JetBrains AI (detailed data collection off) and the Claude account used for Claude Code (claude.ai → Settings → Privacy).
- [x] **GitHub repo public:** https://github.com/ryzen-esc/opscope
- [ ] Fill in Devpost from `notes/DEVPOST.md` (repo link above).

## Before pushing (all passed Nov 23, 2026; re-run before submitting)
- [x] `git ls-files | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$|stl-hackathon-2026-grid-starter'` prints nothing.
- [x] `uv run pytest` passes (79 tests on Nov 24).
- [x] A fresh clone in a temp folder → follow the README run steps → the app opens (tests the judge's path end to end).
- [x] `.idea/` and `.junie/` are committed (the rules encourage it); `.idea/workspace.xml` is not.
- [x] LICENSE (MIT) is at the root.
- [x] No school email in commit history (noreply address only).

## Docs in the repo
- `README.md`: what it does, run steps, JetBrains tools, credits
- `METHODOLOGY.md`: method, validation, limits
- `AI_SHOWCASE.md`: the AI workflow story (bonus prize)
- `notes/AI_WORKFLOW_LOG.md`: the dated log behind it
