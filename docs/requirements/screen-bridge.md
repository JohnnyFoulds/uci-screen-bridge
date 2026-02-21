# Project: UCI Screen Bridge — Requirements & Implementation Plan

## 1. Executive Summary

**Goal:** Transform this repository into a Python-based UCI chess engine shim that bridges any standard Chess GUI (e.g., BearChess, Fritz, Arena) to any chessboard visible on the computer screen (Chess.com, Lichess, YouTube, puzzle apps, etc.).

**Problem Solved:** Users with electronic chess boards (e.g., Chessnut Air via DGT/UCI drivers) can play against *any* website or app, not just Lichess. The Chess GUI manages the hardware (piece LEDs, move input); this bridge handles screen interaction.

**Mechanism:**
1. **Input (GUI → Bridge):** Chess GUI sends player moves via standard UCI `position` commands → Bridge simulates mouse clicks on the target screen window.
2. **Output (Bridge → GUI):** Bridge monitors screen pixels for opponent moves via Computer Vision → Sends detected move back as UCI `bestmove` → GUI triggers board LEDs and registers the opponent's move.

**Relationship to Existing Code:**
The current repo is a webcam-to-online-game bridge (physical board → webcam → CV → online play). This new tool is a UCI-to-screen bridge (Chess GUI UCI → screen clicks → CV screen scan). The screen-facing half (board detection, move execution via PyAutoGUI, opponent move detection via CV) is directly reusable. The webcam/physical-board half is not needed.

---

## 2. System Architecture

```text
[ Physical Board ] <──> [ Drivers ] <──> [ Chess GUI (BearChess/Fritz) ]
                                                    │
                                              UCI stdin/stdout
                                                    │
                                                    ▼
                                       ┌─────────────────────────┐
                                       │   UCIEngine (new)        │
                                       │  - Parses UCI commands   │
                                       │  - Tracks chess.Board    │
                                       │  - Detects move deltas   │
                                       └────────────┬────────────┘
                                                    │
                              ┌─────────────────────┼──────────────────────┐
                              │                     │                      │
                              ▼                     ▼                      ▼
                   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
                   │  MoveExecutor    │  │  MoveDetector    │  │  BoardLocator    │
                   │ (internet_game.py│  │ (commentator.py  │  │ (chessboard_     │
                   │  REUSE)         │  │  Game_state REUSE│  │  detection.py    │
                   │                 │  │  + classifier.py)│  │  REUSE)         │
                   └────────┬─────── ┘  └────────┬─────────┘  └──────────────────┘
                            │                    │
                    Mouse Clicks             Screen Capture (mss)
                            │                    │
                            └──────────┬─────────┘
                                       ▼
                         [ Web Browser / Any App Window ]
                         [ showing any online chess board ]
```

---

## 3. Development Philosophy & TDD Contract

### 3.1 TDD Contract

This project follows strict Test-Driven Development. The rules are:

- **Tests are written before implementation.** For each phase, the test suite (defined below in Section 7) must be written and committed before any implementation code for that phase.
- **A phase is not complete until all its tests pass.** Advancing to the next phase with failing tests is not permitted.
- **No integration before unit tests pass.** Each component is tested in isolation using mocks before it is wired together with other components.

### 3.2 Three-Tier Testing Strategy

The project uses three tiers of tests with different trade-offs between speed, isolation, and realism.

#### Tier 1 — Headless unit tests (real-site screenshots, no screen required)
**Purpose:** Verify the CV pipeline handles real-world board variations from actual chess sites.

- `tests/fixtures/` holds **real screenshots** captured from Chess.com and Lichess (white/black sides, various positions)
- `mock_mss` fixture replaces `mss.mss()` with these real PNGs so tests run headlessly
- Tests cover: different board sizes, color schemes, piece shapes, dark/light themes
- These tests are **irreplaceable** — a custom local board cannot replicate the specific piece art, font rendering, or UI chrome of real chess sites
- Runs in CI, no screen required

#### Tier 2 — Component mocked integration tests (headless, no screen required)
**Purpose:** Verify UCI protocol parsing and component wiring without needing a screen.

- All screen interactions mocked (executor and detector both replaced with test doubles)
- Fast, CI-suitable
- Tests UCI command parsing, move delta detection, `bestmove` output format

#### Tier 3 — True end-to-end tests (real pixels, local HTML board, requires display)
**Purpose:** Verify the full UCI bridge pipeline: PyAutoGUI clicks land on a real window, CV reads live pixels, `bestmove` matches the applied move.

- Uses a local HTML board (`tests/fixtures/board.html`) served via `http.server`
- Browser controlled via `playwright`; board state changed programmatically from Python
- The CV's OCM classifier **self-calibrates** from the initial board screenshot, so it works with any piece art that has visible edges
- `auto_find_chessboard()` uses Hough-line detection on the 8×8 grid — works with any regular grid board
- Mark with `@pytest.mark.integration`; excluded from CI (`make test`); run on dev machine with `make test-full`

### 3.3 Test Framework & Infrastructure

**Framework:** `pytest` — add to `requirements_dev.txt`. Also add `pytest-mock` for mocking.

```text
requirements_dev.txt additions:
  pytest>=8.0
  pytest-mock>=3.12
  Pillow>=10.0          # for synthesizing test images
  playwright>=1.40      # Tier 3 end-to-end tests
```

**Test directory structure** (new top-level `tests/` mirroring `src/uci_screen_bridge/`):

```text
tests/
├── conftest.py                    # shared fixtures (board positions, fake screenshots, local_board)
├── fixtures/                      # static test assets (committed as binary files)
│   ├── board.html                 # Tier 3: self-contained local HTML chess board
│   ├── chesscom_white.png         # Chess.com board screenshot (playing white)
│   ├── chesscom_black.png         # Chess.com board screenshot (playing black)
│   ├── lichess_white.png          # Lichess board screenshot (playing white)
│   ├── lichess_black.png          # Lichess board screenshot (playing black)
│   ├── chesscom_after_e2e4.png    # Chess.com board after 1.e4
│   ├── chesscom_after_e2e4_e7e5.png  # Chess.com board after 1.e4 e5
│   ├── chesscom_capture.png       # Chess.com board mid-capture (e.g. d4xc5)
│   ├── chesscom_castled.png       # Chess.com board after e1g1 castling
│   ├── chesscom_promo_dialog.png  # Chess.com board with promotion dialog at e8
│   ├── lichess_promo_dialog.png   # Lichess board with promotion dialog
│   ├── no_promo_region.png        # Region with no dialog pixels (for fallback test)
│   ├── board_before_promo.png     # Board with white pawn on e7
│   ├── board_after_promo_queen.png  # Board after white promotes to queen on e8
│   └── board_after_promo_rook.png   # Board after white promotes to rook on e8
├── uci/
│   └── test_engine.py
├── screen/
│   ├── test_calibration.py
│   ├── test_executor.py
│   └── test_detector.py
└── integration/
    ├── test_uci_round_trip.py     # Tier 2: mocked round-trip tests
    └── test_bridge_real_board.py  # Tier 3: real pixels, local board
```

**`conftest.py`** provides:

- `fake_board_position` fixture: a `Board_position(minX=100, minY=100, maxX=900, maxY=900)` for unit tests
- `board_image_before(move)` / `board_image_after(move)` fixtures: synthesized numpy arrays or PNG paths representing known board states
- `mock_mss` fixture: patches `mss.mss()` to return pre-captured images from `tests/fixtures/`
- `local_board` fixture (Tier 3 only): starts a local HTTP server, opens `board.html` in a headed browser via playwright at a fixed screen position, returns `board_position` coordinates to tests

### 3.4 CV Mocking Strategy

Screen-capture code (`mss.mss()`) must be replaced with a fixture in all tests so they run headlessly:

```python
# conftest.py
@pytest.fixture
def mock_mss(mocker, request):
    """Return a fake mss context manager that yields fixture images."""
    fixture_name = getattr(request, "param", "chesscom_white.png")
    img = PIL.Image.open(Path("tests/fixtures") / fixture_name)
    fake_shot = {"top": 0, "left": 0, "width": img.width, "height": img.height,
                 "raw": np.array(img)}
    mock = mocker.patch("mss.mss")
    mock.return_value.__enter__.return_value.grab.return_value = fake_shot
    return mock
```

Provide at minimum four reference screenshots as test assets in `tests/fixtures/` (Chess.com white/black, Lichess white/black). These are committed into the repository as binary test assets.

**Fixture file specification** — all board screenshots should be full browser window at 1920×1080 or the board region at native display resolution (include browser chrome so Hough-line detection is realistic):

| File | Content | Used by |
|------|---------|---------|
| `chesscom_white.png` | Chess.com board, starting position, playing white | Phase 2 Hough detection, Phase 4 baseline |
| `chesscom_black.png` | Chess.com board, starting position, playing black | Phase 2 orientation detection |
| `lichess_white.png` | Lichess board, starting position, playing white | Phase 2, Phase 4 |
| `lichess_black.png` | Lichess board, starting position, playing black | Phase 2 orientation |
| `chesscom_after_e2e4.png` | Chess.com board after 1.e4 | Phase 4 move detection |
| `chesscom_after_e2e4_e7e5.png` | Chess.com board after 1.e4 e5 | Phase 4 move detection |
| `chesscom_capture.png` | Chess.com board mid-capture (e.g., d4xc5) | Phase 4 capture detection |
| `chesscom_castled.png` | Chess.com board after `e1g1` castling | Phase 4 castling detection |
| `chesscom_promo_dialog.png` | Chess.com board with promotion dialog visible at e8 | Phase 3 promotion |
| `lichess_promo_dialog.png` | Lichess board with promotion dialog visible | Phase 3 promotion |
| `no_promo_region.png` | Region with no dialog pixels | Phase 3 fallback |
| `board_before_promo.png` | Board with white pawn on e7 | Phase 4 opponent promotion |
| `board_after_promo_queen.png` | Board after white promotes to queen on e8 | Phase 4 opponent promotion |
| `board_after_promo_rook.png` | Board after white promotes to rook on e8 | Phase 4 opponent promotion |

### 3.5 Running Tests

Add targets to the `Makefile`:

```makefile
test:           # Tier 1 + Tier 2 — headless, no screen required; suitable for CI
	pytest tests/ -v -m "not integration"

test-full:      # All tiers including Tier 3 — requires a display and browser
	pytest tests/ -v
```

Run with: `make test` (headless) or `make test-full` (all tiers).

---

## 4. Existing Code Inventory & Reuse Plan

### 4.1 Directly Reusable (no modification)

| Module | What it does | Used for |
|--------|-------------|----------|
| `calibration/chessboard_detection.py` → `auto_find_chessboard()` | Hough-line board detection; returns `Board_position(minX,minY,maxX,maxY)` and `we_play_white` | Default board location at startup |
| `detection/classifier.py` → `Classifier` | Oriented Chamfer Matching to identify piece type per square (needed by `Game_state.get_valid_move()`) | Piece classification during move validation |
| `utils/paths.py` | `model_path()`, `data_path()` | All asset/data file resolution |

> **Note — minor modification required for `calibration/chessboard_detection.py`:** Replace the two bare `print()` calls in `find_chessboard_from_image()` with `logging.getLogger(__name__).warning(...)`. This is the only change to the existing file and is required to keep stdout clean for UCI.
> - Line 151: `print("Board is not square.")` → `logger.warning("Board is not square.")`
> - Line 159: `print("Chess board of online game could not be found.")` → `logger.warning("Chess board of online game could not be found.")`

> **Note on template-match:** `calibration/chessboard_detection.py` → `find_chessboard()` (template-match using `white.JPG` / `black.JPG`) is also available but is **opt-in only** — it is only invoked when the UCI option `CalibrationMethod` is explicitly set to `Template`. The `white.JPG` and `black.JPG` assets remain bundled but are not loaded by default.

### 4.2 Partially Reusable (adapt or wrap)

| Module | Reusable part | Change needed |
|--------|--------------|---------------|
| `online/commentator.py` → `Game_state` | Core CV pipeline: screenshot → square diff → OCM classification → chess legality (opponent move detection) | Add `if self.game_thread is not None` guard before the `len(self.game_thread.played_moves)` check (line ~264). This makes `game_thread = None` an explicitly valid UCI-mode state. |
| `online/commentator.py` → `Commentator_thread` | `Game_state` inner class is the real logic | The thread wrapper needs to be replaced with a call-on-demand pattern driven by UCI `go` commands |
| `calibration/chessboard_detection.py` → `find_chessboard()` | Board location logic (template variant) | Only invoked when `CalibrationMethod = Template`; save/load board position to/from `data/board_position.bin` |
| `online/internet_game.py` → `Internet_game` | Maps UCI move string to screen coordinates, executes PyAutoGUI click/drag | Needs a thin `DirectInternetGame` subclass (see Section 6.6) to bypass the GUI-specific `__init__`; mark as "needs thin subclass" |
| `utils/speech.py` → `Speech_thread` | TTS dispatch (macOS `say` / pyttsx3 elsewhere), daemon thread with queue | Reuse for **out-of-band audio alerts only** — not for move commentary. Wrap with `TTSAlerts` UCI option guard. |
| `utils/languages.py` | English `Language` class | Keep English only; use only the minimal alert phrase set (not full game commentary) |

### 4.3 Not Needed (webcam/physical-board specific)

- `calibration/board_calibration.py` — physical corner detection
- `calibration/board_calibration_machine_learning.py` — YOLO corner detection on webcam
- `detection/board_basics.py` — perspective transform, SSIM, physical board geometry
- `utils/videocapture.py` — webcam thread
- `main.py` (current) — webcam game loop
- `gui.py` — Tkinter GUI
- `diagnostic.py` — webcam overlay

---

## 5. Functional Requirements

### FR1: UCI Protocol Compliance
The engine must run as a standalone subprocess called by the Chess GUI, communicating via stdin/stdout.

- **FR1.1 Handshake:** Respond correctly to `uci`, `isready`, `ucinewgame`.
- **FR1.2 Position tracking:** Parse `position [startpos | fen <fen>] [moves <move_list>]`. Maintain an internal `chess.Board` that mirrors the GUI's board state.
- **FR1.3 Move delta detection:** After each `position` command, compare the new moves list to the previous. If a new move appeared AND it is the player's move (i.e., the side we play), execute it on screen immediately.
- **FR1.4 Go command:** On `go` (any variant: `go`, `go infinite`, `go movetime N`, `go wtime ... btime ...`), enter the CV scan loop to detect the opponent's move on screen. Block until a move is confirmed, then output `bestmove <move>`.
- **FR1.5 Quit:** On `quit`, release resources and exit cleanly.
- **FR1.6 UCI options:** Expose configuration as UCI options so the Chess GUI can pass settings without a separate config file. Full option set:
  - `option name Side type combo default Auto var Auto var White var Black` — which color we play. `Auto` (the default) uses the `we_play_white` value returned by `auto_find_chessboard()` / `is_white_on_bottom()` at `isready` time; `White` and `Black` override the auto-detected result. If the explicit value conflicts with the detected orientation, emit `info string WARNING: Side option conflicts with detected board orientation`.
  - `option name CalibrationMethod type combo default Auto var Auto var Template` — board detection method (Auto = Hough-line, **default**; Template = template-match using bundled images, opt-in only)
  - `option name ScanInterval type spin default 500 min 100 max 2000` — milliseconds between CV scans
  - `option name DragDrop type check default false` — use drag-and-drop vs. two-click
  - `option name MoveTimeout type spin default 60 min 10 max 300` — seconds to wait for opponent move before emitting `bestmove 0000`
  - `option name Recalibrate type button` — triggers re-detection of board on screen (same as re-running `isready` calibration)
  - `option name TTSAlerts type check default true` — enable/disable TTS audio alerts for critical events (board not found, move failed, timeout)
  - `option name PromotionStyle type combo default Auto var Auto var ChessCom var Lichess` — site-specific promotion dialog handling
  - `option name LogLevel type combo default INFO var DEBUG var INFO var WARNING var OFF` — verbosity of the log file written to `data/uci-bridge.log`. `DEBUG`: every CV scan, click coordinate, and move candidate. `INFO` (default): move executions, calibration events, timeouts. `WARNING`: errors and warnings only. `OFF`: no log file written.

### FR2: Board Calibration
The bridge must know where the chess board is on screen before play begins.

- **FR2.1 Auto-detect (default):** Use Hough-line detection (`auto_find_chessboard()`) to automatically locate the board from a screenshot. This is the **primary and default** method. It requires no user action and no user-provided template files.
- **FR2.2 Template-match (opt-in):** Use existing `white.JPG` / `black.JPG` templates via `find_chessboard()` as an **opt-in alternative**, activated only when `CalibrationMethod = Template` is explicitly set. This is not a fallback — it is a user-selected mode. Remove any language implying it is a "fallback".
- **FR2.3 Persistence:** Save the detected `Board_position` and `we_play_white` flag to `data/board_position.bin` (pickle). On subsequent `isready`, load from file to avoid re-detection.
- **FR2.4 Calibration command:** Support `setoption name Recalibrate value true` (UCI button) or a separate CLI (`python -m uci_screen_bridge.calibrate`) to re-run board detection on demand.
- **FR2.5 Orientation:** The board detection already returns `we_play_white` via `is_white_on_bottom()`. Confirm this matches the side configured via UCI option. Warn (via `info string`) if there is a mismatch.
- **FR2.6 Guided calibration flow:** When calibration needs to run (no cached `board_position.bin`, stale data >24h, or `Recalibrate` triggered), the engine must guide the user to ensure only the target web board is visible on screen. A Chess GUI (Fritz, BearChess, etc.) also shows an 8×8 chess board — Hough-line detection cannot distinguish between two boards simultaneously. If both are visible, the merged grid lines produce an unpredictable or failed detection result.

  **Guided flow steps (executed inside `_handle_isready()` before emitting `readyok`):**
  1. Emit `info string CALIBRATING: Please minimize your chess client. Make sure only the web chess board is visible, then wait...`
  2. If `TTSAlerts = true`: speak "Please minimize your chess client and show the web chess board"
  3. Poll `auto_find_chessboard()` (or `find_chessboard()` when `CalibrationMethod = Template`) every 2 seconds, for up to 60 seconds total.
  4. On success: emit `info string CALIBRATING: Chess board detected. You can reopen your chess client now.` + TTS "Board detected, you may reopen your chess client". Save result to `board_position.bin`. Continue `isready` processing normally.
  5. If 60 seconds elapse with no board detected: emit `info string ERROR: Chess board not found on screen. Please navigate to the chess board and use Recalibrate.` + TTS alert. Emit `readyok` anyway — do not hang or exit. Subsequent `go` commands with a `None` board position will emit `bestmove 0000`.

  **Subsequent starts:** If `board_position.bin` is fresh (< 24h), skip the guided flow entirely. `readyok` is emitted immediately with no user prompts.

### FR3: Move Execution (UCI → Screen)
When the player makes a move, execute it via simulated mouse input.

- **FR3.1 Coordinate mapping:** Reuse `Internet_game.get_square_center(square_name)` which already accounts for board orientation. **Note:** Coordinate mapping assumes `Board_position` values are in logical (pyautogui) coordinates. `screen/calibration.py` is responsible for normalising physical-pixel coordinates from `mss` to logical before saving.
- **FR3.2 Click sequence:** Click source square, then destination square. Support drag-and-drop mode.
- **FR3.3 Humanization:** Introduce a small random delay (50–200ms) between clicks to avoid bot detection.
- **FR3.4 Promotion:** If the move includes a promotion piece (e.g., `e7e8q`), after the destination click:
  1. Poll every 50ms (up to 500ms) for the promotion dialog to appear. Proceed as soon as it is detected; do not wait the full 500ms if detected earlier.
  2. **Dialog direction:** The dialog always appears toward the *near edge* — the edge closest to the promoting player's side. For white promoting on rank 8, the dialog appears above the destination square. For black promoting on rank 1, the dialog appears below the destination square.
  3. Capture a screenshot of the near-edge region (≈1.5 square heights above or below the destination square). Scan for the promotion dialog using the pattern: a sudden color transition (brighter or darker band) in a pixel column.
  4. **Icon position lookup table** (controlled by `PromotionStyle` UCI option):
     - `ChessCom`: icons stacked **vertically** above/below the destination square. Order top→bottom: Queen(0), Knight(1), Rook(2), Bishop(3). Click position: `destination_center + (icon_index × square_size)` in the vertical direction toward the near edge.
     - `Lichess`: icons arranged **horizontally** in a row at the top or bottom of the board. Order left→right: Queen(0), Rook(1), Bishop(2), Knight(3). Click position: `destination_center + (icon_index × square_size)` in the horizontal direction.
     - `Auto`: attempt generic detection first; fall back to ChessCom then Lichess patterns.
  5. **File-edge clipping:** After computing the icon click position, clamp the x-coordinate to `[0, screen_width - 1]` and the y-coordinate to `[0, screen_height - 1]` to prevent overflow on edge files (a-file / h-file).
  6. **Fallback:** If no promotion dialog is detected after the full 500ms polling window:
     1. Emit `info string WARNING: promotion dialog not detected on <square>`
     2. If `TTSAlerts = true`: speak "Please promote to <piece> on <square>"
        (piece name is always known from the UCI move string, e.g. `e7e8q` → "queen")
     3. Poll every 100 ms for up to 10 s, watching for any piece to appear on the destination
        square (board-state change = user resolved the dialog manually)
     4. If board-state change detected within 10 s: continue normally
     5. If 10 s expires without change: emit `info string ERROR: promotion not completed after
        10s`, proceed with `bestmove <move>` anyway. Do NOT deadlock.
     Note: when `TTSAlerts = false`, the `info string WARNING` in the Chess GUI's engine log
     is the only notification; users should ensure TTS is enabled when promoting.
  7. The UCI move string (including the promotion character `q`/`r`/`b`/`n`) must survive to the `bestmove` reply. The `bestmove` line must include the promotion character (e.g., `bestmove e7e8r`, not `bestmove e7e8`).
- **FR3.5 Move confirmation:** After executing, optionally take a screenshot and verify the source square is now empty (lightweight sanity check).

### FR4: Opponent Move Detection (Screen → UCI)
When `go` is received, scan the screen for the opponent's move and return it as `bestmove`.

- **FR4.1 Baseline capture:** At the time `go` is received, call `MoveDetector.set_baseline()` to capture the current board image as the reference state. This image becomes `game_state.previous_chessboard_image`. After `bestmove` is returned, `set_baseline()` is called again at the start of the *next* `go` command — the post-move board state becomes the new baseline for the next turn.
- **FR4.2 Scan loop:** Poll at `ScanInterval` ms. Capture current board image and compute per-square pixel diffs using `Game_state.get_potential_moves()`.
- **FR4.3 Move validation:** Use `Game_state.get_valid_move()` which validates candidates against `python-chess` legal moves and the OCM classifier.
- **FR4.4 Animation debounce:** Reuse the existing double-confirmation logic from `Game_state.register_move_if_needed()`: if a candidate move is detected, wait 100ms and re-check — only accept if the same move is still seen (avoids animation artifacts).
- **FR4.5 Output:** When confirmed, print `bestmove <uci_move>` and flush stdout. Update internal board state.
- **FR4.6 Castling:** `Game_state.get_valid_move()` already handles all four castling patterns explicitly.
- **FR4.7 Promotion:** `Game_state.get_valid_move()` already handles promotion detection via classifier output.

---

## 6. Technical Architecture

### 6.1 New Module Structure

```text
src/uci_screen_bridge/
├── uci/
│   ├── __init__.py
│   └── engine.py           # UCIEngine class — main UCI loop
├── screen/
│   ├── __init__.py
│   ├── calibration.py      # Board detection + persistence (wraps chessboard_detection.py)
│   ├── executor.py         # Player move execution (wraps DirectInternetGame)
│   └── detector.py         # Opponent move detection (wraps Game_state)
├── uci_bridge.py           # Entry point: wire UCI engine + screen components + Speech_thread
│                           #   Calls _configure_logging(level_name) before UCIEngine.run().
│                           #   _configure_logging sets up logging.FileHandler → data/uci-bridge.log
│
│   [EXISTING — unchanged]
├── calibration/
│   └── chessboard_detection.py
├── detection/
│   └── classifier.py
├── online/
│   ├── commentator.py
│   └── internet_game.py
├── models/                 # Bundled ONNX models + template images
└── utils/
    └── paths.py
```

**`utils/paths.py` additions:** The existing `model_path()` and `data_path()` helpers are unchanged. A new `uci_data_path(filename)` helper is added that uses `platformdirs.user_data_dir("uci-screen-bridge")` to resolve an OS-compliant user data directory. It creates the directory on first call. All UCI-engine data files (`board_position.bin`, `uci-bridge.log`) use this helper. (`data_path()` is left unchanged — it continues to serve the existing webcam-bridge pickle files.)

**Startup logging configuration** — called in `uci_bridge.py` before `UCIEngine.run()`:

```python
# uci_bridge.py
import logging
from uci_screen_bridge.utils.paths import uci_data_path

def _configure_logging(level_name: str):
    level = getattr(logging, level_name, logging.INFO)
    if level_name == "OFF":
        return  # no log file written
    log_file = uci_data_path("uci-bridge.log")
    logging.basicConfig(
        filename=str(log_file),
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
```

All internal modules use a module-level logger (`logger = logging.getLogger(__name__)`). `UCIEngine._emit()` is the **only** function allowed to write to stdout. Everything else logs.

### 6.2 UCIEngine State Machine

```text
                    ┌─────────┐
               ─────► INIT    │  (on startup)
                    └────┬────┘
                         │ "uci" received
                         ▼
                    ┌─────────┐
                    │ IDENTIFY │  print id name/author, options, uciok
                    └────┬────┘
                         │ "isready" received
                         ▼
                    ┌─────────┐
                    │  READY  │◄─────────────────────────────────────┐
                    └────┬────┘                                       │
                         │ "position" received                        │
                         ▼                                            │
                    ┌─────────────────────────┐                      │
                    │  UPDATE_POSITION        │                      │
                    │  - Parse moves list     │                      │
                    │  - If new player move:  │                      │
                    │    execute on screen    │                      │
                    └────┬────────────────────┘                      │
                         │ "go" received                             │
                         ▼                                            │
                    ┌─────────────────────────┐                      │
                    │  SCANNING               │  (blocks)            │
                    │  - set_baseline()       │                      │
                    │  - CV poll loop         │                      │
                    │  - Detect opponent move │                      │
                    │  - Print bestmove       │──────────────────────┘
                    └─────────────────────────┘
```

### 6.3 UCI `position` Parsing Logic

```python
def _handle_position(self, command):
    # Parse: "position startpos moves e2e4 e7e5 g1f3"
    # or:    "position fen <fen> moves ..."
    new_moves = parse_moves_from_command(command)
    prev_len = len(self.played_moves)

    # Rebuild board from scratch
    self.board = chess.Board()
    for m in new_moves:
        self.board.push(chess.Move.from_uci(m))

    self.played_moves = new_moves

    # If a new move was added and it belongs to us: execute it on screen
    if len(new_moves) > prev_len:
        last_move = new_moves[-1]
        # Determine whose move it was: before pushing it, the board's turn
        # tells us which color made that move. Compare with we_play_white.
        move_count_before = len(new_moves) - 1
        it_was_white = (move_count_before % 2 == 0)  # White moves on even indices
        if it_was_white == self.we_play_white:
            self.executor.execute(last_move)
```

### 6.4 `go` Command Handler

```python
def _handle_go(self, command):
    # Capture baseline board image at go time
    self.detector.set_baseline()
    # Block-scan for opponent move (returns "0000" on timeout)
    opponent_move = self.detector.wait_for_move(self.board)
    # Update internal state
    if opponent_move != "0000":
        self.board.push(chess.Move.from_uci(opponent_move))
        self.played_moves.append(opponent_move)
    # Return to UCI
    print(f"bestmove {opponent_move}")
    sys.stdout.flush()
```

### 6.5 `screen/detector.py` — MoveDetector

Wraps `Game_state` from `commentator.py`:

```python
class MoveDetector:
    def __init__(self, board_position, we_play_white, scan_interval_ms, move_timeout_s):
        self.game_state = Game_state()
        self.game_state.board_position_on_screen = board_position
        self.game_state.we_play_white = we_play_white
        self.scan_interval = scan_interval_ms / 1000.0
        self.move_timeout = move_timeout_s
        self.game_state.sct = mss.mss()

    def set_baseline(self):
        """Call at go time. Captures the current board state as reference.
        After bestmove is returned, call set_baseline() again at the next go
        so the new board position becomes the reference for the next turn."""
        # Set game_thread = None to mark UCI mode where premove detection is
        # disabled. commentator.py guards the game_thread.played_moves access
        # with an `if self.game_thread is not None` check, so no stub is needed.
        self.game_state.game_thread = None
        self.game_state.previous_chessboard_image = self.game_state.get_chessboard()
        self.game_state.classifier = Classifier(self.game_state)

    def wait_for_move(self, board):
        """Block until a legal opponent move is detected or timeout is reached.
        Returns UCI move string, or '0000' on timeout."""
        self.game_state.board = board.copy()
        deadline = time.time() + self.move_timeout
        while time.time() < deadline:
            found, move = self.game_state.register_move_if_needed()
            if found:
                return move.uci() if hasattr(move, 'uci') else move
            time.sleep(self.scan_interval)
        return "0000"
```

**Baseline lifecycle:** `set_baseline()` is called once per `go` command, immediately before the scan loop starts. The baseline image (`previous_chessboard_image`) persists through the entire wait. After `bestmove` is returned, `set_baseline()` is called again at the start of the *next* `go` command, ensuring the post-move board state becomes the new reference. `Game_state.register_move()` updates `previous_chessboard_image` internally after each registered move — this is the same mechanism used in the existing webcam game loop.

**`game_thread = None`:** `Game_state.register_move_if_needed()` checks `self.game_thread.played_moves` for premove detection. In the UCI bridge, premove detection is unnecessary (the UCI protocol enforces turn order). A `None` value is assigned to `game_state.game_thread` in `set_baseline()`. This is an explicitly valid UCI-mode state — `commentator.py` guards the access with `if self.game_thread is not None` before reading `played_moves`. No stub class is required; premove detection is simply disabled. This is intentional — premove is explicitly out of scope.

### 6.6 `screen/executor.py` — MoveExecutor

Uses a thin `DirectInternetGame` subclass to bypass the GUI-specific `Internet_game.__init__` and override `move()` to replace the inherited `print()` with logging:

```python
_log = logging.getLogger(__name__)

class DirectInternetGame(Internet_game):
    """Thin subclass of Internet_game that accepts board position directly,
    bypassing the GUI-dependent __init__ of the parent class."""
    def __init__(self, board_position, we_play_white, drag_drop):
        # Deliberately do NOT call super().__init__() — it expects GUI context
        self.position = board_position
        self.we_play_white = we_play_white
        self.drag_drop = drag_drop
        self.is_our_turn = we_play_white   # set defensively

    def move(self, move):
        """Execute move on screen. Overrides parent to:
        - Use logging instead of print()
        - Handle promotion moves (parent does not)
        """
        move_string = move.uci()
        origin_square = move_string[0:2]
        destination_square = move_string[2:4]
        promotion_piece = move_string[4] if len(move_string) > 4 else None

        centerXOrigin, centerYOrigin = self.get_square_center(origin_square)
        centerXDest, centerYDest = self.get_square_center(destination_square)

        if self.drag_drop:
            pyautogui.moveTo(centerXOrigin, centerYOrigin, 0.01)
            pyautogui.dragTo(centerXOrigin, centerYOrigin + 1,
                             button='left', duration=0.01)
            pyautogui.dragTo(centerXDest, centerYDest,
                             button='left', duration=0.3)
        else:
            pyautogui.click(centerXOrigin, centerYOrigin, duration=0.1)
            pyautogui.click(centerXDest, centerYDest, duration=0.1)

        if promotion_piece:
            self._handle_promotion(promotion_piece, centerXDest, centerYDest)

        _log.debug("Executed move %s -> %s (promo=%s)",
                   origin_square, destination_square, promotion_piece)

    def _handle_promotion(self, piece, dest_x, dest_y):
        """Poll for and click the promotion dialog. See FR3.4."""
        ...  # new code — see FR3.4 spec

class MoveExecutor:
    def __init__(self, board_position, we_play_white, drag_drop):
        self.game = DirectInternetGame(board_position, we_play_white, drag_drop)

    def execute(self, uci_move_str):
        move = chess.Move.from_uci(uci_move_str)
        # random humanization delay
        time.sleep(random.uniform(0.05, 0.2))
        self.game.move(move)
```

> **Reuse table note:** `Internet_game` is marked as "needs thin subclass" in Section 4.2, not "directly reusable". This approach makes the bypass intentional and fails loudly if `Internet_game` internals change, rather than silently misbehaving.

### 6.7 `screen/calibration.py` — BoardCalibration

```python
SAVE_FILE = uci_data_path("board_position.bin")

class BoardNotFoundError(Exception):
    pass

def detect_and_save(method="auto"):
    """Detects the board on screen and saves position to disk.

    Raises BoardNotFoundError if no chess board is detected.
    Board_position stored on disk is always in logical (pyautogui) coordinates.
    """
    if method == "template":
        position, we_play_white = find_chessboard()
    else:
        position, we_play_white = auto_find_chessboard()

    if position is None:
        raise BoardNotFoundError("No chess board detected on screen")

    # Normalise physical-pixel coordinates from mss to logical (pyautogui) coords.
    # scale = logical_width / mss_image_pixel_width; divides all Board_position
    # values so downstream code (get_square_center, executor) uses logical coords.
    position = _to_logical(position, scale=_compute_hidpi_scale())

    with open(SAVE_FILE, 'wb') as f:
        pickle.dump((position, we_play_white), f)
    return position, we_play_white

def load():
    if not SAVE_FILE.exists():
        return None, None
    with open(SAVE_FILE, 'rb') as f:
        return pickle.load(f)
```

> `auto_find_chessboard()` was modified to return `(None, None)` instead of calling
> `sys.exit(0)` on failure. `detect_and_save()` checks for `None` and raises
> `BoardNotFoundError`, which `UCIEngine._handle_isready()` catches to emit
> `info string ERROR: chess board not found on screen`.

---

## 7. Implementation Phases

### Phase 0 — Isolation Smoke Tests (committed, instant)
**Goal:** Confirm `Game_state` can be used standalone before committing to full TDD phases.

**File:** `tests/screen/test_detector.py` (seed file for Phase 4)

#### Phase 0 Prerequisites — Source Modifications

The following source patches must be applied and committed **before** the smoke tests. Unit tests mock the affected code paths, so tests pass even with the bugs present — but Tier 3 and real-world runs break silently without these fixes.

| File | Change | Required before |
|------|--------|----------------|
| `online/commentator.py` line ~264 | Add `if self.game_thread is not None` guard before the `len(self.game_thread.played_moves)` check | Phase 0 smoke tests |
| `calibration/chessboard_detection.py` lines 151, 159 | Replace `print()` with `logger.warning()` | Phase 2 (calibration) |

These are not new phases — they are prerequisite source patches committed as part of setting up the Phase 0 environment.

---

The coupling point is fully understood: `register_move_if_needed()` accesses
`self.game_thread.played_moves` (lines 264–265 of `commentator.py`) only in the
premove-detection branch. The fix is a `None` guard in `commentator.py` (see prerequisites above).

Two committed smoke tests replace exploratory spike code:
- `test_game_state_instantiates_without_thread` — verifies standalone instantiation
- `test_game_thread_none_does_not_raise` — verifies that calling `register_move_if_needed()` with `game_thread = None` does not raise `AttributeError`

**Success criteria:** Both tests pass green with no screen, no browser, no fixtures.
Run: `pytest tests/screen/test_detector.py -v`

---

### Phase 1 — UCI Engine Skeleton
**Goal:** A working UCI loop that correctly handshakes and parses position/go commands.

**Files to create (tests first):**
- `tests/uci/test_engine.py` ← **write and commit before implementation**
- `src/uci_screen_bridge/uci/__init__.py`
- `src/uci_screen_bridge/uci/engine.py`

**Deliverable:** Running `echo -e "uci\nisready\nquit"` piped to the engine produces correct UCI handshake output.

**Acceptance criteria:**
- Responds to `uci` with `id name UCI Screen Bridge`, `id author [name]`, all 8 UCI options, `uciok`
- Responds to `isready` with `readyok`
- Responds to `ucinewgame` by resetting internal board
- Parses `position startpos moves e2e4 e7e5` correctly
- Exits cleanly on `quit`

#### Phase 1 Test Suite (`tests/uci/test_engine.py`)

All tests may call parser functions directly (unit style) or pipe commands to the engine subprocess via `subprocess.Popen`.

| Test | Description |
|------|-------------|
| `test_uci_handshake` | `uci` command output contains `id name UCI Screen Bridge`, `id author`, all 8 UCI options, and `uciok` |
| `test_isready` | `isready` responds with exactly `readyok` |
| `test_isready_before_uci` | `isready` received before `uci` still responds with `readyok` |
| `test_isready_with_cached_calibration_is_immediate` | When `board_position.bin` exists and is fresh (< 24h), `isready` emits `readyok` immediately with no `CALIBRATING:` lines |
| `test_isready_without_cache_emits_calibrating_prompt` | When no cached file exists, `isready` emits `info string CALIBRATING: Please minimize...` before `readyok` |
| `test_guided_calibration_emits_success_message` | When `auto_find_chessboard()` returns a valid board on first poll, engine emits the "board detected" message before `readyok` |
| `test_guided_calibration_retries_on_none` | When `auto_find_chessboard()` returns `None` for the first several polls then succeeds, `readyok` is eventually emitted with success message |
| `test_guided_calibration_timeout_emits_error` | When all polls time out (60s), `info string ERROR:` is emitted and `readyok` is still sent (engine does not hang) |
| `test_recalibrate_reruns_guided_flow` | `setoption name Recalibrate value true` triggers the same guided flow as first-run calibration (prompts user, polls, emits success) |
| `test_tts_called_on_calibration_prompt` | With `TTSAlerts = true`, `Speech_thread` receives the "minimize your client" phrase during guided calibration |
| `test_tts_not_called_when_disabled` | With `TTSAlerts = false`, no TTS call is made during guided calibration |
| `test_ucinewgame_resets_board` | After `position startpos moves e2e4`, `ucinewgame` resets the board to the starting position |
| `test_position_startpos_one_move` | `position startpos moves e2e4` results in board where e4 is occupied by a white pawn |
| `test_position_startpos_three_moves` | `position startpos moves e2e4 e7e5 g1f3` leaves board with correct FEN (knight on f3, pawns on e4/e5) |
| `test_position_startpos_no_moves` | `position startpos` (no moves list) does not trigger executor and leaves board at starting position |
| `test_position_fen` | `position fen <fen> moves ...` correctly parses a non-starting FEN and applies subsequent moves |
| `test_move_delta_player_move` | When player side is white and a white move is added, executor is called exactly once with the new move |
| `test_move_delta_opponent_move` | When player side is white and a black move is added, executor is NOT called |
| `test_move_delta_no_new_move` | Sending the same position twice does not trigger the executor |
| `test_go_before_position_assumes_startpos` | `go` received before any `position` command assumes start position with no moves; does not crash |
| `test_go_variants_all_trigger_scan` | `go`, `go infinite`, `go movetime 5000`, and `go wtime 60000 btime 60000` all invoke the CV scan loop (mock detector) |
| `test_stop_interrupts_go` | `stop` command interrupts any blocking `go` and causes `bestmove 0000` to be emitted |
| `test_unknown_command_ignored` | Unknown commands (e.g., `xboard`, `ping 1`) are silently ignored; no output and no crash |
| `test_setoption_side_white` | `setoption name Side value White` stores the side and executor uses white orientation |
| `test_setoption_side_black` | `setoption name Side value Black` stores the side and executor uses black orientation |
| `test_setoption_side_auto_uses_calibration` | `setoption name Side value Auto` (default) uses `we_play_white` from `auto_find_chessboard()` |
| `test_setoption_side_explicit_overrides_calibration` | Explicit `Side = White` overrides a detected `we_play_white = False`; emits `info string WARNING:` about mismatch |
| `test_setoption_scan_interval` | `setoption name ScanInterval value 200` passes 200ms to the detector |
| `test_setoption_drag_drop` | `setoption name DragDrop value true` passes `drag_drop=True` to the executor |
| `test_setoption_move_timeout` | `setoption name MoveTimeout value 30` passes 30s to the detector |
| `test_setoption_calibration_method` | `setoption name CalibrationMethod value Template` passes `method="template"` to calibration |
| `test_setoption_before_isready` | `setoption` between `uci` and `isready` is accepted and applied at `isready` time |
| `test_quit_exits` | `quit` causes the process to exit with code 0 |

---

### Phase 2 — Board Calibration
**Goal:** Detect the chess board on screen and persist its position.

**Files to create (tests first):**
- `tests/screen/test_calibration.py` ← **write and commit before implementation**
- `src/uci_screen_bridge/screen/__init__.py`
- `src/uci_screen_bridge/screen/calibration.py`

**Deliverable:** Running `python -m uci_screen_bridge.calibrate` detects the board and saves `data/board_position.bin`.

**Acceptance criteria:**
- Auto-detect (Hough-line) works against Chess.com and Lichess boards
- Template-match works when explicitly selected (`CalibrationMethod = Template`)
- `we_play_white` is correctly determined
- Saved data loads correctly on next engine start
- If no saved data, auto-detect runs on `isready`

#### Phase 2 Test Suite (`tests/screen/test_calibration.py`)

| Test | Description |
|------|-------------|
| `test_detect_and_save_auto` | `detect_and_save(method="auto")` with mocked `auto_find_chessboard()` returning a fixed `Board_position` writes the correct data to a temp file |
| `test_detect_and_save_template` | `detect_and_save(method="template")` with mocked `find_chessboard()` returning a fixed `Board_position` writes the correct data |
| `test_detect_and_save_overwrites_existing` | Calling `detect_and_save()` a second time overwrites the existing file with new values atomically |
| `test_detect_and_save_raises_when_board_not_found` | When `auto_find_chessboard()` returns `None`, `detect_and_save()` raises `BoardNotFoundError` |
| `test_load_returns_none_when_missing` | `load()` returns `(None, None)` when the save file does not exist |
| `test_load_round_trip` | After `detect_and_save()`, `load()` returns the same `Board_position` and `we_play_white` values |
| `test_board_position_values_plausible` | Loaded `Board_position` satisfies `minX < maxX` and `minY < maxY` |
| `test_orientation_white_on_bottom` | `is_white_on_bottom()` returns `True` for `chesscom_white.png` fixture (bottom edge is lighter — white pieces) |
| `test_orientation_black_on_bottom` | `is_white_on_bottom()` returns `False` for `chesscom_black.png` fixture |
| `test_hough_detects_chesscom_board` | `auto_find_chessboard()` with `chesscom_white.png` fixture returns a valid `Board_position` with `minX < maxX` |
| `test_hough_detects_lichess_board` | `auto_find_chessboard()` with `lichess_white.png` fixture returns a valid `Board_position` with `minX < maxX` |

**Clarification on `isready` vs `load()` staleness:** `load()` always returns data if the file exists (no mtime check). The `isready` handler is responsible for checking whether `board_position.bin` mtime is >24h and discarding stale data by calling `detect_and_save()` again. `load()` itself is a pure file reader.

---

### Phase 3 — Move Executor
**Goal:** Execute a player's UCI move as mouse clicks on the screen board.

**Files to create (tests first):**
- `tests/screen/test_executor.py` ← **write and commit before implementation**
- `src/uci_screen_bridge/screen/executor.py`

**Deliverable:** Given a detected board position, `executor.execute("e2e4")` clicks the correct squares.

**Acceptance criteria:**
- Correct pixel mapping for both white-on-bottom and black-on-bottom orientation
- Click-click and drag-drop modes both work
- Humanization delay applied (random 50–200ms between clicks)
- No import errors or crashes on a real browser window

#### Phase 3 Test Suite (`tests/screen/test_executor.py`)

| Test | Description |
|------|-------------|
| `test_execute_white_on_bottom` | `execute("e2e4")` with white-on-bottom calls `pyautogui.click` twice with correct pixel coordinates (mock pyautogui) |
| `test_execute_black_on_bottom` | `execute("e2e4")` with black-on-bottom (board flipped) calls `pyautogui.click` with correctly mirrored coordinates |
| `test_execute_small_board` | `execute("e2e4")` with `Board_position(minX=0,minY=0,maxX=400,maxY=400)` — coordinates scale correctly to 50px squares |
| `test_execute_large_board` | `execute("e2e4")` with `Board_position(minX=0,minY=0,maxX=1000,maxY=1000)` — coordinates scale correctly to 125px squares |
| `test_humanization_delay` | The time elapsed between the two clicks is within the 50–200ms range |
| `test_drag_drop_mode` | With `drag_drop=True`, calls `pyautogui.moveTo` + `pyautogui.dragTo` instead of two `click` calls |
| `test_execute_malformed_move_logs_error` | `execute("z9z9")` (invalid UCI) emits `info string ERROR:` and does NOT call `pyautogui.click` |
| `test_executor_handles_failsafe` | If PyAutoGUI raises `FailSafeException`, the executor catches it and emits `info string WARNING:` |
| `test_direct_internet_game_has_required_attrs` | `DirectInternetGame.__init__` sets all attributes that `Internet_game.move()` accesses (`position`, `we_play_white`, `drag_drop`, etc.) |
| `test_promotion_queen_chesscom` | `execute("e7e8q")` with ChessCom style: `pyautogui.click` lands on the queen-icon pixel (top icon in vertical stack, index 0) |
| `test_promotion_rook_chesscom` | `execute("e7e8r")` with ChessCom style: click lands on rook icon (index 2 in vertical stack) |
| `test_promotion_knight_chesscom` | `execute("e7e8n")` with ChessCom style: click lands on knight icon (index 1 in vertical stack) |
| `test_promotion_queen_lichess` | `execute("e7e8q")` with Lichess style: click lands on leftmost horizontal icon (index 0) |
| `test_promotion_rook_lichess` | `execute("e7e8r")` with Lichess style: click lands on second icon from left (index 1) |
| `test_promotion_black_side` | `execute("e2e1q")` (black promotion): dialog region is searched **below** the destination square, not above |
| `test_promotion_no_dialog_fallback` | Mock returns no dialog pixels for full 500ms: emits `info string WARNING: promotion dialog not detected on <square>`, speaks TTS alert (when enabled), polls for board-state change every 100ms, emits `info string ERROR:` after 10s and does NOT deadlock |
| `test_promotion_delayed_dialog` | Dialog absent at first 50ms poll but present at 300ms poll: detected and clicked correctly (tests polling, not fixed sleep) |
| `test_promotion_afile_clip` | Promotion on a-file or h-file: computed click x-coordinate is clamped to `[0, screen_width - 1]` |

Fixtures for promotion tests: `tests/fixtures/chesscom_promo_dialog.png`, `tests/fixtures/lichess_promo_dialog.png`, `tests/fixtures/no_promo_region.png`.

---

### Phase 4 — Move Detector
**Goal:** Detect an opponent move from screen pixels and return it as a UCI string.

**Files to create (tests first):**
- `tests/screen/test_detector.py` ← **write and commit before implementation**
- `src/uci_screen_bridge/screen/detector.py`

**Deliverable:** `detector.wait_for_move(board)` blocks until a legal opponent move appears on screen.

**Acceptance criteria:**
- Correctly detects normal moves, captures, and castling
- Double-confirmation (100ms anti-animation debounce) is active
- Promotion detection works for opponent promotions
- Does not return a move that was already in `board`'s history
- Returns `"0000"` when `MoveTimeout` is reached

#### Phase 4 Test Suite (`tests/screen/test_detector.py`)

All tests use the `mock_mss` fixture from `conftest.py` to supply board images from `tests/fixtures/`.

| Test | Description |
|------|-------------|
| `test_set_baseline_captures_image` | `set_baseline()` sets `game_state.previous_chessboard_image` to a non-None numpy array |
| `test_set_baseline_creates_classifier` | `set_baseline()` creates a `Classifier` instance on `game_state` |
| `test_set_baseline_called_twice_resets` | Calling `set_baseline()` twice resets to the *current* board state (does not accumulate) |
| `test_wait_for_move_detects_move` | Given before/after PNG fixtures for a known position (e.g., e2→e4), `wait_for_move()` returns `"e2e4"` |
| `test_capture_move_detected` | Before/after PNG fixtures for a capture (e.g., d4xc5): `wait_for_move()` returns `"d4c5"` |
| `test_double_confirmation_rejects_animation` | A move detected only on the first scan but not on the second (100ms later) is rejected; function continues waiting |
| `test_castling_detection` | Before/after image pair for king-side castling returns `"e1g1"` |
| `test_opponent_promotion_queen` | Before/after PNG pair where opponent promotes e7→e8 to queen: `wait_for_move()` returns `"e7e8q"` (not `"e7e8"`) |
| `test_opponent_promotion_rook` | Before/after PNG pair where opponent promotes e7→e8 to rook: `wait_for_move()` returns `"e7e8r"` |
| `test_scan_interval_is_respected` | The polling loop sleeps `scan_interval` seconds between scans (mock `time.sleep`, verify it's called with the correct value) |
| `test_wait_for_move_game_over_returns_null` | If `board.is_game_over()` is True, `wait_for_move()` returns `"0000"` immediately |
| `test_screen_capture_failure_retried` | If `sct.grab()` raises (e.g., window gone), the detector catches the exception and retries on the next poll cycle |
| `test_timeout_returns_null_move` | With `move_timeout_s=0.1` and a static board image (no move), returns `"0000"` within 1 second |

Fixtures for promotion tests: `tests/fixtures/board_before_promo.png`, `tests/fixtures/board_after_promo_queen.png`, `tests/fixtures/board_after_promo_rook.png`.

---

### Phase 5 — Integration & Entry Point
**Goal:** Wire all components into a working UCI engine binary.

**Files to create (tests first):**
- `tests/integration/test_uci_round_trip.py` ← **write and commit before implementation**
- `src/uci_screen_bridge/uci_bridge.py` (entry point; integrates `Speech_thread` for TTS alerts)

**Files to modify:**
- `pyproject.toml` — add new console script: `uci-screen-bridge-engine = "uci_screen_bridge.uci_bridge:main"`
- `requirements_dev.txt` — add `pytest>=8.0`, `pytest-mock>=3.12`, `Pillow>=10.0`

**Deliverable:** BearChess can configure the engine, make a move, and the engine returns an opponent move correctly.

**Acceptance criteria:**
- Full round-trip: physical board move → UCI `position` → screen click → CV scan → `bestmove` → board LED
- Works end-to-end with Chess.com in a browser
- No stdout pollution from debug prints (guard all debug output with `info string` prefix)

#### Phase 5 Test Suite — Tier 2 (`tests/integration/test_uci_round_trip.py`)

Full round-trip tests using pipe to the engine subprocess. All screen interactions are mocked via fixture injection.

| Test | Description |
|------|-------------|
| `test_uci_isready_sequence` | Sends `uci` then `isready`; receives `uciok` then `readyok` in correct order |
| `test_ucinewgame_then_position` | After `ucinewgame`, `position startpos moves e2e4` does not crash and executor is called |
| `test_go_returns_bestmove` | After setup, `go` returns a `bestmove <uci>` line within the configured timeout |
| `test_no_stdout_pollution` | A full session including `ucinewgame`, `setoption`, `position`, `go` produces no unexpected lines — every non-standard line has `info string` prefix. Verified even when `executor.execute()` calls `DirectInternetGame.move()` (which uses `_log.debug()` not `print()`) and when `calibration.detect_and_save()` calls `auto_find_chessboard()` via `find_chessboard_from_image()` (which uses `logger.warning()` not `print()`). `pyautogui` is mocked but the `move()` logging path runs. |
| `test_executor_called_on_player_move` | Mocked executor's `execute()` is called exactly once when playing white and a white move is issued |
| `test_setoption_before_isready_accepted` | `setoption` between `uci` and `isready` is accepted without error and applied at `isready` time |
| `test_position_fen_mid_game` | `position fen <mid-game-fen> moves e4d5` correctly parses a non-starting FEN and registers the move delta |
| `test_side_orientation_mismatch_warning` | If `Side = White` but calibration returns `we_play_white = False`, `info string WARNING:` is emitted |

#### Phase 5 Test Suite — Tier 3 (`tests/integration/test_bridge_real_board.py`)

End-to-end tests using a local HTML board served via `http.server` and controlled via playwright. Marked `@pytest.mark.integration` — excluded from `make test`, included in `make test-full`.

**Test flow:**
1. `local_board` fixture starts local HTTP server, opens `board.html` in a headed browser at fixed screen position, returns `(page, board_position)` to tests.
2. Spawn UCI engine subprocess.
3. Send `uci` / `isready` → engine auto-detects board via Hough-line from live screen pixels.
4. Send `position startpos moves e2e4` → engine clicks source (e2) + destination (e4) on browser board.
5. Verify: `page.evaluate("window.testBoard.getCurrentFen()")` matches expected FEN.
6. Apply opponent move via JS: `page.evaluate("window.testBoard.applyMove('e7e5')")`.
7. Send `go` → CV scan detects e7e5 from live screen pixels → returns `bestmove e7e5`.
8. Assert response equals `bestmove e7e5`.

| Test | Description |
|------|-------------|
| `test_engine_detects_board_on_isready` | Engine correctly identifies the local HTML board's position via Hough-line detection |
| `test_player_move_clicks_board` | `position startpos moves e2e4` causes PyAutoGUI to click on the correct squares; FEN changes match expected post-move position |
| `test_opponent_move_via_cv` | Applying `e7e5` via JS and sending `go` causes CV to detect and return `bestmove e7e5` |
| `test_castling_round_trip` | Full round-trip for `e1g1` castling (both the click and the CV detection of the rook move) |

---

### Phase 6 — Hardening & Edge Cases
**Goal:** Handle real-world failure modes robustly.

**Files to create (tests first):**
- Tests appended to or alongside existing phase test files

**Items:**

- **Board not found:** The guided calibration flow (FR2.6) handles this during `isready`. It polls for up to 60 seconds with user-facing prompts. If the board is still not detected after 60 seconds, the engine emits `info string ERROR: Chess board not found on screen. Please navigate to the chess board and use Recalibrate.` and continues without exiting — `readyok` is emitted so the Chess GUI does not hang. Subsequent `go` commands with a `None` board position emit `bestmove 0000` with an `info string ERROR`. The user resolves this by triggering the `Recalibrate` UCI option.
- **Move execution failure:** If `executor.execute()` raises (window not found, click fails), retry up to 3 times with 500ms backoff. If still failing after 3 retries, emit `info string ERROR: could not execute move` + TTS alert "Move execution failed, please check the screen" + output `bestmove 0000`.
- **Board state drift:** If the CV scan detects a move that doesn't match any legal move (e.g., premove, board refresh animation), emit `info string WARNING: illegal move detected, retrying`, reset `previous_chessboard_image` to the current frame, and retry. If drift persists for 3 consecutive scans, emit TTS "Board detection error, please check the window".
- **Scan timeout (MoveTimeout reached):** Emit `info string WARNING: move timeout after N seconds` + TTS "Move timeout, no opponent move detected" + `bestmove 0000`.
- **Calibration stale:** If saved `board_position.bin` is more than 24 hours old, discard it and re-run auto-detect on the next `isready`. Log `info string INFO: stale calibration data, re-detecting board`.
- **Window moved/resized:** If CV confidence drops below threshold for 3 consecutive scans, emit TTS "Chess board lost, recalibrating" and attempt re-detect.
- **Draw / resign / game over:** Detect via `board.is_game_over()` and emit appropriate `info string` messages.
- **TTS alerts:** All audible alerts require `TTSAlerts = true` (default). Use `Speech_thread` from `utils/speech.py` with English alert phrases only; no full game commentary infrastructure.

#### Phase 6 Test Suite

| Test | Description |
|------|-------------|
| `test_timeout_emits_null_bestmove` | `bestmove 0000` is emitted after `MoveTimeout` seconds with no detected move |
| `test_calibration_failure_emits_error` | When `auto_find_chessboard()` returns `None` for the full guided-flow timeout, `info string ERROR:` is emitted and `readyok` is still sent |
| `test_no_legal_moves_drift` | When `get_valid_move()` returns `None` for 3 consecutive scans, TTS is triggered and `previous_chessboard_image` is reset |
| `test_move_execution_retry` | If executor raises on first two attempts, third attempt succeeds; no `bestmove 0000` emitted |
| `test_move_execution_all_retries_fail` | If executor raises on all 3 attempts, `bestmove 0000` is emitted and TTS alert fires |
| `test_stale_calibration_triggers_redetect` | If `board_position.bin` mtime is >24h old, `isready` discards the file and re-runs detection |
| `test_tts_disabled_when_option_false` | With `TTSAlerts = false`, no call is made to `Speech_thread` even when an alert condition is triggered |
| `test_game_over_info_string_content` | When `board.is_game_over()` is True, emits `info string INFO: game over — <result>` (e.g., `info string INFO: game over — White wins by checkmate`) |

**Hardening spec clarification:** The "CV confidence drops below threshold" condition is defined as: `get_valid_move()` returns `None` (no legal move found) for 3 consecutive scan intervals. Remove all references to vague "confidence threshold" language; use this concrete definition instead.

---

## 8. Data Files (Runtime)

| File | Contents | Created by | Location |
|------|----------|-----------|----------|
| `board_position.bin` | Pickled `(Board_position, we_play_white: bool)` | Phase 2 calibration | `uci_data_path("board_position.bin")` |
| `uci-bridge.log` | Application log (debug/info/warning messages from all internal modules) | `uci_bridge.py` at startup via `_configure_logging()` | `uci_data_path("uci-bridge.log")` |

The existing `data/*.bin` files (constants, ssim, hog, gui, promotion) are not used by the new UCI engine path.

---

## 9. Entry Points Summary

| Command | Purpose |
|---------|---------|
| `uci-screen-bridge-engine` | **New:** UCI engine shim (stdin/stdout) — register this in Chess GUI |
| `python -m uci_screen_bridge.calibrate` | **New:** Standalone board detection + save |
| `uci-screen-bridge` | **Existing:** Tkinter GUI (webcam → online game, unchanged) |

---

## 10. Dependencies

Existing runtime libraries (already in `requirements.txt`):
- `python-chess` — board state tracking, legal move validation
- `opencv-python` — image processing (pixel diff, Canny, Hough, OCM, ONNX inference)
- `pyautogui` — mouse click simulation
- `mss` — fast screen capture
- `numpy` — pixel array manipulation
- `scikit-image` — SSIM (used by classifier pipeline)

**New runtime dependency** (add to `requirements.txt`):
- `platformdirs>=3.0` — OS-compliant user data directory for UCI data files (`uci_data_path()`)

**New test dependencies** (add to `requirements_dev.txt`):
- `pytest>=8.0` — test runner (`make test`)
- `pytest-mock>=3.12` — mocking for CV and screen-capture dependencies
- `Pillow>=10.0` — synthesizing and loading test images in fixtures
- `playwright>=1.40` — Tier 3 end-to-end tests (headed browser control for local HTML board)

---

## 11. Key Design Decisions & Rationale

### Why reuse `Game_state` from `commentator.py`?
It already implements the complete opponent move detection pipeline: screenshot → square diff → OCM classification → chess legality check → castling handling → animation debounce. This is the hardest part to get right and it's already proven to work against Chess.com and Lichess.

### Why not use SSIM/HOG/KNN for screen detection?
Those tiers of the detection cascade are designed for a physical webcam board (noisy, variable lighting, perspective distortion). The screen board is clean, high-resolution, and deterministic. The pixel-diff + OCM pipeline in `Game_state` is sufficient and much simpler.

### Why not keep the Tkinter GUI?
The UCI engine communicates entirely via stdin/stdout. The Chess GUI (BearChess/Fritz) already provides the user interface. A separate GUI would be redundant and would complicate the subprocess model. Configuration is handled via UCI options and the `calibrate` CLI.

### Why block on `go`?
UCI engines are expected to think and then respond. Since this bridge has no evaluation to do, it simply waits until the opponent makes their move on screen. This is the correct UCI behavior — the Chess GUI will wait for `bestmove` before allowing further input.

### Why `DirectInternetGame` subclass instead of `__new__`?
`Internet_game.__init__` expects GUI context (a settings object and running calibration state). Rather than calling `__new__` and manually setting attributes (fragile if the parent class changes), a thin subclass with an explicit `__init__` makes the bypass intentional and visible. If `Internet_game` is refactored, the subclass will fail loudly rather than silently.

### Why TTS alerts via `Speech_thread` and not a new mechanism?
`Speech_thread` is already cross-platform (macOS `say` / pyttsx3) and is a battle-tested daemon thread. Rather than re-implementing TTS plumbing, we reuse the wrapper and control it with the `TTSAlerts` UCI option. Only English alert phrases are used — no full commentary infrastructure.

### Thread safety
The UCI engine runs single-threaded on stdin. Move execution (Phase 3) and move detection (Phase 4) run synchronously in the main thread (called from the UCI loop). `Speech_thread` runs as a background daemon thread. This avoids the complexity of the existing multi-threaded architecture, which was necessary for the webcam loop but is not needed here.

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Screen board not detected | Hough-line auto-detect is default; retry loop up to 3×; `info string` diagnostic; manual recalibrate option |
| Animation causes false move detection | Double-confirmation (100ms) already in `Game_state` |
| Chess GUI sends `go` before player's move is reflected on screen | Executor performs click before returning control to `go` handler |
| Promotion dialog varies by site | `PromotionStyle` UCI option (`Auto`/`ChessCom`/`Lichess`); queen fallback with `info string WARNING` |
| HiDPI / Retina display coordinate scaling | After `mss.grab()`, compute `scale = logical_width / mss_image_pixel_width` (where `logical_width` is from `pyautogui.size()` and `mss_image_pixel_width` is the actual pixel width of the captured array). Divide all `Board_position` coordinate values by this scale before storing them. This normalises to logical coordinates once at calibration time; all downstream code (`get_square_center`, executor) uses logical coords naturally. Diagnostic: log `pyautogui.size()` vs mss physical dimensions at calibration startup. |
| Bot detection on chess sites | Humanization delay on clicks (FR3.3) |
| Test images not representative | Provide 4+ reference screenshots; supplement with synthetic numpy arrays for edge cases |
| `Internet_game` internals change | `DirectInternetGame` subclass fails loudly on breakage; easy to update |
| `Game_state.game_thread` coupling | `register_move_if_needed()` accesses `self.game_thread.played_moves`; `game_thread` defaults to `None` causing `AttributeError`. | Add `if self.game_thread is not None` guard in `commentator.py` before the premove check. Set `game_state.game_thread = None` in `set_baseline()`. No stub class required. |
| `auto_find_chessboard()` hard-exits | Function originally called `sys.exit(0)` on failure, which would silently kill the engine subprocess. | Modified `auto_find_chessboard()` to `return None, None` on failure; `detect_and_save()` checks for `None` and raises `BoardNotFoundError`. |

---

## 13. Logging Strategy

### 13.1 Rule

**`UCIEngine._emit()` is the only function allowed to write to stdout.** All internal debug/diagnostic output uses Python's `logging` module (to a file), never `print()`. This ensures stdout is a clean UCI protocol channel.

### 13.2 Configuration

| Aspect | Specification |
|--------|--------------|
| **Module** | Python stdlib `logging` — no new dependency |
| **Handler** | `logging.FileHandler` writing to `uci_data_path("uci-bridge.log")` (append mode) |
| **Format** | `%(asctime)s %(name)s %(levelname)s %(message)s` |
| **Setup** | `uci_bridge.py` calls `_configure_logging(level_name)` before `UCIEngine.run()` |
| **Per-module** | All internal modules use `logger = logging.getLogger(__name__)` |

### 13.3 LogLevel UCI Option

```
option name LogLevel type combo default INFO var DEBUG var INFO var WARNING var OFF
```

- `DEBUG` — verbose: every CV scan, every click coordinate, every move candidate
- `INFO` — default: move executions, calibration events, timeouts
- `WARNING` — errors and warnings only
- `OFF` — no log file written (`_configure_logging()` returns early without setting up a handler)

The `LogLevel` option is read from `setoption` and passed to `_configure_logging()` at `isready` time (first call) or immediately if set after startup.

### 13.4 Modules with Required print() → logger Migrations

| Module | Location | Change |
|--------|----------|--------|
| `calibration/chessboard_detection.py` | `find_chessboard_from_image()` line 151 | `print("Board is not square.")` → `logger.warning("Board is not square.")` |
| `calibration/chessboard_detection.py` | `find_chessboard_from_image()` line 159 | `print("Chess board of online game could not be found.")` → `logger.warning("Chess board of online game could not be found.")` |
| `online/internet_game.py` | `Internet_game.move()` | `print("Done playing move", ...)` → replaced by `_log.debug(...)` in `DirectInternetGame.move()` override (parent `move()` is not called) |

### 13.5 Verification

After implementation:
```bash
echo -e "uci\nisready\nposition startpos moves e2e4\ngo\nquit" | uci-screen-bridge-engine
```
Every output line must start with `id`, `option`, `uciok`, `readyok`, `info`, or `bestmove`.
The log file `data/uci-bridge.log` should contain the debug/warning messages instead.
