import pytest
from uci_screen_bridge.online.commentator import Game_state


def test_game_state_instantiates_without_thread():
    """Game_state can be created standalone, no Commentator_thread needed."""
    state = Game_state()
    assert state.game_thread is None
    assert state.board is not None
    assert state.registered_moves == []


def test_game_thread_none_does_not_raise(monkeypatch):
    """Calling register_move_if_needed() with game_thread=None must not raise AttributeError."""
    import numpy as np
    state = Game_state()
    state.game_thread = None
    dummy = np.zeros((800, 800), dtype=np.uint8)
    state.previous_chessboard_image = dummy
    # Stub hardware dependencies so execution reaches the premove guard at line ~264.
    monkeypatch.setattr(state, 'get_chessboard', lambda: dummy)
    # Non-empty potential_starts forces the premove branch; empty move string means no
    # valid move was found, so only the game_thread guard prevents an AttributeError.
    monkeypatch.setattr(state, 'get_potential_moves', lambda *_: (["e2"], ["e4"]))
    monkeypatch.setattr(state, 'get_valid_move', lambda *_: "")
    # Should not raise — the guard in commentator.py makes None an explicitly valid state
    try:
        state.register_move_if_needed()
    except AttributeError:
        pytest.fail("register_move_if_needed() raised AttributeError with game_thread=None")
