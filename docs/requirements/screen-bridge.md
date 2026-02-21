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

## 3. Existing Code Inventory & Reuse Plan

### 3.1 Directly Reusable (no modification)

| Module | What it does | Used for |
|--------|-------------|----------|
| `online/internet_game.py` → `Internet_game` | Maps UCI move string to screen coordinates, executes PyAutoGUI click/drag | Player move execution |
| `calibration/chessboard_detection.py` | Template-match or Hough-line board detection; returns `Board_position(minX,minY,maxX,maxY)` and `we_play_white` | Board location at startup |
| `online/commentator.py` → `Game_state` | Captures board region via mss, diffs square images, validates moves against `python-chess` legality, handles castling/promotion/premove | Opponent move detection |
| `detection/classifier.py` → `Classifier` | Oriented Chamfer Matching to identify piece type per square (needed by `Game_state.get_valid_move()`) | Piece classification during move validation |
| `utils/paths.py` | `model_path()`, `data_path()` | All asset/data file resolution |

### 3.2 Partially Reusable (adapt or wrap)

| Module | Reusable part | Change needed |
|--------|--------------|---------------|
| `online/commentator.py` → `Commentator_thread` | `Game_state` inner class is the real logic | The thread wrapper needs to be replaced with a call-on-demand pattern driven by UCI `go` commands |
| `calibration/chessboard_detection.py` → `find_chessboard()` / `auto_find_chessboard()` | Board location logic | Save/load board position to/from `data/board_position.bin` for persistence across engine invocations |

### 3.3 Not Needed (webcam/physical-board specific)

- `calibration/board_calibration.py` — physical corner detection
- `calibration/board_calibration_machine_learning.py` — YOLO corner detection on webcam
- `detection/board_basics.py` — perspective transform, SSIM, physical board geometry
- `utils/videocapture.py` — webcam thread
- `utils/speech.py` — TTS output
- `utils/languages.py` — TTS language support
- `main.py` (current) — webcam game loop
- `gui.py` — Tkinter GUI
- `diagnostic.py` — webcam overlay

---

## 4. Functional Requirements

### FR1: UCI Protocol Compliance
The engine must run as a standalone subprocess called by the Chess GUI, communicating via stdin/stdout.

- **FR1.1 Handshake:** Respond correctly to `uci`, `isready`, `ucinewgame`.
- **FR1.2 Position tracking:** Parse `position [startpos | fen <fen>] [moves <move_list>]`. Maintain an internal `chess.Board` that mirrors the GUI's board state.
- **FR1.3 Move delta detection:** After each `position` command, compare the new moves list to the previous. If a new move appeared AND it is the player's move (i.e., the side we play), execute it on screen immediately.
- **FR1.4 Go command:** On `go` (any variant: `go`, `go infinite`, `go movetime N`, `go wtime ... btime ...`), enter the CV scan loop to detect the opponent's move on screen. Block until a move is confirmed, then output `bestmove <move>`.
- **FR1.5 Quit:** On `quit`, release resources and exit cleanly.
- **FR1.6 UCI options:** Expose configuration as UCI options so the Chess GUI can pass settings without a separate config file. Minimum set:
  - `option name Side type combo default White var White var Black` — which color we play
  - `option name CalibrationMethod type combo default Auto var Auto var Template` — board detection method
  - `option name ScanInterval type spin default 500 min 100 max 2000` — milliseconds between CV scans
  - `option name DragDrop type check default false` — use drag-and-drop vs. two-click

### FR2: Board Calibration
The bridge must know where the chess board is on screen before play begins.

- **FR2.1 Auto-detect:** Use Hough-line detection (`auto_find_chessboard()`) to automatically locate the board from a screenshot. This is the default and requires no user action.
- **FR2.2 Template-match:** Use existing `white.JPG` / `black.JPG` templates via `find_chessboard()` as a fallback.
- **FR2.3 Persistence:** Save the detected `Board_position` and `we_play_white` flag to `data/board_position.bin` (pickle). On subsequent `isready`, load from file to avoid re-detection.
- **FR2.4 Calibration command:** Support a custom UCI command `setoption name Recalibrate value true` or a separate CLI (`python -m uci_screen_bridge.calibrate`) to re-run board detection.
- **FR2.5 Orientation:** The board detection already returns `we_play_white` via `is_white_on_bottom()`. Confirm this matches the side configured via UCI option. Warn (via `info string`) if there is a mismatch.

### FR3: Move Execution (UCI → Screen)
When the player makes a move, execute it via simulated mouse input.

- **FR3.1 Coordinate mapping:** Reuse `Internet_game.get_square_center(square_name)` which already accounts for board orientation.
- **FR3.2 Click sequence:** Click source square, then destination square. Support drag-and-drop mode.
- **FR3.3 Humanization:** Introduce a small random delay (50–200ms) between clicks to avoid bot detection.
- **FR3.4 Promotion:** If the move includes a promotion piece (e.g., `e7e8q`), after the destination click, detect and click the promotion dialog. Strategy: after clicking the destination, take a screenshot and look for the promotion piece picker in the expected screen region.
- **FR3.5 Move confirmation:** After executing, optionally take a screenshot and verify the source square is now empty (lightweight sanity check).

### FR4: Opponent Move Detection (Screen → UCI)
When `go` is received, scan the screen for the opponent's move and return it as `bestmove`.

- **FR4.1 Baseline capture:** At the time `go` is received, capture the current board image as the baseline (equivalent to `previous_chessboard_image` in `Game_state`).
- **FR4.2 Scan loop:** Poll at `ScanInterval` ms. Capture current board image and compute per-square pixel diffs using `Game_state.get_potential_moves()`.
- **FR4.3 Move validation:** Use `Game_state.get_valid_move()` which validates candidates against `python-chess` legal moves and the OCM classifier.
- **FR4.4 Animation debounce:** Reuse the existing double-confirmation logic from `Game_state.register_move_if_needed()`: if a candidate move is detected, wait 100ms and re-check — only accept if the same move is still seen (avoids animation artifacts).
- **FR4.5 Output:** When confirmed, print `bestmove <uci_move>` and flush stdout. Update internal board state.
- **FR4.6 Castling:** `Game_state.get_valid_move()` already handles all four castling patterns explicitly.
- **FR4.7 Promotion:** `Game_state.get_valid_move()` already handles promotion detection via classifier output.

---

## 5. Technical Architecture

### 5.1 New Module Structure

```text
src/uci_screen_bridge/
├── uci/
│   ├── __init__.py
│   └── engine.py           # UCIEngine class — main UCI loop
├── screen/
│   ├── __init__.py
│   ├── calibration.py      # Board detection + persistence (wraps chessboard_detection.py)
│   ├── executor.py         # Player move execution (wraps Internet_game)
│   └── detector.py         # Opponent move detection (wraps Game_state)
├── uci_bridge.py           # Entry point: wire UCI engine + screen components
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

### 5.2 UCIEngine State Machine

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
                    │  - CV poll loop         │                      │
                    │  - Detect opponent move │                      │
                    │  - Print bestmove       │──────────────────────┘
                    └─────────────────────────┘
```

### 5.3 UCI `position` Parsing Logic

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

### 5.4 `go` Command Handler

```python
def _handle_go(self, command):
    # Capture baseline board image at go time
    self.detector.set_baseline()
    # Block-scan for opponent move
    opponent_move = self.detector.wait_for_move(self.board)
    # Update internal state
    self.board.push(chess.Move.from_uci(opponent_move))
    self.played_moves.append(opponent_move)
    # Return to UCI
    print(f"bestmove {opponent_move}")
    sys.stdout.flush()
```

### 5.5 `screen/detector.py` — MoveDetector

Wraps `Game_state` from `commentator.py`:

```python
class MoveDetector:
    def __init__(self, board_position, we_play_white, scan_interval_ms):
        self.game_state = Game_state()
        self.game_state.board_position_on_screen = board_position
        self.game_state.we_play_white = we_play_white
        self.scan_interval = scan_interval_ms / 1000.0
        self.game_state.sct = mss.mss()

    def set_baseline(self):
        self.game_state.previous_chessboard_image = self.game_state.get_chessboard()
        self.game_state.classifier = Classifier(self.game_state)

    def wait_for_move(self, board):
        self.game_state.board = board.copy()
        while True:
            found, move = self.game_state.register_move_if_needed()
            if found:
                return move.uci() if hasattr(move, 'uci') else move
            time.sleep(self.scan_interval)
```

### 5.6 `screen/executor.py` — MoveExecutor

Thin wrapper around `Internet_game`:

```python
class MoveExecutor:
    def __init__(self, board_position, we_play_white, drag_drop):
        self.game = Internet_game.__new__(Internet_game)
        self.game.position = board_position
        self.game.we_play_white = we_play_white
        self.game.drag_drop = drag_drop

    def execute(self, uci_move_str):
        move = chess.Move.from_uci(uci_move_str)
        # random humanization delay
        time.sleep(random.uniform(0.05, 0.2))
        self.game.move(move)
```

### 5.7 `screen/calibration.py` — BoardCalibration

```python
SAVE_FILE = data_path("board_position.bin")

def detect_and_save(method="auto"):
    if method == "template":
        position, we_play_white = find_chessboard()
    else:
        position, we_play_white = auto_find_chessboard()
    with open(SAVE_FILE, 'wb') as f:
        pickle.dump((position, we_play_white), f)
    return position, we_play_white

def load():
    if not SAVE_FILE.exists():
        return None, None
    with open(SAVE_FILE, 'rb') as f:
        return pickle.load(f)
```

---

## 6. Implementation Phases

### Phase 1 — UCI Engine Skeleton
**Goal:** A working UCI loop that correctly handshakes and parses position/go commands.

**Files to create:**
- `src/uci_screen_bridge/uci/__init__.py`
- `src/uci_screen_bridge/uci/engine.py`

**Deliverable:** Running `echo -e "uci\nisready\nquit"` piped to the engine produces correct UCI handshake output.

**Acceptance criteria:**
- Responds to `uci` with `id name UCI Screen Bridge`, `id author [name]`, UCI options, `uciok`
- Responds to `isready` with `readyok`
- Responds to `ucinewgame` by resetting internal board
- Parses `position startpos moves e2e4 e7e5` correctly
- Exits cleanly on `quit`

---

### Phase 2 — Board Calibration
**Goal:** Detect the chess board on screen and persist its position.

**Files to create:**
- `src/uci_screen_bridge/screen/__init__.py`
- `src/uci_screen_bridge/screen/calibration.py`

**Deliverable:** Running `python -m uci_screen_bridge.calibrate` detects the board and saves `data/board_position.bin`.

**Acceptance criteria:**
- Auto-detect works against Chess.com and Lichess boards
- Template-match works as fallback
- `we_play_white` is correctly determined
- Saved data loads correctly on next engine start
- If no saved data, auto-detect runs on `isready`

---

### Phase 3 — Move Executor
**Goal:** Execute a player's UCI move as mouse clicks on the screen board.

**Files to create:**
- `src/uci_screen_bridge/screen/executor.py`

**Deliverable:** Given a detected board position, `executor.execute("e2e4")` clicks the correct squares.

**Acceptance criteria:**
- Correct pixel mapping for both white-on-bottom and black-on-bottom orientation
- Click-click and drag-drop modes both work
- Humanization delay applied (random 50–200ms between clicks)
- No import errors or crashes on a real browser window

---

### Phase 4 — Move Detector
**Goal:** Detect an opponent move from screen pixels and return it as a UCI string.

**Files to create:**
- `src/uci_screen_bridge/screen/detector.py`

**Deliverable:** `detector.wait_for_move(board)` blocks until a legal opponent move appears on screen.

**Acceptance criteria:**
- Correctly detects normal moves, captures, and castling
- Double-confirmation (100ms anti-animation debounce) is active
- Promotion detection works for opponent promotions
- Does not return a move that was already in `board`'s history

---

### Phase 5 — Integration & Entry Point
**Goal:** Wire all components into a working UCI engine binary.

**Files to create:**
- `src/uci_screen_bridge/uci_bridge.py` (entry point)

**Files to modify:**
- `pyproject.toml` — add new console script: `uci-screen-bridge-engine = "uci_screen_bridge.uci_bridge:main"`

**Deliverable:** BearChess can configure the engine, make a move, and the engine returns an opponent move correctly.

**Acceptance criteria:**
- Full round-trip: physical board move → UCI `position` → screen click → CV scan → `bestmove` → board LED
- Works end-to-end with Chess.com in a browser
- No stdout pollution from debug prints (guard all debug output with `info string` prefix)

---

### Phase 6 — Hardening & Edge Cases
**Goal:** Handle real-world failure modes robustly.

**Items:**
- **Board not found:** If calibration fails on startup, emit `info string ERROR: chess board not found on screen. Please navigate to chess board and restart.` and enter a retry loop.
- **Scan timeout:** If `wait_for_move()` runs for > N seconds (configurable UCI option `MoveTimeout`), emit `bestmove 0000` (null move) to unblock the GUI.
- **Board state drift:** If the CV scan detects a move that doesn't match any legal move (e.g., premove, board refresh animation), log via `info string` and retry.
- **Reconnect:** If the screen board disappears (window closed/minimized), re-run calibration or pause until board reappears.
- **Draw / resign / game over:** Detect via `board.is_game_over()` and emit appropriate `info string` messages.

---

## 7. Data Files (Runtime)

| File | Contents | Created by |
|------|----------|-----------|
| `data/board_position.bin` | Pickled `(Board_position, we_play_white: bool)` | Phase 2 calibration |

The existing `data/*.bin` files (constants, ssim, hog, gui, promotion) are not used by the new UCI engine path.

---

## 8. Entry Points Summary

| Command | Purpose |
|---------|---------|
| `uci-screen-bridge-engine` | **New:** UCI engine shim (stdin/stdout) — register this in Chess GUI |
| `python -m uci_screen_bridge.calibrate` | **New:** Standalone board detection + save |
| `uci-screen-bridge` | **Existing:** Tkinter GUI (webcam → online game, unchanged) |

---

## 9. Dependencies

All needed libraries already exist in `requirements.txt`:
- `python-chess` — board state tracking, legal move validation
- `opencv-python` — image processing (pixel diff, Canny, Hough, OCM, ONNX inference)
- `pyautogui` — mouse click simulation
- `mss` — fast screen capture
- `numpy` — pixel array manipulation
- `scikit-image` — SSIM (used by classifier pipeline)

No new dependencies are needed.

---

## 10. Key Design Decisions & Rationale

### Why reuse `Game_state` from `commentator.py`?
It already implements the complete opponent move detection pipeline: screenshot → square diff → OCM classification → chess legality check → castling handling → animation debounce. This is the hardest part to get right and it's already proven to work against Chess.com and Lichess.

### Why not use SSIM/HOG/KNN for screen detection?
Those tiers of the detection cascade are designed for a physical webcam board (noisy, variable lighting, perspective distortion). The screen board is clean, high-resolution, and deterministic. The pixel-diff + OCM pipeline in `Game_state` is sufficient and much simpler.

### Why not keep the Tkinter GUI?
The UCI engine communicates entirely via stdin/stdout. The Chess GUI (BearChess/Fritz) already provides the user interface. A separate GUI would be redundant and would complicate the subprocess model. Configuration is handled via UCI options and the `calibrate` CLI.

### Why block on `go`?
UCI engines are expected to think and then respond. Since this bridge has no evaluation to do, it simply waits until the opponent makes their move on screen. This is the correct UCI behavior — the Chess GUI will wait for `bestmove` before allowing further input.

### Thread safety
The UCI engine runs single-threaded on stdin. Move execution (Phase 3) and move detection (Phase 4) run synchronously in the main thread (called from the UCI loop). This avoids the complexity of the existing multi-threaded architecture, which was necessary for the webcam loop but is not needed here. If performance becomes an issue, the executor click can be moved to a background thread.

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Screen board not detected | Template fallback + retry loop + `info string` diagnostic |
| Animation causes false move detection | Double-confirmation (100ms) already in `Game_state` |
| Chess GUI sends `go` before player's move is reflected on screen | Executor performs click before returning control to `go` handler |
| Promotion dialog varies by site | Phase 3 hardening: after destination click, scan for promotion widget |
| HiDPI / Retina display coordinate scaling | PyAutoGUI handles this via screen coordinate space; mss captures at physical resolution. Verify during testing |
| Bot detection on chess sites | Humanization delay on clicks (FR3.3) |
