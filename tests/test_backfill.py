import json

import pytest

from closeout.data.backfill import backfill_rows, run_backfill


def _pbp_row(
    action_number,
    period,
    clock,
    person_id,
    shot_result,
    sub_type,
    description,
    is_field_goal=True,
    player_name="",
    team="",
):
    return {
        "actionNumber": action_number,
        "period": period,
        "clock": clock,
        "isFieldGoal": is_field_goal,
        "shotResult": shot_result,
        "personId": person_id,
        "playerName": player_name,
        "teamTricode": team,
        "subType": sub_type,
        "description": description,
    }


def test_backfill_rows_merges_shot_type_and_assisted_by_event_id():
    rows = [
        {"game_id": "g1", "event_id": 5, "made": True},
        {"game_id": "g1", "event_id": 9, "made": False},
    ]
    pbp_rows = [
        _pbp_row(
            5,
            1,
            "PT11M30.00S",
            100,
            "Made",
            "Jump Shot",
            "Curry 13' Jump Shot (2 PTS) (Green 1 AST)",
            player_name="Curry",
            team="GSW",
        ),
        _pbp_row(
            9,
            1,
            "PT10M00.00S",
            100,
            "Missed",
            "Pullup Jump shot",
            "MISS Curry 25' Pullup Jump Shot",
            player_name="Curry",
            team="GSW",
        ),
    ]

    backfilled = backfill_rows(rows, pbp_rows)

    assert backfilled[0]["shot_type"] == "Jump Shot"
    assert backfilled[0]["assisted"] is True
    assert backfilled[0]["shooter_id"] == 100
    assert backfilled[0]["shooter_name"] == "Curry"
    assert backfilled[0]["team"] == "GSW"
    assert backfilled[1]["shot_type"] == "Pullup Jump shot"
    assert backfilled[1]["assisted"] is False
    # original fields untouched
    assert backfilled[0]["made"] is True
    assert backfilled[1]["made"] is False


def test_backfill_rows_corrects_a_shot_misattributed_to_its_blocker():
    # the exact real-world shape that exposed the bug: a companion "Block"
    # row shares actionNumber 101 with the real, missed shot. An old row
    # written before this fix would have shooter_id 202702 (the blocker).
    rows = [{"game_id": "0021500044", "event_id": 101, "shooter_id": 202702, "shooter_name": "Faried", "team": "DEN"}]
    pbp_rows = [
        _pbp_row(
            101,
            1,
            "PT03M19.00S",
            202713,
            "Missed",
            "Alley Oop Layup shot",
            "MISS Singler 2' Alley Oop Layup",
            player_name="Singler",
            team="OKC",
        ),
        _pbp_row(101, 1, "PT03M19.00S", 202702, None, None, "Faried BLOCK (1 BLK)", is_field_goal=False),
    ]

    backfilled = backfill_rows(rows, pbp_rows)

    assert backfilled[0]["shooter_id"] == 202713
    assert backfilled[0]["shooter_name"] == "Singler"
    assert backfilled[0]["team"] == "OKC"


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


def test_run_backfill_always_reprocesses_even_content_that_looks_already_backfilled(tmp_path, monkeypatch):
    # the correction logic itself can change (as it just did, to fix
    # shooter misattribution) -- a presence-based skip would silently
    # trust stale, already-wrong content instead of re-deriving it
    game_path = tmp_path / "0021500001.jsonl"
    game_path.write_text(
        json.dumps({"game_id": "0021500001", "event_id": 5, "shot_type": "Jump Shot", "assisted": True}) + "\n"
    )
    fetch_calls = []

    def fake_fetch(game_id):
        fetch_calls.append(game_id)
        return [_pbp_row(5, 1, "PT11M30.00S", 100, "Made", "Hook Shot", "x (2 PTS)")]

    monkeypatch.setattr("closeout.data.backfill.fetch_playbyplay_rows", fake_fetch)

    results = run_backfill(tmp_path)

    assert fetch_calls == ["0021500001"]
    assert results == [{"game_id": "0021500001", "status": "ok", "n_shots": 1}]
    written = json.loads(game_path.read_text().splitlines()[0])
    assert written["shot_type"] == "Hook Shot"


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
