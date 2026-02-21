# Plan: Repurpose Repo as UCI Screen Bridge Engine

## Context
The repo is being completely repurposed. The webcam/physical-board code is removed. The new application is a UCI chess engine that relays between a chess GUI (BearChess/Fritz) and any on-screen chess board:
- **Player move:** UCI `position` + `go` → detect new player move → simulate mouse clicks on screen
- **Opponent move:** screen pixel-diff CV → detected move → UCI `bestmove` response

Users with electronic boards (e.g. Chessnut Air via DGT/UCI driver) can play against any website or app.

---

## Phase 1: Delete Webcam / Physical Board Code

### Directories to delete entirely
```
src/uci_screen_bridge/detection/        # board_basics.py, classifier.py, game.py
src/uci_screen_bridge/online/           # internet_game.py, commentator.py, lichess_*.py
```

### Individual files to delete
```
src/uci_screen_bridge/gui.py
src/uci_screen_bridge/main.py
src/uci_screen_bridge/diagnostic.py
src/uci_screen_bridge/calibration/board_calibration.py
src/uci_screen_bridge/calibration/board_calibration_machine_learning.py
src/uci_screen_bridge/utils/speech.py
src/uci_screen_bridge/utils/languages.py
src/uci_screen_bridge/utils/videocapture.py
src/uci_screen_bridge/utils/helper.py   # CV utils for webcam; not needed
src/uci_screen_bridge/models/yolo_corner.onnx
src/uci_screen_bridge/models/cnn_color.onnx
src/uci_screen_bridge/models/cnn_piece.onnx
```

### Files to keep
```
src/uci_screen_bridge/calibration/chessboard_detection.py  # Board_position, auto_find_chessboard()
src/uci_screen_bridge/utils/paths.py                       # data_path(), model_path()
src/uci_screen_bridge/models/white.JPG                     # template for auto-calibration
src/uci_screen_bridge/models/black.JPG                     # template for auto-calibration
```

---

## Phase 2: Create Bridge Module

### New files

#### `src/uci_screen_bridge/bridge/__init__.py`
Empty.

#### `src/uci_screen_bridge/bridge/screen_board.py`
Single class `ScreenBoard` — all screen interaction in one place.

**State:**
- `position: Board_position` — board pixel bounds (loaded from calibration)
- `white_on_bottom: bool` — board orientation
- `sct: mss.mss()` — screen capture

**Public interface:**
```python
click_move(move_uci: str, delay_ms: int)
    # Parse move_uci ("e2e4"), calc pixel coords, pyautogui.click×2
    # ±20% random delay jitter for humanization

wait_for_move(board: chess.Board, timeout_secs: int) -> str
    # Take baseline screenshot
    # Poll every 0.5s; when ≥2 squares change:
    #   re-verify 100ms later (anti-animation guard)
    #   validate against board.legal_moves
    # Return UCI move string, raise TimeoutError on expiry
```

**Private helpers:**
```python
_get_board_img() -> np.ndarray
    # mss screenshot → crop to position bounds → resize 800×800 grayscale

_square_center(square_name: str) -> (int, int)
    # convert algebraic name to pixel coords using Board_position bounds + orientation

_name_to_row_col(square_name: str) -> (int, int)
    # "e4" → (row, col) respecting white_on_bottom

_get_square_img(row, col, img) -> np.ndarray
    # slice 800×800 image into 100×100 square, trim 6px borders

_square_changed(old, new) -> bool
    # cv2.absdiff(old, new).mean() > 8.0

_find_changed(old_img, new_img) -> list[str]
    # all square names where the image changed

_validate(changed: list[str], board: chess.Board) -> str
    # try all (src, dst) pairs from changed squares against board.legal_moves
    # handles normal moves, castling, en passant (all work via legal_moves check)
    # returns UCI string or ""
```

#### `src/uci_screen_bridge/bridge/uci_engine.py`
Class `UCIEngine` — UCI protocol loop.

**State:**
- `board: chess.Board`
- `move_list: list[str]` — moves parsed from latest `position` command
- `clicks_done: int` — count of moves already clicked on screen
- `screen: ScreenBoard`
- `scan_timeout: int`, `click_delay: int`, `anim_wait_ms: int`

**Protocol handlers:**
```python
run()             # main stdin loop; dispatches commands
_uci()            # print id name/author, options, uciok
_isready()        # print readyok
_ucinewgame()     # reset board + move_list + clicks_done
_setoption(cmd)   # update scan_timeout / click_delay / anim_wait_ms
_position(cmd)    # rebuild board from "startpos moves ..." or "fen ... moves ..."
_go(cmd)          # core action (see flow below)
```

**`_go()` flow:**
1. If `clicks_done < len(move_list)`: call `screen.click_move(move_list[clicks_done], click_delay)` → increment `clicks_done`
2. `time.sleep(anim_wait_ms / 1000)`
3. `move = screen.wait_for_move(self.board, scan_timeout)`
4. `print(f"bestmove {move}")` + `sys.stdout.flush()`

**UCI options:**
```
ScanTimeoutSecs  spin  default=120  min=10   max=600
ClickDelayMs     spin  default=100  min=0    max=1000
AnimationWaitMs  spin  default=1000 min=0    max=5000
```

**`main()` entry point:** instantiate `UCIEngine` (which constructs `ScreenBoard`, which loads calibration). Print clear error to stderr and exit if `data/bridge_calibration.bin` not found.

#### `src/uci_screen_bridge/bridge/calibrator.py`
Standalone tool, `main()` entry point.

```python
# Manual mode (default):
#   1. Print: "Move your mouse to the TOP-LEFT corner of the board, then press Enter"
#   2. input() to pause → pyautogui.position() → top_left
#   3. Repeat for BOTTOM-RIGHT corner
#   4. input("Is White on the bottom? [y/n]: ") → white_on_bottom
#   5. pickle.dump((Board_position(minX, minY, maxX, maxY), white_on_bottom), f)

# --auto flag:
#   auto_find_chessboard() → Board_position
#   is_white_on_bottom(board_screenshot) → bool
#   Same save step
```

Saves to `data/bridge_calibration.bin`.

---

## Phase 3: Update Existing Files

### `pyproject.toml`
```toml
[project.scripts]
uci-bridge           = "uci_screen_bridge.bridge.uci_engine:main"
uci-bridge-calibrate = "uci_screen_bridge.bridge.calibrator:main"

[tool.setuptools.package-data]
"uci_screen_bridge.models" = ["*.JPG"]   # only white.JPG, black.JPG remain
```

Remove the old `uci-screen-bridge = "uci_screen_bridge.gui:main"` entry.

### `requirements.txt`
Remove packages no longer needed:
- `pyttsx3` (TTS)
- `pygrabber` (Windows webcam)
- `berserk` (Lichess API)
- `scikit-image` (SSIM in deleted board_basics.py)

Keep: `opencv-python`, `python-chess`, `pyautogui`, `mss`, `numpy`

### `environment.yml`
Mirror the same removals.

### `CLAUDE.md`
Rewrite to describe the new UCI bridge architecture, entry points, and project structure.

---

## Final Directory Structure

```
uci-screen-bridge/
├── pyproject.toml
├── environment.yml
├── requirements.txt
├── requirements_dev.txt
├── Makefile
├── data/                               # runtime-generated (gitignored)
│   └── bridge_calibration.bin
└── src/
    └── uci_screen_bridge/
        ├── bridge/
        │   ├── __init__.py
        │   ├── uci_engine.py           # UCI protocol loop
        │   ├── screen_board.py         # click + scan screen interaction
        │   └── calibrator.py           # one-time calibration tool
        ├── calibration/
        │   └── chessboard_detection.py # auto-calibration backend (kept)
        ├── models/
        │   ├── white.JPG
        │   └── black.JPG
        └── utils/
            └── paths.py               # data_path() / model_path()
```

---

## Data Flow

```
Chess GUI (BearChess/Fritz)
  │  position startpos moves e2e4
  │  go
  ▼
UCIEngine._go()
  ├─► ScreenBoard.click_move("e2e4")   → pyautogui clicks e2 then e4
  ├─► time.sleep(anim_wait)
  ├─► ScreenBoard.wait_for_move(board) → pixel diff → legal move validation
  └─► print("bestmove e7e5") + flush
  ▼
GUI receives e7e5 → lights up board LEDs for human's next move
```

---

## Verification

1. **Flake8 clean** on all new + kept files: `flake8 src/ --max-line-length=100`
2. **Calibrate:** `uci-bridge-calibrate` → verify `data/bridge_calibration.bin` exists
3. **Manual UCI smoke test:** `python -m uci_screen_bridge.bridge.uci_engine`, type:
   ```
   uci       → id + options + uciok
   isready   → readyok
   ucinewgame
   position startpos moves e2e4
   go        → e2→e4 clicked on screen, scanner starts
   ```
   Make a move on the online board → verify `bestmove` printed
4. **Integration:** Configure `uci-bridge` as engine in Arena/BearChess
