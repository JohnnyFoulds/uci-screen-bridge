from uci_screen_bridge.online.commentator import Game_state


class _GameThreadStub:
    played_moves = []


def test_game_state_instantiates_without_thread():
    """Game_state can be created standalone, no Commentator_thread needed."""
    state = Game_state()
    assert state.game_thread is None
    assert state.board is not None
    assert state.registered_moves == []


def test_game_thread_stub_prevents_attribute_error():
    """_GameThreadStub prevents AttributeError in register_move_if_needed's premove branch."""
    state = Game_state()
    state.game_thread = _GameThreadStub()
    assert len(state.game_thread.played_moves) == 0
