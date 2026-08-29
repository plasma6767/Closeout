# Closeout — project plan & status

Last updated: 2026-08-28 (modeling stage)

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
  per game inside. 636 games available in this mirror across the whole
  league (covers roughly Oct 2015 - Jan 22 2016, not the full season).
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

**Done**, on `feature/batch-ingestion` (superseded by the league-wide join
below, but the batch-driver mechanics carried forward): resolved the
game_id ↔ tracking-file join for the 42 available Warriors games, built
`download.py` + `batch.py` to fetch and run the pipeline per game with
per-game error isolation, and ran it for real (42/42 games, 7,332 shots).

**Done**, on `feature/league-wide-shot-history`: realized the Warriors-only
dataset was a problem for modeling, not just for Curry's own stats --
every non-Warriors shot in it only existed because that team happened to
play GSW that season, so it wasn't a representative sample of how shots
of a given difficulty go in around the league. Fixed by widening the pull
to the whole league:
- Joined the *full* 2015-16 league schedule (`nba_api`'s
  `LeagueGameFinder`) against the tracking mirror's file listing, by date
  + home/away team abbreviations (date alone isn't a unique key once
  every team is in play, since multiple games happen per night).
  635 of the mirror's 636 files matched a real game with no ambiguity;
  one (`01.23.2016.UTA.at.WAS.7z`) doesn't correspond to any game in the
  official schedule at all and is dropped. Pinned as
  `src/closeout/data/resources/season_2015_16_games.json`.
- Went to the whole league also meant the per-game raw tracking data
  (~100MB decompressed) would've meant tens of GB kept around for no
  reason. Instead: `match_shots_to_frames()` now also finds a second,
  "prior" frame from about a second before each shot (game clock counts
  down, so this reuses the same frame-finder with a shifted target
  clock), and `build_shot_dataset()` saves both frames' positions per
  shot (`prior_ball_x/y/z`, `prior_players`, `prior_game_clock`) -- enough
  to compute closing speed later without ever needing the raw tracking
  data again. `download.py` no longer persists anything to disk; `batch.py`
  skips a game whose output file already exists instead of relying on a
  raw-file cache, which also makes an interrupted run resumable for free.
- Ran the full batch for real: **632 of 635 games processed, 105,163
  shots total**, spanning all 30 teams (3,061-3,803 shots each, no team
  dominating the sample) and 375 distinct shooters. 3 games
  (`0021500587`, `0021500590`, `0021500589`, all from 2016-01-14) failed
  for a real reason, not a bug: their tracking archives are valid but
  genuinely empty at the source (confirmed by downloading and opening
  them directly -- 32-byte 7z files with zero entries inside). Total
  disk footprint for the entire run: **187 MB**, all of it the final
  processed output -- nothing raw was kept.

**Known limitation, not a bug:** the tracking mirror only has games
through 2016-01-22 — this is a hard cutoff across the whole mirror (all
30 teams), not specific to any team. It just means this dataset covers
roughly the first half of the 82-game season, not the full 73-9/402-three
campaign. Doesn't affect the shot-quality modeling methodology (the
cutoff hits everyone equally, so it's not a biased sample), but the
eventual Curry write-up (roadmap item 4) needs to frame results as "first
half of the season" rather than implying the full season.

**Fixed**, on `fix/shot-release-frame-detection`: found a real bug in the
core shot-to-frame join, not just a limitation. What was believed validated
(ball position lining up with shot descriptions) only checked where the
ball ends up, not where it started -- the play-by-play's recorded clock for
a shot lags the true release by 1.5-3.5 seconds in practice (it reflects
roughly when the shot resolves: ball at the rim, a rebound scramble), so
matching directly on that clock was landing on frames where the shooter
could be 20+ feet from the ball. Checked across a sample of games: median
shooter-to-ball distance at the old "matched" frame was 23 ft, with ball
height at 4.4 ft (well below release height). This meant every downstream
"defender distance/positioning at the shot" feature would have measured
something closer to "positioning after the shot resolved," not shot
difficulty at release.

Fixed with `find_release_frame()` in `tracking.py`: scans backward from the
recorded clock (up to 5 seconds) for the last frame where the ball was
within 1.5 ft of the shooter. A dribble -- or a driving layup's slower
gather, where the ball can drift a foot or two from the body before truly
leaving the hand -- always brings the ball back close again; a true release
never does, so the last close approach in the window is the release by
construction. This works the same way for a flat-arced dunk as a high jump
shot, without needing separate tuning per shot type (an earlier version of
this heuristic that required the ball to visibly rise after separating was
biased against dropping layups/dunks -- fixed before it shipped).
`match_shots_to_frames()` now anchors both the shot frame and the prior
frame off the detected release instead of the raw play-by-play clock.

Re-ran the full batch: **632 of 635 games, 98,449 shots total** (down from
105,163 -- the old code never actually failed to match more often, it just
never refused to answer, so a chunk of those 105,163 were confidently wrong
rather than correctly dropped). Checked whether the drop is biased toward
close-range shots (a real concern, since easy shots being disproportionately
excluded would skew the model toward overestimating shot difficulty): on
one game the gap looked large (14.6% vs. 8.2% drop rate), but across a
60-game sample (~10,000 shots) it narrows to 7.4% vs. 5.8% -- a small
residual tilt, not a serious bias, and in the same category as the season-
cutoff limitation above rather than something blocking further work.

## Status: Stage 2 — feature engineering (done)

Built on `feature/shot-quality-features`, in `src/closeout/features/shot_features.py`:

- **Shot distance & angle from the basket**, from the release-frame ball
  position.
- **Closest and second-closest defender**: distance to the ball, plus the
  angle between the shooter-to-basket line and the shooter-to-defender
  line -- distance alone can't tell "defender right in the shooting lane"
  from "defender standing nearby but out of the play." Confirmed on a real
  shot in the dataset (Casspi's driving dunk, game `0021500031`, event 113)
  where the closest defender at 1.35 ft was at a 179.8-degree angle --
  essentially standing directly behind the shooter, not contesting at all
  despite being closer than any other player on the floor.
- **Shooter speed and closest-defender closing speed**, from the release
  frame vs. the ~1-second-prior frame already saved per shot.
- **A catch-and-shoot proxy**: assisted + a plain, unqualified "Jump Shot"
  subtype (excludes Pullup/Step Back/Turnaround/Driving/Running/Hook/
  Dunk/Tip/Cutting/Alley-Oop variants, all of which mean the shooter
  created it off movement). Not the NBA's own catch-and-shoot stat, which
  also needs touch-time/dribble-count data this project doesn't have --
  the standard proxy used in public analytics when that data isn't
  available.

**Which basket a team is attacking** is inferred per team, per half (teams
switch baskets at halftime, not every quarter) by majority vote across all
of that team's shots in the half, not from any single shot's own release
position. Picking the nearer basket per-shot breaks on end-of-quarter
heaves: the shooter is standing next to their *own* basket when a 90-foot
heave leaves their hand, so a per-shot heuristic would score it as a
point-blank attempt. Verified 495 of 98,449 shots (0.5%) have a computed
shot distance over 40 ft -- consistent with genuine buzzer-beater heaves
being handled correctly, not a sign of basket-side mixups.

**shot_type and assisted required backfilling into the play-by-play.** The
632 already-processed games predate these fields, and re-running the full
tracking pipeline just to add them would mean re-downloading every
tracking archive again for data that only ever came from play-by-play.
Added `src/closeout/data/backfill.py`: re-fetches play-by-play only (no
tracking download) and merges the fields onto existing rows by event_id.

**Found and fixed a real, pre-existing bug while wiring up defender
features**, not something this stage introduced: a blocked shot generates
a second play-by-play row at the same `actionNumber`, crediting the
blocker (e.g. a missed, blocked Singler layup in game `0021500044` also
generated a companion row crediting Faried, the blocker). The original
`build_shot_dataset()` built its actionNumber lookup from every row
without filtering to real shot attempts, so that companion row could
silently overwrite the real shot's entry in the lookup dict -- meaning
`shooter_id`/`shooter_name`/`team` were wrong for a meaningful share of
blocked shots across the whole dataset (one sampled game had 30 duplicate
`actionNumber`s out of 495 total rows, roughly half of them shot+block
pairs). The tracking-derived positions were never affected (frame matching
always used the correct shooter id, sourced from the shot row itself), so
nothing needed re-downloading -- fixed in `shot_rows_by_action_number()`
(restricts the lookup to real field-goal rows) and folded into the same
backfill pass that adds shot_type/assisted. This is exactly why the
closest-defender feature raised on 12 games at first (the misattributed
"shooter" genuinely wasn't on the court in that frame) -- after the fix,
all 632 games process cleanly with 0 failures, same 98,449-shot total as
the release-frame fix left it at.

**New, smaller limitation found in the process, not yet fixed:** for shot
types that should always be at the rim (layups, dunks, tip-ins, alley-oops
-- 28,873 of the 98,449 shots), 2,494 (8.6% of that group, 2.5% of all
shots) come out with a computed shot distance over 10 ft. This is a
precision gap in the existing release-frame heuristic (`find_release_frame`
in `tracking.py`, from the earlier release-frame fix), not something this
stage's feature math got wrong: for some finishes -- reverse layups,
finger rolls, alley-oops -- the ball can leave the hand from further than
the 1.5 ft "near" threshold, or an earlier incidental close-approach (e.g.
gathering a loose ball well before actually attacking the rim) gets picked
instead of the true release. In the same category as the season cutoff and
shot-drop-bias limitations already documented above: real, worth knowing
about for modeling (may be worth an outlier filter on rim-type shots
before training), but not blocking this stage.

Final numbers: **98,449 shots featured across all 632 games, 0 failures.**
Catch-and-shoot rate came out to 12.4% (12,169 shots) -- lower than the
NBA's own ~20-25% catch-and-shoot rate, which makes sense given the proxy
requires both an assist and the plain "Jump Shot" subtype specifically,
missing catch-and-shoot shots that are unassisted or get bucketed under a
different subtype label. Only 379 shots (0.4%) are missing shooter/closing
speed (no usable prior frame); 0 shots have zero tracked defenders.

## Status: Stage 3 — modeling (done)

Built on `feature/shot-quality-modeling`, in `src/closeout/models/`:

- `dataset.py` loads every game's feature file into one table and splits
  it into train/test **by game_id**, not by individual shot -- splitting
  shot-by-shot would let shots from the same game land on both sides,
  leaking that game's personnel/pace/matchups into what's supposed to be
  a held-out evaluation.
- `train.py` fits two models on the train split: a logistic-regression
  baseline on shot distance alone, and an xgboost model (300 trees, depth
  4) over every engineered feature (both defenders' distance/angle,
  shooter/defender speed, catch-and-shoot). Both get evaluated on the
  held-out games: AUC, log-loss, and a 10-bucket calibration table
  (predicted vs. actual make rate, bucketed by quantile so buckets have
  even shot counts rather than even probability width).

Ran for real on the full 98,449-shot dataset:

```
baseline: AUC=0.6124  log_loss=0.6706
full:     AUC=0.8423  log_loss=0.4571
```

The full model clearly wins -- distance alone explains some of shot
difficulty, but defender positioning explains a lot more. Calibration on
the full model is tight across the whole range (e.g. shots it called
~35% went in 34% of the time, ~65% went in 65% of the time, ~91% went in
92% of the time) -- the predicted probabilities aren't just well-ranked,
they're trustworthy as actual probabilities, which matters for stage 4
since the Curry analysis is a straight actual-vs-expected comparison.

The full model gets refit on the entire dataset (train+test) and used to
score `expected_fg_pct` for all 98,449 shots, written to
`data/predictions/*.jsonl` (one file per game, same convention as
`processed/`/`features/`, gitignored the same way).

## Roadmap

1. ~~**Data ingestion module**~~ — done, see above.
2. ~~**Feature engineering**~~ — done, see above.
3. ~~**Modeling**~~ — done, see above.
4. **The Curry analysis**: compare Curry's actual vs. expected FG% across
   all his shots in the dataset vs. league average, write this up.
5. **Dashboard/viz** (`app/`): shot chart colored by expected probability,
   plus the actual-vs-expected leaderboard, likely Streamlit.
6. **README polish + push** once there's something real to show.

Each numbered stage above = roughly "a feature" for commit/push purposes.
