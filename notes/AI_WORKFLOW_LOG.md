# AI workflow log

Running notes for the "Best AI-Powered Workflow Story" bonus. Add an entry whenever Junie, Air, or Claude does something notable.

| Date | Tool | Task | What happened | Time saved / lesson |
|------|------|------|---------------|---------------------|
| 2026-11-23 | Claude Code | Environment setup + project plan | Set up uv/git and the sparse data clone; probed real feeds to confirm where Op ownership, positions and weapons live; a review subagent checked the architecture; wrote `notes/PLAN.md` (M1–M6). | Planning was grounded in measured numbers (e.g. C9 Op in 102 rounds) instead of assumptions. |
| 2026-11-23 | Claude Code | M1 ingest pipeline | Wrote a streaming parser → parquet cache for all 857 series (4 min, 9 processes). The first full build flagged 35 games with an extra round; tracing it showed GRID rollbacks (`!` events) undo events LIFO with new ids. Added an undo stack, and all games then matched the official scores. | Validating the build against `meta/games.csv` caught a data bug that would have silently skewed every stat. |
| 2026-11-23 | Claude Code | M2 Operator profiler | Built the analytics, a minimap drawn from 1.4M recorded positions (no Riot art), and a Streamlit page with sample-size cards and Wilson intervals. Checked it in the in-app browser; the map insight was switched from raw percentages to Wilson bounds after it picked a 0-of-35 map over a more confident 2-of-134. | First data-backed insight for C9: Op on 38% of Haven defense rounds vs 1.5% on Lotus. |
