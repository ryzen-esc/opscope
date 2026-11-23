# Submission checklist (deadline Jan 12, 2027, 11:00am PT; aim for Jan 9)

## Things only Eli can do
- [ ] **Screenshots** for the README: save to `docs/screenshots/`, then replace the comment near the top of `README.md` with the images.
  - `report.png`: Scouting report, NRG, Game plan visible
  - `operator.png`: Operator profiler, Cloud9 VCT, Haven defense
  - `utility.png`: Utility profiler, Lotus defense, landing view
- [ ] **Demo video** (under 3 min) following `notes/DEMO_SCRIPT.md`. Upload to YouTube as **Public**, and paste the link into Devpost.
- [ ] **JetBrains tools:** decide what else to use them for (e.g. AI Assistant commit messages, a docs draft) and update the "JetBrains tools" lists in `README.md` and `notes/DEVPOST.md`. Mention JetBrains Air only if it's actually used.
- [ ] **AI training opt-out:** the data license says to opt out of training on your inputs wherever a tool allows it. JetBrains AI is done. Also check the privacy settings of the Claude account used for Claude Code (claude.ai → Settings → Privacy).
- [x] **GitHub repo public:** https://github.com/ryzen-esc/opscope
- [ ] Fill in Devpost from `notes/DEVPOST.md` (repo link above).

## Before pushing (Claude Code can run these with you)
- [ ] `git ls-files | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$|stl-hackathon-2026-grid-starter'` prints nothing.
- [ ] `uv run pytest` passes.
- [ ] A fresh clone in a temp folder → follow the README run steps → the app opens (tests the judge's path end to end).
- [ ] `.idea/` and `.junie/` are committed (the rules encourage it); `.idea/workspace.xml` is not.
- [ ] LICENSE (MIT) is at the root.

## Docs in the repo
- `README.md`: what it does, run steps, JetBrains tools, credits
- `METHODOLOGY.md`: method, validation, limits
- `AI_SHOWCASE.md`: the AI workflow story (bonus prize)
- `notes/AI_WORKFLOW_LOG.md`: the dated log behind it
