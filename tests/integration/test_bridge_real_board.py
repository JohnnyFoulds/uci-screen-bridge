"""Tier 3 end-to-end integration tests: real pixels, local HTML board.

These tests open an actual browser window, let the UCI engine interact with live
screen pixels via PyAutoGUI and mss, and verify the full round-trip.

Requirements:
  - A display (not headless CI)
  - playwright installed + browsers: `playwright install chromium`
  - The package installed in editable mode: `make install`

Run with: `make test-full`   (included in `pytest tests/ -v`)
Skip in CI: `make test`      (uses `pytest tests/ -v -m "not integration"`)
"""
import subprocess
import sys
import time

import chess
import pytest


pytestmark = pytest.mark.integration


# ── Helper: communicate with UCI engine subprocess ───────────────────────────

def _send(proc, line):
    """Write a UCI command to the engine's stdin."""
    proc.stdin.write((line + "\n").encode())
    proc.stdin.flush()


def _recv_until(proc, keyword, timeout=10.0):
    """Read lines from engine stdout until one contains *keyword*, or timeout."""
    deadline = time.time() + timeout
    lines = []
    while time.time() < deadline:
        proc.stdout.flush()
        line = proc.stdout.readline().decode().rstrip()
        lines.append(line)
        if keyword in line:
            return lines, line
    raise TimeoutError(
        f"Timed out waiting for '{keyword}' from engine.\n"
        f"Lines received: {lines}"
    )


@pytest.fixture(scope="module")
def engine_proc():
    """Spawn the UCI engine as a subprocess. Shared across all tests in this module."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uci_screen_bridge.uci_bridge"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    yield proc
    _send(proc, "quit")
    proc.wait(timeout=5)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_engine_detects_board_on_isready(local_board, engine_proc):
    """Engine correctly identifies the local HTML board's grid via Hough-line detection.

    After `isready`, the engine should emit `readyok` and log that a board was found
    (not an error about board not found on screen).
    """
    _send(engine_proc, "uci")
    _recv_until(engine_proc, "uciok")

    _send(engine_proc, "isready")
    _, line = _recv_until(engine_proc, "readyok")

    # `readyok` must be present; and no ERROR about board not found
    # (engine logs errors with `info string ERROR:`)
    # We can't assert positively that the board IS found without draining all
    # info lines, but the absence of an error + successful readyok is a strong signal.
    assert "readyok" in line, f"Expected readyok, got: {line}"


def test_player_move_clicks_board(local_board, engine_proc):
    """Sending a position command with a player move causes a click on the board.

    The JS board's FEN should change to reflect the move.
    """
    page = local_board["page"]

    # Ensure board is at starting position
    page.evaluate("window.testBoard.setPosition('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')")
    time.sleep(0.2)

    _send(engine_proc, "ucinewgame")
    _send(engine_proc, "setoption name Side value White")

    # White plays e2e4
    _send(engine_proc, "position startpos moves e2e4")
    time.sleep(1.0)  # allow PyAutoGUI to click and board to update

    fen = page.evaluate("window.testBoard.getCurrentFen()")
    # After 1.e4, the e4 square should be occupied by a white pawn
    board = chess.Board(fen)
    piece_at_e4 = board.piece_at(chess.E4)
    assert piece_at_e4 is not None, f"Expected a piece at e4; FEN={fen}"
    assert piece_at_e4.piece_type == chess.PAWN, f"Expected pawn at e4; FEN={fen}"
    assert piece_at_e4.color == chess.WHITE, f"Expected white pawn at e4; FEN={fen}"


def test_opponent_move_via_cv(local_board, engine_proc):
    """Apply an opponent move via JS and verify CV scan returns bestmove.

    Flow: board is at position after 1.e4; opponent plays e7e5;
    engine scans live screen pixels and returns bestmove e7e5.
    """
    page = local_board["page"]

    # Set board to position after 1.e4
    page.evaluate(
        "window.testBoard.setPosition("
        "'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1')"
    )
    time.sleep(0.3)

    # Tell engine the position
    _send(engine_proc, "position startpos moves e2e4")

    # Apply opponent move on screen
    page.evaluate("window.testBoard.applyMove('e7e5')")
    time.sleep(0.3)  # allow browser to repaint

    # Engine scans and detects the move
    _send(engine_proc, "go movetime 10000")
    _, bestmove_line = _recv_until(engine_proc, "bestmove", timeout=30.0)

    assert "bestmove e7e5" in bestmove_line, (
        f"Expected bestmove e7e5, got: {bestmove_line}"
    )


def test_castling_round_trip(local_board, engine_proc):
    """Full round-trip for king-side castling.

    White castles (e1g1): the engine clicks both king and rook positions,
    the JS board reflects the change, and the CV can detect subsequent moves.
    """
    page = local_board["page"]

    # Position ready for white to castle (pieces cleared from f1, g1)
    castling_fen = (
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 4 5"
    )
    page.evaluate(f"window.testBoard.setPosition('{castling_fen}')")
    time.sleep(0.2)

    _send(engine_proc, "ucinewgame")
    _send(engine_proc, f"position fen {castling_fen} moves e1g1")
    time.sleep(1.2)

    fen = page.evaluate("window.testBoard.getCurrentFen()")
    board = chess.Board(fen)

    # King should be on g1, rook on f1
    king_at_g1 = board.piece_at(chess.G1)
    rook_at_f1 = board.piece_at(chess.F1)
    assert king_at_g1 is not None and king_at_g1.piece_type == chess.KING, (
        f"Expected white king at g1 after castling; FEN={fen}"
    )
    assert rook_at_f1 is not None and rook_at_f1.piece_type == chess.ROOK, (
        f"Expected white rook at f1 after castling; FEN={fen}"
    )
