# Closeout — project plan & status

Last updated: 2026-08-24

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

## Status: Stage 1 — data ingestion module (done)

- [x] `build_quarter_timelines()` — dedupe/merge overlapping tracking events
      into one per-quarter timeline, tested
- [x] `find_frame_for_clock()` — match a play-by-play clock to a tracking
      frame, with late-coverage detection, tested
- [x] `parse_shot_events()` — parse a play-by-play shot row into
      `{event_id, quarter, game_clock, made}`, tested (field names/formats
      confirmed against the installed `nba_api` package and a real
      `PlayByPlayV3` response)
- [x] `match_shots_to_frames()` — ties parsed shots to matched frames by
      quarter + game clock, tested
- [x] Downloaded + extracted one real game (`0021500480`, GSW @ DAL,
      2015-12-30) and validated the whole pipeline against it: ball
      positions line up with shot descriptions (e.g. a 15ft fadeaway lands
      the ball right by the rim), across all 4 quarters, not just one.
      Found and fixed a real edge case doing this — a frame can have no
      ball entry at all (untracked/occluded) even when it otherwise
      matches; those shots are now dropped like coverage-gap shots are.
- [x] `build_shot_dataset()` / `write_shot_dataset()` — assembles the final
      per-shot rows (shooter identity, make/miss, raw ball/player
      positions) and writes them as JSON Lines. Ran end-to-end on the real
      game: 163 shots in, 157 written (5 dropped for coverage gaps, 1 for
      the missing-ball case), output at `data/processed/0021500480.jsonl`.

**Done**, on `feature/batch-ingestion`:
- Resolved the game_id ↔ tracking-file join for all 42 available Warriors
  games (matched the Warriors' 2015-16 schedule from `nba_api`'s
  `TeamGameLog` against the tracking mirror's file listing, by date — a
  team plays at most one game per day so this is an unambiguous 1:1 join,
  verified all 42 dates matched with no leftovers). Pinned as a static
  resource (`src/closeout/data/resources/warriors_2015_16_games.json`)
  since the season is historical and frozen — no reason to re-derive this
  from two live APIs on every run.
- `download.py` — fetches and caches (skips re-fetching if already on
  disk) both raw inputs per game: the tracking `.7z` archive, and
  play-by-play rows via `PlayByPlayV3`.
- `batch.py` — runs the existing single-game pipeline once per game,
  isolating each in its own try/except so one bad game doesn't kill the
  run, and reports a per-game success/failure summary.
- Ran the full batch for real: **42/42 games processed, 7,332 shots
  total**, written to `data/processed/{game_id}.jsonl`. The one
  previously hand-validated game (`0021500480`) still produces exactly
  157 shots through the automated path, matching the earlier manual
  result.

**Known limitation, not a bug:** the tracking mirror only has games
through 2016-01-22 — checked, and this is a hard cutoff across the whole
mirror (all 30 teams, not just the Warriors), so it's not a
Warriors-specific or home/away-biased gap. It just means this dataset
covers roughly the first half of the 82-game season, not the full
73-9/402-three campaign. Doesn't affect the shot-quality modeling
methodology, but the eventual Curry write-up (roadmap item 4) needs to
frame results as "first half of the season" rather than implying the
full season.

## Roadmap

1. ~~**Data ingestion module**~~ — done, see above.
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
