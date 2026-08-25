import json
from unittest.mock import patch

from closeout.data.batch import run_batch


def test_run_batch_writes_a_dataset_per_game_and_reports_shot_counts(tmp_path):
    games = [{"game_id": "G1", "tracking_url": "url1"}]
    processed_dir = tmp_path / "processed"

    with (
        patch("closeout.data.batch.download_tracking_events", return_value=[]),
        patch("closeout.data.batch.fetch_playbyplay_rows", return_value=[]),
        patch("closeout.data.batch.build_shot_dataset", return_value=[{"made": True}]),
    ):
        results = run_batch(games, processed_dir=processed_dir)

    assert results == [{"game_id": "G1", "status": "ok", "n_shots": 1}]
    written = (processed_dir / "G1.jsonl").read_text().splitlines()
    assert [json.loads(line) for line in written] == [{"made": True}]


def test_run_batch_isolates_a_failing_game_and_still_processes_the_rest(tmp_path):
    games = [{"game_id": "BAD", "tracking_url": "url1"}, {"game_id": "GOOD", "tracking_url": "url2"}]
    processed_dir = tmp_path / "processed"

    def fake_download(game_id, tracking_url):
        if game_id == "BAD":
            raise RuntimeError("network exploded")
        return []

    with (
        patch("closeout.data.batch.download_tracking_events", side_effect=fake_download),
        patch("closeout.data.batch.fetch_playbyplay_rows", return_value=[]),
        patch("closeout.data.batch.build_shot_dataset", return_value=[]),
    ):
        results = run_batch(games, processed_dir=processed_dir)

    assert results == [
        {"game_id": "BAD", "status": "error", "error": "network exploded"},
        {"game_id": "GOOD", "status": "ok", "n_shots": 0},
    ]
    assert not (processed_dir / "BAD.jsonl").exists()
    assert (processed_dir / "GOOD.jsonl").exists()


def test_run_batch_skips_a_game_whose_output_already_exists(tmp_path):
    games = [{"game_id": "DONE", "tracking_url": "url1"}]
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "DONE.jsonl").write_text('{"made": true}\n')

    with (
        patch("closeout.data.batch.download_tracking_events") as mock_download,
        patch("closeout.data.batch.fetch_playbyplay_rows") as mock_pbp,
    ):
        results = run_batch(games, processed_dir=processed_dir)

    mock_download.assert_not_called()
    mock_pbp.assert_not_called()
    assert results == [{"game_id": "DONE", "status": "skipped"}]
