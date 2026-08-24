import json
from unittest.mock import MagicMock, patch

import py7zr

from closeout.data.download import download_tracking_events, fetch_playbyplay_rows


def _write_archive(path, game_id, events):
    with py7zr.SevenZipFile(path, mode="w") as archive:
        archive.writestr(json.dumps({"gameid": game_id, "gamedate": "", "events": events}), f"{game_id}.json")


def test_download_tracking_events_downloads_and_extracts_when_not_cached(tmp_path):
    events = [{"eventId": "1", "moments": []}]
    source_path = tmp_path / "source.7z"
    _write_archive(source_path, "0021500480", events)
    archive_bytes = source_path.read_bytes()

    raw_dir = tmp_path / "raw"
    with patch("closeout.data.download.requests.get") as mock_get:
        mock_get.return_value = MagicMock(content=archive_bytes)
        result = download_tracking_events("0021500480", "http://example.com/x.7z", raw_dir)

    assert result == events
    mock_get.assert_called_once_with("http://example.com/x.7z", timeout=60)
    assert (raw_dir / "0021500480.7z").exists()
    assert (raw_dir / "0021500480.json").exists()


def test_download_tracking_events_skips_download_when_archive_already_cached(tmp_path):
    events = [{"eventId": "1", "moments": []}]
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_archive(raw_dir / "0021500480.7z", "0021500480", events)

    with patch("closeout.data.download.requests.get") as mock_get:
        result = download_tracking_events("0021500480", "http://example.com/x.7z", raw_dir)

    mock_get.assert_not_called()
    assert result == events


def test_fetch_playbyplay_rows_fetches_and_caches_when_not_cached(tmp_path):
    rows = [{"actionNumber": 1, "isFieldGoal": True}]
    raw_dir = tmp_path / "raw"

    fake_dataframe = MagicMock()
    fake_dataframe.to_dict.return_value = rows
    fake_response = MagicMock()
    fake_response.get_data_frames.return_value = [fake_dataframe]

    with patch("closeout.data.download.playbyplayv3.PlayByPlayV3", return_value=fake_response) as mock_cls:
        result = fetch_playbyplay_rows("0021500480", raw_dir)

    assert result == rows
    mock_cls.assert_called_once_with(game_id="0021500480")
    assert json.loads((raw_dir / "0021500480_pbp.json").read_text()) == rows


def test_fetch_playbyplay_rows_uses_cache_when_present(tmp_path):
    rows = [{"actionNumber": 1, "isFieldGoal": True}]
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "0021500480_pbp.json").write_text(json.dumps(rows))

    with patch("closeout.data.download.playbyplayv3.PlayByPlayV3") as mock_cls:
        result = fetch_playbyplay_rows("0021500480", raw_dir)

    mock_cls.assert_not_called()
    assert result == rows
