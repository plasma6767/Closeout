from closeout.data.schedule import load_warriors_games


def test_load_warriors_games_returns_all_pinned_games_uniquely_and_with_urls():
    games = load_warriors_games()

    assert len(games) == 42
    game_ids = [game["game_id"] for game in games]
    assert len(set(game_ids)) == 42
    for game in games:
        assert game["game_id"]
        assert game["tracking_url"].startswith("https://raw.githubusercontent.com/")
