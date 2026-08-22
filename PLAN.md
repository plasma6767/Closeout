# Closeout — project plan & status

Last updated: 2026-08-22 (evening)

## The pitch

A shot-quality model trained on real NBA player-tracking data, applied to a
concrete question: how much of Steph Curry's 2015-16 season (unanimous MVP,
402 threes, 73-9 Warriors) was true shot-making skill vs. getting easier
shots than everyone else? The model estimates expected FG% from defender
distance/angle/closing speed at the moment of each shot; comparing actual
vs. expected reveals who's over/underperforming shot difficulty.

## Decisions already made (don't re-litigate these)

- **Name:** Closeout. Repo: https://github.com/plasma6767/Closeout
- **License:** All rights reserved, copyright plasma6767. No open-source license.
- **Data source:** `linouk23/NBA-Player-Movements` GitHub repo — the public
  mirror of 2015-16 SportVU raw tracking data (last season the NBA released
  raw optical tracking publicly; current tracking is proprietary Second
  Spectrum data, unavailable outside teams). ~5-6MB `.7z` per game, one JSON
  per game inside. 42 Warriors games available in this mirror (covers roughly
  Oct 2015 - Jan 22 2016, not the full season).
- **Labels (make/miss):** tracking data has no shot outcome by itself. Cross-
  reference with official play-by-play via `nba_api`'s `PlayByPlayV3`
  endpoint (NOT `PlayByPlayV2` — deprecated, returns empty data). Game IDs
  match directly between the two sources (e.g. `0021500480`).
- **Join key confirmed working:** tracking event's `eventId` (string) equals
  play-by-play's `actionNumber` (int) for the same play. Cast eventId to int
  when joining.

## Shot-to-frame join (core mechanism, mostly built)

Finding the exact tracking *frame* that corresponds to a given shot was
trickier than expected — two problems, both now solved in code:

- Each tracking "event" is a clip of moments, but consecutive events'
  moments **overlap** (each new event repeats trailing frames from the
  previous one as pre-roll) — so searching only within the matched event's
  own moments can land on the wrong frame.
- Tracking coverage doesn't start at the true beginning of a quarter (e.g. Q1
  tracking in the sample game starts at 680.93s remaining, not 720s) — the
  first shot(s) of a quarter may have no matching frame at all. This needs
  to be detected and those shots dropped/flagged, not silently mismatched.

**Done**, on `feature/data-ingestion`, in `src/closeout/data/tracking.py`
(tested with hand-built fixtures, not live downloads):
- `build_quarter_timelines(events)` — merges+dedupes all moments across all
  events by epoch timestamp into one continuous per-quarter timeline.
- `find_frame_for_clock(timeline, target_clock)` — finds the frame with the
  closest game-clock value to a play-by-play action's clock; returns `None`
  (instead of a wrong guess) when tracking coverage starts after the target
  clock already elapsed.

This approach worked cleanly (exact clock match, plausible ball/player
positions) on the one sample game tested by hand so far
(`0021500480`, GSW @ DAL, 2015-12-30). **Not yet verified:** ball position
sanity-checking across all shot types, and whether this holds across other
games — that verification wants real downloaded data, not just fixtures.

**Next step here:** parse a raw play-by-play shot event into
`(quarter, game_clock, event_id)` — the actual input `find_frame_for_clock`
needs — then wire up the eventId ↔ actionNumber join between tracking
events and play-by-play rows.

## Status: Stage 1 — project scaffolding (in progress)

- [x] Repo created on GitHub, git initialized locally, remote added
- [x] Python venv created
- [x] Confirmed `py7zr` extracts the tracking data fine
- [x] Confirmed `nba_api`'s `PlayByPlayV3` works and the join key lines up
- [x] Folder structure, README, requirements.txt, .gitignore, LICENSE
- [x] First commit made (not pushed yet — nothing functional exists yet)

## Status: Stage 1 — data ingestion module (in progress, on `feature/data-ingestion`)

- [x] `build_quarter_timelines()` — dedupe/merge overlapping tracking events
      into one per-quarter timeline, tested
- [x] `find_frame_for_clock()` — match a play-by-play clock to a tracking
      frame, with late-coverage detection, tested
- [ ] Parse a play-by-play shot row into `(quarter, game_clock, event_id)`
- [ ] Join tracking eventId to play-by-play actionNumber
- [ ] Download + extract one real game (tracking `.7z` + play-by-play) to
      verify the join against real data, not just fixtures
- [ ] Output a clean labeled shot dataset to `data/processed/`

## Roadmap (not started)

1. **Data ingestion module** (`src/closeout/data/`): download N Warriors
   games, extract, parse moments + play-by-play, resolve the shot-moment
   join issue above with real tests, output a clean labeled shot dataset
   (one row per shot: shooter, defender distances/angles, distance to
   basket, shot clock, make/miss, etc.) to `data/processed/`.
2. **Feature engineering** (`src/closeout/features/`): closest/second-
   closest defender distance & angle, shot distance/angle from basket,
   shooter speed, catch-and-shoot vs. off-dribble, quarter/clock context.
3. **Modeling** (`src/closeout/models/`): baseline (distance-only logistic
   regression) vs. full-feature model (gradient boosting), evaluate with
   AUC/log-loss/calibration, derive expected FG% per shot.
4. **The Curry analysis**: compare Curry's actual vs. expected FG% across
   all his shots in the dataset vs. league average, write this up.
5. **Dashboard/viz** (`app/`): shot chart colored by expected probability,
   plus the actual-vs-expected leaderboard, likely Streamlit.
6. **README polish + push** once there's something real to show.

Each numbered stage above = roughly "a feature" for commit/push purposes.
