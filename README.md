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

## Project structure

```
src/closeout/
  data/       ingestion + parsing: tracking data, play-by-play, the join between them
  features/   feature engineering (defender distance/angle, shot distance, etc.)
  models/     model training and evaluation
  viz/        shot charts and plotting utilities
app/          dashboard (Streamlit)
notebooks/    exploratory analysis
tests/        test suite
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Status

Actively in development. See `PLAN.md` for current progress and roadmap.

## License

Copyright (c) 2026 plasma6767. All rights reserved. See `LICENSE`.
