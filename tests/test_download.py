import json
from unittest.mock import MagicMock, patch

import py7zr

from closeout.data.download import download_tracking_events, fetch_playbyplay_rows


def _build_archive_bytes(tmp_path, game_id, events):
    archive_path = tmp_path / "source.7z"
    with py7zr.SevenZipFile(archive_path, mode="w") as archive:
        archive.writestr(json.dumps({"gameid": game_id, "gamedate": "", "events": events}), f"{game_id}.json")
    return archive_path.read_bytes()


def test_download_tracking_events_downloads_and_extracts(tmp_path):
    events = [{"eventId": "1", "moments": []}]
    archive_bytes = _build_archive_bytes(tmp_path, "0021500480", events)

    with patch("closeout.data.download.requests.get") as mock_get:
        mock_get.return_value = MagicMock(content=archive_bytes)
        result = download_tracking_events("0021500480", "http://example.com/x.7z")

    assert result == events
    mock_get.assert_called_once_with("http://example.com/x.7z", timeout=60)


def test_download_tracking_events_does_not_write_into_the_working_directory(tmp_path, monkeypatch):
    events = [{"eventId": "1", "moments": []}]
    archive_bytes = _build_archive_bytes(tmp_path, "0021500480", events)
    monkeypatch.chdir(tmp_path)

    with patch("closeout.data.download.requests.get") as mock_get:
        mock_get.return_value = MagicMock(content=archive_bytes)
        download_tracking_events("0021500480", "http://example.com/x.7z")

    # only the fixture archive we built above should be here -- nothing new
    assert [p.name for p in tmp_path.iterdir()] == ["source.7z"]


def test_fetch_playbyplay_rows_fetches_from_playbyplayv3():
    rows = [{"actionNumber": 1, "isFieldGoal": True}]
    fake_dataframe = MagicMock()
    fake_dataframe.to_dict.return_value = rows
    fake_response = MagicMock()
    fake_response.get_data_frames.return_value = [fake_dataframe]

    with patch("closeout.data.download.playbyplayv3.PlayByPlayV3", return_value=fake_response) as mock_cls:
        result = fetch_playbyplay_rows("0021500480")

    assert result == rows
    mock_cls.assert_called_once_with(game_id="0021500480")
