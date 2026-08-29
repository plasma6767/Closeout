from closeout.data.players import full_name_for

CURRY_PLAYER_ID = 201939


def test_full_name_for_known_player():
    assert full_name_for(CURRY_PLAYER_ID, fallback="Curry") == "Stephen Curry"


def test_full_name_for_unknown_id_falls_back():
    assert full_name_for(999999999, fallback="Mystery") == "Mystery"
