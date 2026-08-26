import json

import pytest

from closeout.data.backfill import backfill_rows, run_backfill


def _pbp_row(action_number, period, clock, person_id, shot_result, sub_type, description):
    return {
        "actionNumber": action_number,
        "period": period,
        "clock": clock,
        "isFieldGoal": True,
        "shotResult": shot_result,
        "personId": person_id,
        "subType": sub_type,
        "description": description,
    }


def test_backfill_rows_merges_shot_type_and_assisted_by_event_id():
    rows = [
        {"game_id": "g1", "event_id": 5, "made": True},
        {"game_id": "g1", "event_id": 9, "made": False},
    ]
    pbp_rows = [
        _pbp_row(5, 1, "PT11M30.00S", 100, "Made", "Jump Shot", "Curry 13' Jump Shot (2 PTS) (Green 1 AST)"),
        _pbp_row(9, 1, "PT10M00.00S", 100, "Missed", "Pullup Jump shot", "MISS Curry 25' Pullup Jump Shot"),
    ]

    backfilled = backfill_rows(rows, pbp_rows)

    assert backfilled[0]["shot_type"] == "Jump Shot"
    assert backfilled[0]["assisted"] is True
    assert backfilled[1]["shot_type"] == "Pullup Jump shot"
    assert backfilled[1]["assisted"] is False
    # original fields untouched
    assert backfilled[0]["made"] is True
    assert backfilled[1]["made"] is False


def test_backfill_rows_raises_when_a_row_event_id_has_no_matching_shot():
    rows = [{"game_id": "g1", "event_id": 5, "made": True}]
    pbp_rows = [_pbp_row(9, 1, "PT10M00.00S", 100, "Made", "Jump Shot", "x (1 PTS) (y 1 AST)")]

    with pytest.raises(ValueError, match="event_id 5"):
        backfill_rows(rows, pbp_rows)


def test_run_backfill_writes_backfilled_rows_and_reports_ok(tmp_path, monkeypatch):
    processed_dir = tmp_path
    game_path = processed_dir / "0021500001.jsonl"
    game_path.write_text(json.dumps({"game_id": "0021500001", "event_id": 5, "made": True}) + "\n")

    def fake_fetch(game_id):
        assert game_id == "0021500001"
        return [_pbp_row(5, 1, "PT11M30.00S", 100, "Made", "Jump Shot", "x (2 PTS) (y 1 AST)")]

    monkeypatch.setattr("closeout.data.backfill.fetch_playbyplay_rows", fake_fetch)

    results = run_backfill(processed_dir)

    assert results == [{"game_id": "0021500001", "status": "ok", "n_shots": 1}]
    written = json.loads(game_path.read_text().splitlines()[0])
    assert written["shot_type"] == "Jump Shot"
    assert written["assisted"] is True


def test_run_backfill_skips_a_game_already_backfilled(tmp_path, monkeypatch):
    game_path = tmp_path / "0021500001.jsonl"
    game_path.write_text(
        json.dumps({"game_id": "0021500001", "event_id": 5, "shot_type": "Jump Shot", "assisted": True}) + "\n"
    )

    def fail_fetch(game_id):
        raise AssertionError("should not fetch play-by-play for an already-backfilled game")

    monkeypatch.setattr("closeout.data.backfill.fetch_playbyplay_rows", fail_fetch)

    results = run_backfill(tmp_path)

    assert results == [{"game_id": "0021500001", "status": "skipped"}]


def test_run_backfill_isolates_a_failure_to_one_game(tmp_path, monkeypatch):
    good = tmp_path / "0021500001.jsonl"
    good.write_text(json.dumps({"game_id": "0021500001", "event_id": 5, "made": True}) + "\n")
    bad = tmp_path / "0021500002.jsonl"
    bad.write_text(json.dumps({"game_id": "0021500002", "event_id": 7, "made": True}) + "\n")

    def fake_fetch(game_id):
        if game_id == "0021500002":
            raise RuntimeError("network error")
        return [_pbp_row(5, 1, "PT11M30.00S", 100, "Made", "Jump Shot", "x (2 PTS)")]

    monkeypatch.setattr("closeout.data.backfill.fetch_playbyplay_rows", fake_fetch)

    results = run_backfill(tmp_path)

    by_game = {r["game_id"]: r for r in results}
    assert by_game["0021500001"]["status"] == "ok"
    assert by_game["0021500002"]["status"] == "error"
    assert "network error" in by_game["0021500002"]["error"]
