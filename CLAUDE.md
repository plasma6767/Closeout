# Closeout — working conventions

Read this and `PLAN.md` before touching code — `PLAN.md` has current status,
this file has rules for how the repo is maintained.

## What this project is

A shot-quality model built on real 2015-16 NBA SportVU player-tracking data.
It estimates expected field-goal percentage from defender positioning
(distance, angle, closing speed) at the moment of each shot, then compares
actual vs. expected outcomes to identify shot-making performance relative to
shot difficulty — applied specifically to Steph Curry's 2015-16 season.

## Repo conventions

- Always build new features on their own branch off `main` — never commit
  feature work directly to `main`.
- Never merge branches. Merging is done by the repo owner, not Claude.
- Commit often, in small logical units — not one giant commit per session.
- Push only when a feature is fully working, not after every commit.
- Commit messages should read like a person wrote them: plain language,
  describe what changed and why. No filler, no robotic file-listing.
- New logic (data parsing, feature engineering, model code) requires a real
  test before it's considered done.
- Once a mechanism (e.g. a data join) is understood, implement it as real,
  tested code in `src/` rather than continuing to iterate in throwaway
  scripts.

## License

All rights reserved, copyright plasma6767. No open-source license file.
