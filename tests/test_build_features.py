import json

from closeout.features.build_features import build_game_features, run_build_features


def _row(event_id, team="ATL", quarter=1, ball_x=6.0, shooter_id=1):
    return {
        "event_id": event_id,
        "team": team,
        "quarter": quarter,
        "made": True,
        "ball_x": ball_x,
        "ball_y": 25.0,
        "shooter_id": shooter_id,
        "players": [
            {"team_id": 1, "player_id": shooter_id, "x": ball_x, "y": 25.0},
            {"team_id": 2, "player_id": 99, "x": ball_x + 3.0, "y": 25.0},
        ],
    }


def test_build_game_features_reads_a_processed_file_and_adds_features(tmp_path):
    processed_path = tmp_path / "0021500001.jsonl"
    processed_path.write_text("\n".join(json.dumps(_row(i)) for i in range(1, 4)) + "\n")

    rows = build_game_features(processed_path)

    assert len(rows) == 3
    assert all("shot_distance_ft" in row for row in rows)
    assert all(row["closest_defender_dist_ft"] == 3.0 for row in rows)


def test_run_build_features_writes_one_file_per_game_and_reports_ok(tmp_path):
    processed_dir = tmp_path / "processed"
    features_dir = tmp_path / "features"
    processed_dir.mkdir()
    (processed_dir / "0021500001.jsonl").write_text(json.dumps(_row(1)) + "\n")

    results = run_build_features(processed_dir, features_dir)

    assert results == [{"game_id": "0021500001", "status": "ok", "n_shots": 1}]
    written = json.loads((features_dir / "0021500001.jsonl").read_text().splitlines()[0])
    assert written["event_id"] == 1
    assert "shot_distance_ft" in written


def test_run_build_features_skips_a_game_whose_output_already_exists(tmp_path):
    processed_dir = tmp_path / "processed"
    features_dir = tmp_path / "features"
    processed_dir.mkdir()
    features_dir.mkdir()
    (processed_dir / "0021500001.jsonl").write_text(json.dumps(_row(1)) + "\n")
    (features_dir / "0021500001.jsonl").write_text("stale output, should not be touched\n")

    results = run_build_features(processed_dir, features_dir)

    assert results == [{"game_id": "0021500001", "status": "skipped"}]
    assert (features_dir / "0021500001.jsonl").read_text() == "stale output, should not be touched\n"


def test_run_build_features_isolates_a_failure_to_one_game(tmp_path):
    processed_dir = tmp_path / "processed"
    features_dir = tmp_path / "features"
    processed_dir.mkdir()
    (processed_dir / "0021500001.jsonl").write_text(json.dumps(_row(1)) + "\n")
    # shooter_id 999 isn't in this row's players -- should raise inside compute_shot_features
    bad_row = _row(2, shooter_id=1)
    bad_row["shooter_id"] = 999
    (processed_dir / "0021500002.jsonl").write_text(json.dumps(bad_row) + "\n")

    results = run_build_features(processed_dir, features_dir)

    by_game = {r["game_id"]: r for r in results}
    assert by_game["0021500001"]["status"] == "ok"
    assert by_game["0021500002"]["status"] == "error"
    assert (features_dir / "0021500001.jsonl").exists()
    assert not (features_dir / "0021500002.jsonl").exists()
