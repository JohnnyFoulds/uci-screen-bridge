"""Unit tests for screen/calibration.py."""
import os
import time

import pytest

import uci_screen_bridge.screen.calibration as cal_module
from uci_screen_bridge.calibration.chessboard_detection import Board_position
from uci_screen_bridge.screen.calibration import (
    BoardNotFoundError,
    detect_and_save,
    is_fresh,
    load,
)


def _make_position(minX=100, minY=100, maxX=900, maxY=900):
    return Board_position(minX=minX, minY=minY, maxX=maxX, maxY=maxY)


@pytest.fixture(autouse=True)
def tmp_save(tmp_path, monkeypatch):
    """Redirect SAVE_FILE to a temp directory so tests don't touch data/."""
    monkeypatch.setattr(cal_module, "SAVE_FILE", tmp_path / "board_position.bin")
    return tmp_path / "board_position.bin"


# ---------------------------------------------------------------------------
# detect_and_save
# ---------------------------------------------------------------------------

def test_detect_and_save_auto(mocker):
    pos = _make_position()
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 return_value=(pos, True))

    result_pos, result_white = detect_and_save(method="auto")

    assert result_pos is pos
    assert result_white is True
    assert cal_module.SAVE_FILE.exists()


def test_detect_and_save_template(mocker):
    pos = _make_position()
    mocker.patch("uci_screen_bridge.screen.calibration.find_chessboard",
                 return_value=(pos, False))

    result_pos, result_white = detect_and_save(method="template")

    assert result_pos is pos
    assert result_white is False
    assert cal_module.SAVE_FILE.exists()


def test_detect_and_save_overwrites_existing(mocker):
    pos1 = _make_position(minX=100)
    pos2 = _make_position(minX=200, maxX=1000)
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 side_effect=[(pos1, True), (pos2, False)])

    detect_and_save()
    detect_and_save()

    loaded_pos, loaded_white = load()
    assert loaded_pos.minX == 200
    assert loaded_white is False


def test_detect_and_save_raises_when_board_not_found(mocker):
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 return_value=(None, None))

    with pytest.raises(BoardNotFoundError):
        detect_and_save(method="auto")


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def test_load_returns_none_when_missing():
    pos, white = load()
    assert pos is None
    assert white is None


def test_load_round_trip(mocker):
    pos = _make_position()
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 return_value=(pos, True))
    detect_and_save()

    loaded_pos, loaded_white = load()

    assert loaded_pos.minX == pos.minX
    assert loaded_pos.minY == pos.minY
    assert loaded_pos.maxX == pos.maxX
    assert loaded_pos.maxY == pos.maxY
    assert loaded_white is True


def test_board_position_values_plausible(mocker):
    pos = _make_position()
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 return_value=(pos, True))
    detect_and_save()

    loaded_pos, _ = load()

    assert loaded_pos.minX < loaded_pos.maxX
    assert loaded_pos.minY < loaded_pos.maxY


# ---------------------------------------------------------------------------
# is_fresh
# ---------------------------------------------------------------------------

def test_is_fresh_returns_false_when_missing():
    assert not is_fresh()


def test_is_fresh_returns_true_for_new_file(mocker):
    pos = _make_position()
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 return_value=(pos, True))
    detect_and_save()

    assert is_fresh()


def test_is_fresh_returns_false_for_old_file(mocker):
    pos = _make_position()
    mocker.patch("uci_screen_bridge.screen.calibration.auto_find_chessboard",
                 return_value=(pos, True))
    detect_and_save()

    old_mtime = time.time() - 25 * 3600  # 25 hours ago
    os.utime(cal_module.SAVE_FILE, (old_mtime, old_mtime))

    assert not is_fresh()
