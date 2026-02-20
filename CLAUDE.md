# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This application uses computer vision (webcam) to detect moves made on a physical chess board and replays them in an online chess interface — either via simulated mouse clicks (PyAutoGUI) or the Lichess API. The project uses a `src/` layout and must be installed as a package before running.

## Environment Setup

```bash
# Create the conda environment (Python 3.12, named "uci-screen-bridge")
make venv
conda activate uci-screen-bridge

# Install the package in editable mode (required — uses importlib.resources for model assets)
make install

# Rebuild the environment from scratch (useful after dependency changes)
make clean
```

## Running the Application

```bash
# Main entry point — launches the Tkinter GUI
python -m uci_screen_bridge.gui
# or via the installed console script:
uci-screen-bridge

# Subprocesses (normally spawned by the GUI, but can be run directly)
python -m uci_screen_bridge.calibration.board_calibration
python -m uci_screen_bridge.main
python -m uci_screen_bridge.diagnostic
```

> **Important:** The package must be installed (`make install`) before running any module. Raw `python src/...` invocations will fail with import errors.

## Project Structure

```text
uci-screen-bridge/
├── pyproject.toml                          # Build config (setuptools, src layout, console script)
├── environment.yml                         # Conda env spec (Python 3.12)
├── requirements.txt                        # Pinned runtime dependencies
├── requirements_dev.txt                    # Pinned dev dependencies (flake8, autopep8)
├── Makefile                                # venv / install / clean targets
├── data/                                   # Runtime-generated files (gitignored, created on first run)
│   ├── constants.bin                       # Board calibration data (corners, rotation, side-view)
│   ├── ssim.bin                            # SSIM threshold values per square type
│   ├── hog.bin                             # HOG/KNN training data (online-updated each game)
│   ├── gui.bin                             # Persisted GUI settings
│   └── promotion.bin                       # Selected promotion piece
└── src/
    └── uci_screen_bridge/
        ├── gui.py                          # Tkinter GUI — main entry point
        ├── main.py                         # Core game loop (subprocess entry point)
        ├── diagnostic.py                   # Diagnostic overlay (subprocess entry point)
        ├── calibration/
        │   ├── board_calibration.py        # Empty-board calibration (OpenCV chessboard corners)
        │   ├── board_calibration_machine_learning.py  # ML calibration (YOLO corner detection)
        │   └── chessboard_detection.py     # Screen-capture online board detection (Hough lines)
        ├── detection/
        │   ├── board_basics.py             # Board geometry, SSIM scoring, potential move calculation
        │   ├── classifier.py               # Oriented Chamfer Matching piece classifier
        │   └── game.py                     # Game class: 5-tier move registration cascade
        ├── models/                         # Bundled ML model assets (installed as package data)
        │   ├── cnn_color.onnx              # CNN: classifies piece color (white/black)
        │   ├── cnn_piece.onnx              # CNN: classifies square as piece or empty
        │   ├── yolo_corner.onnx            # YOLOv8: detects 4 board corners
        │   ├── white.JPG                   # Template: online board playing as white
        │   └── black.JPG                   # Template: online board playing as black
        ├── online/
        │   ├── commentator.py              # Screen-scraping opponent move detection (OCM)
        │   ├── internet_game.py            # PyAutoGUI browser click/drag backend
        │   ├── lichess_commentator.py      # Lichess API move streaming
        │   └── lichess_game.py             # Lichess Board API backend (berserk)
        └── utils/
            ├── helper.py                   # CV utilities: perspective transform, CNN predict, etc.
            ├── languages.py                # TTS language classes (English, German, Russian, Turkish, Italian, French)
            ├── paths.py                    # importlib.resources helpers: model_path(), data_path()
            ├── speech.py                   # Speech_thread (TTS via `say` on macOS, pyttsx3 elsewhere)
            └── videocapture.py             # Video_capture_thread (webcam frames into Queue)
```

## Architecture

### Process Model

`gui.py` (Tkinter) is the user-facing entry point. It spawns three types of subprocesses via `sys.executable -m <module>`, redirecting their stdout to the GUI log panel:

- **board_calibration.py** — Detects physical board corners, writes `data/constants.bin`
- **main.py** — Core game loop: webcam capture → move detection → online move execution
- **diagnostic.py** — Shows perspective-transformed board with piece detection overlay

### Package and Asset Resolution

- **ML models** (`*.onnx`, `*.JPG`) live in `uci_screen_bridge/models/` and are declared as package data in `pyproject.toml`. They are resolved via `importlib.resources.files("uci_screen_bridge.models")` in `utils/paths.py` (`model_path(filename)`).
- **Runtime data files** (`*.bin`) live in `data/` at the repo root. They are resolved via a filesystem path relative to `paths.py` (`data_path(filename)`). This works correctly only with an editable install; a site-packages install would resolve the path incorrectly.

### Main Game Loop (main.py)

Threads started by `main.py`:

- `Video_capture_thread` (`videocapture.py`) — continuously reads webcam frames into a `queue.Queue`
- `Speech_thread` (`speech.py`) — TTS output via `queue.Queue` (macOS: `say`, others: `pyttsx3`)

Game loop flow: read frame → perspective transform → KNN background subtraction → detect motion onset → wait for motion to stop → attempt move registration → execute move online → update KNN model.

Two `cv2.createBackgroundSubtractorKNN` instances are used:

- `motion_fgbg` — detects whether the board is being touched (learning rate 1.0 always)
- `move_fgbg` — captures the difference between before and after a move (learning rate 0.0 during moves)

### Move Registration Cascade (game.py)

`Game.register_move()` tries 5 detection tiers in order, stopping at first success:

1. **CNN 2-move** — Detects opponent + player moves together (`cnn_piece.onnx` + `cnn_color.onnx`)
2. **CNN single-move** — CNN-based single move detection
3. **SSIM** — Structural similarity scoring + chess legality check
4. **Canny edge** — Edge detection with ROI mask (empty-board calibration only)
5. **HOG + KNN** — HOG feature classifier (online-learned during game)

After each successful move, the KNN model is updated with the current frame (rolling 100-sample window).

### Board Calibration Modes

- **Empty board** (`board_calibration.py`): OpenCV `findChessboardCorners` on inner 7×7 grid, extrapolates outer corners, computes side-view compensation from edge length ratios, saves ROI edge mask.
- **Starting position / ML** (`board_calibration_machine_learning.py`): YOLOv8 (`yolo_corner.onnx`) detects 4 corners; CNNs determine rotation count (0–3) by checking which edge has black pieces.
- **Just before game** (`calibrate` CLI flag): ML calibration triggered at game start time.

### Online Play Backends

- `internet_game.py` — Finds the chess board on screen (template match or Hough-line auto-detect), then simulates mouse clicks or drag-and-drop (PyAutoGUI + mss).
- `lichess_game.py` — Uses Lichess Board API via `berserk`; reads promotion choice from `data/promotion.bin`.

### Opponent Move Detection

- `commentator.py` (`Commentator_thread`) — Screen-captures the online board, uses Oriented Chamfer Matching (`classifier.py`) to detect piece changes. Waits 100ms after initial detection to rule out animation artifacts.
- `lichess_commentator.py` (`Lichess_commentator`) — Streams moves from Lichess API via `berserk`. Supports takebacks via `unregister_move()`.

### ML Models (ONNX, run via OpenCV DNN)

- `yolo_corner.onnx` — YOLOv8 model for detecting 4 board corners (640×640 padded input, NMS post-processing)
- `cnn_piece.onnx` — CNN classifying a square as piece or empty (64×64 input, via `helper.predict()`)
- `cnn_color.onnx` — CNN classifying piece color: white or black (64×64 input, via `helper.predict()`)

### Persisted State (pickle files in `data/`, created at runtime)

- `constants.bin` — Board calibration data: `[is_machine_learning, (pts1, side_view_compensation, rotation_count)]`
- `ssim.bin` — SSIM threshold values from initial frame (per square type and piece color)
- `hog.bin` — KNN training data (HOG features, online-updated each game)
- `gui.bin` — GUI settings (checkboxes, dropdowns, spinbox values)
- `promotion.bin` — Selected promotion piece (written by GUI, read by `lichess_game.py`)

## Key Design Patterns

- **Subprocess isolation**: GUI and game logic run in separate processes, communicating via stdout
- **Thread-safe queues**: Webcam frames and TTS messages passed through `queue.Queue`
- **Multi-strategy degradation**: Move detection cascades through 5 methods for robustness
- **Online learning**: HOG/KNN classifier adapts to lighting changes during the game
- **Platform branching**: Camera API (`CAP_AVFOUNDATION` / `CAP_V4L2` / `CAP_DSHOW`), webcam enumeration, and TTS engine all branch on `platform.system()`

## Code Style

- PEP 8 enforced; run `flake8 src/ --max-line-length=100` to check
- Format with `autopep8 --in-place --max-line-length=100 --aggressive --aggressive --recursive src/`

## No Tests

There is currently no test suite in this repository.
