"""Board calibration persistence for the UCI screen bridge.

Wraps chessboard_detection.py to add save/load and guided-calibration support.
"""
import pickle
import time

from uci_screen_bridge.calibration.chessboard_detection import (
    auto_find_chessboard,
    find_chessboard,
)
from uci_screen_bridge.utils.paths import data_path

SAVE_FILE = data_path("board_position.bin")
MAX_AGE_SECONDS = 24 * 3600


class BoardNotFoundError(Exception):
    """Raised when no chess board can be detected on screen."""


def detect_and_save(method="auto"):
    """Detect the board on screen and save position to disk.

    Args:
        method: "auto" (Hough-line, default) or "template" (template-match).

    Returns:
        (position, we_play_white) on success.

    Raises:
        BoardNotFoundError: if no chess board is detected.
    """
    if method == "template":
        position, we_play_white = find_chessboard()
    else:
        position, we_play_white = auto_find_chessboard()

    if position is None:
        raise BoardNotFoundError("No chess board detected on screen")

    with open(SAVE_FILE, "wb") as f:
        pickle.dump((position, we_play_white), f)
    return position, we_play_white


def load():
    """Load saved board position from disk.

    Returns:
        (position, we_play_white) if the file exists, otherwise (None, None).
    """
    if not SAVE_FILE.exists():
        return None, None
    with open(SAVE_FILE, "rb") as f:
        return pickle.load(f)


def is_fresh(max_age_s=MAX_AGE_SECONDS):
    """Return True if the saved calibration file exists and is newer than max_age_s seconds."""
    if not SAVE_FILE.exists():
        return False
    age = time.time() - SAVE_FILE.stat().st_mtime
    return age < max_age_s
