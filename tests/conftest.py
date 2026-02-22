"""Shared pytest fixtures for all test tiers."""
import http.server
import threading
from pathlib import Path

import numpy as np
import PIL.Image
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Tier 1 / Tier 2: board position stub ─────────────────────────────────────

class FakeBoardPosition:
    """Minimal stand-in for the Board_position namedtuple from chessboard_detection.py."""
    def __init__(self, minX=100, minY=100, maxX=900, maxY=900):
        self.minX = minX
        self.minY = minY
        self.maxX = maxX
        self.maxY = maxY


@pytest.fixture
def fake_board_position():
    """800×800 pixel board starting at (100, 100) — used in unit tests."""
    return FakeBoardPosition(minX=100, minY=100, maxX=900, maxY=900)


# ── Tier 1: mock mss screen-capture ──────────────────────────────────────────

@pytest.fixture
def mock_mss(mocker, request):
    """Replace mss.mss() with a fixture image from tests/fixtures/.

    Usage:
        def test_something(mock_mss):  # uses default chesscom_white.png
            ...

        @pytest.mark.parametrize("mock_mss", ["lichess_white.png"], indirect=True)
        def test_something(mock_mss):
            ...
    """
    fixture_name = getattr(request, "param", "chesscom_white.png")
    fixture_path = FIXTURES_DIR / fixture_name

    if not fixture_path.exists():
        pytest.skip(f"Fixture image not found: {fixture_path}. "
                    "Capture a real screenshot and place it in tests/fixtures/.")

    img = PIL.Image.open(fixture_path).convert("RGB")
    arr = np.array(img)
    fake_shot = {
        "top": 0,
        "left": 0,
        "width": img.width,
        "height": img.height,
        "raw": arr,
    }

    mock = mocker.patch("mss.mss")
    mock.return_value.__enter__.return_value.grab.return_value = fake_shot
    return mock


# ── Tier 3: local HTML board (requires display + playwright) ─────────────────

@pytest.fixture(scope="session")
def local_board_server():
    """Start a local HTTP server serving tests/fixtures/ on an ephemeral port.

    Yields (host, port).  Stops the server when the session ends.
    """
    handler = http.server.SimpleHTTPRequestHandler
    # Change handler's base dir to fixtures/ so board.html is served at "/"
    fixtures_str = str(FIXTURES_DIR)

    class FixturesHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=fixtures_str, **kwargs)

        def log_message(self, fmt, *args):  # silence access log during tests
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), FixturesHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield host, port
    server.shutdown()


@pytest.fixture
def local_board(local_board_server):
    """Open board.html in a headed browser via playwright at a fixed position.

    Yields a dict with keys:
        page         – playwright Page object
        board_url    – URL of the board
        board_x      – screen x-coordinate of the board's left edge (pixels)
        board_y      – screen y-coordinate of the board's top edge (pixels)
        board_size   – side length of the board in pixels (800)

    Requires: playwright browsers installed (`playwright install chromium`)
    Mark tests using this fixture with @pytest.mark.integration.
    """
    pytest.importorskip("playwright", reason="playwright not installed")
    from playwright.sync_api import sync_playwright

    host, port = local_board_server
    url = f"http://{host}:{port}/board.html"

    # Fixed window position so CV can find the board via Hough-line detection
    window_x, window_y = 100, 100
    board_size = 800  # board.html renders at exactly 800×800

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=[
                f"--window-position={window_x},{window_y}",
                "--window-size=900,900",   # a bit larger to accommodate browser chrome
                "--disable-infobars",
            ],
        )
        context = browser.new_context(viewport={"width": 900, "height": 900})
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector("#board")  # ensure board is rendered

        # The board is centred inside the 900×900 viewport; allow 50px for browser chrome
        # These offsets assume a 50px toolbar height — adjust if the OS differs.
        chrome_toolbar_height = 50
        board_x = window_x + (900 - board_size) // 2
        board_y = window_y + chrome_toolbar_height + (900 - board_size) // 2

        yield {
            "page": page,
            "board_url": url,
            "board_x": board_x,
            "board_y": board_y,
            "board_size": board_size,
        }

        browser.close()
