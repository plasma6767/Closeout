# Closeout

A shot-quality model built on real NBA player-tracking data, used to answer
a concrete question: **how much of Steph Curry's 2015-16 season was true
shot-making skill versus getting easier shots than everyone else?**

The model estimates expected field-goal percentage for a shot from defender
positioning at the instant it was taken — closest-defender distance, angle,
and closing speed — using frame-by-frame optical tracking data, not just
shot location. Comparing actual makes against that expected probability
produces a shot-difficulty-adjusted view of shooting performance, applied to
Curry's unanimous-MVP, 402-three-pointer season.

## Data

Player-tracking data comes from the public mirror of the NBA's 2015-16
SportVU optical tracking logs
([`linouk23/NBA-Player-Movements`](https://github.com/linouk23/NBA-Player-Movements)) —
frame-by-frame (x, y) coordinates for the ball and all 10 players, captured
25 times per second. This is the last season the NBA released raw tracking
data publicly; all tracking since has been proprietary (Second Spectrum),
available only to teams and licensed partners.

Shot outcomes (make/miss) are not present in the tracking data itself and
are joined in from the NBA's official play-by-play feed.

The shot-quality model itself is trained on shots from across the whole
league, not just Curry's — an expected-FG% baseline is only meaningful if
it reflects how a shot of a given difficulty goes in for a typical player,
not just for the Warriors. The available mirror covers 632 usable games
spanning all 30 teams (Oct 2015 – Jan 2016, the last date the mirror has
tracking data for anyone), totaling 105,000+ labeled shots. Curry's own
shots are one slice of that dataset, used for the actual-vs-expected
comparison the project is built around.

## Findings: Curry vs. shot difficulty

Comparing actual makes against the model's expected FG% for every shot in
the dataset (Oct 2015 – Jan 2016, the tracking mirror's cutoff), Stephen
Curry made 50.6% of his 716 shots against an expected 39.2% — about 82 more
makes than an average shooter would get on the same shots. That +11.4
percentage point gap is the largest of any player in the league with at
least 200 shots in this window, ahead of Hassan Whiteside (+9.3) and Kevin
Durant (+8.4).

This isn't "Curry took easy shots and made them" — the expected FG% already
accounts for shot difficulty (defender distance, angle, closing speed), so
the gap is shot-making skill beyond what positioning alone predicts. Note
this covers roughly the first half of the 2015-16 season (the tracking
mirror's cutoff), not the full 73-9/402-three campaign.

Reproduce with `python -m closeout.analysis.shot_quality`.

## Dashboard

`streamlit run app/dashboard.py` launches an interactive version of the
findings above: pick any player with 200+ shots in the dataset (last names
alone aren't unique -- e.g. Stephen and Seth Curry both played in 2015-16 --
so the picker shows full names) and see their shot chart, colored by the
model's expected FG% for each shot, next to the full league leaderboard and
that player's rank. Shot charts drop the rare half-court heave rather than
silently cutting it off at the edge of the court diagram, noting how many
were left out.

## Project structure

```
src/closeout/
  data/       ingestion + parsing: tracking data, play-by-play, the join between them
  features/   feature engineering (defender distance/angle, shot distance, etc.)
  models/     model training and evaluation
  analysis/   actual-vs-expected FG% comparisons (the Curry findings above)
  viz/        the shot chart: court drawing + projecting shots onto one half-court
app/          the Streamlit dashboard (dashboard.py)
notebooks/    exploratory analysis
tests/        test suite
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

The last step installs this repo itself in editable mode, so `closeout` is
importable (and the commands above and in `app/dashboard.py` work) without
having to set `PYTHONPATH` by hand.

## Status

All planned stages are done -- see `PLAN.md` for how each one was built and
validated. Curry's shots (and everyone else's) are the point of the project,
not a placeholder; extending past the tracking mirror's Jan 22 cutoff would
need a different data source, since no later 2015-16 SportVU data is
publicly available.

## License

Copyright (c) 2026 plasma6767. All rights reserved. See `LICENSE`.
