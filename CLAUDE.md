# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This application uses computer vision (webcam) to detect moves made on a physical chess board and replays them in an online chess interface—either via simulated mouse clicks (PyAutoGUI) or the Lichess API. All Python source files live flat in the root directory (no src/ subdirectory).

## Environment Setup

```bash
# Using conda (environment.yml defines Python 3.12 env named "uci-screen-bridge")
make venv
conda activate uci-screen-bridge

# Or install directly with pip
pip install -r requirements.txt
```

## Running the Application

```bash
python gui.py                  # Main entry point — launches Tkinter GUI
python board_calibration.py    # Board calibration (run from GUI normally)
python main.py                 # Game loop (run from GUI normally)
python diagnostic.py           # Diagnostic overlay view
```

The GUI spawns `board_calibration.py`, `main.py`, and `diagnostic.py` as subprocesses with CLI arguments.

## Architecture

### Process Model

`gui.py` (Tkinter) is the user-facing entry point. It spawns three types of subprocesses:
- **board_calibration.py** — Detects physical board corners, writes `constants.bin`
- **main.py** — Core game loop: webcam capture → move detection → online move execution
- **diagnostic.py** — Shows perspective-transformed board with piece detection overlay

### Main Game Loop (main.py)

Threads started by main.py:
- `Video_capture_thread` (videocapture.py) — continuously reads webcam frames into a Queue
- `Speech_thread` (speech.py) — TTS output via Queue (macOS: `say`, others: `pyttsx3`)

Game loop flow: read frame → KNN background subtraction → detect motion → wait for motion to stop → attempt move registration → execute move online → update KNN model.

### Move Registration Cascade (game.py)

`game.register_move()` tries 5 detection tiers in order, stopping at first success:
1. **CNN 2-move** — Detects opponent + player move together (`cnn_piece.onnx` + `cnn_color.onnx`)
2. **CNN single-move** — CNN-based single move detection
3. **SSIM** — Structural similarity scoring + chess legality check
4. **Canny edge** — Edge detection with ROI mask (empty-board calibration only)
5. **HOG + KNN** — HOG feature classifier (online-learned during game)

### Board Calibration Modes (board_calibration.py / board_calibration_machine_learning.py)

- **Empty board**: OpenCV `findChessboardCorners` on inner 7×7 grid, extrapolates outer corners
- **Starting position (ML)**: YOLO model (`yolo_corner.onnx`) detects 4 corners; CNN determines rotation
- **Just before game**: YOLO calibration triggered at game start time

### Online Play Backends

- `internet_game.py` — Simulates mouse clicks on any browser chess board (PyAutoGUI + mss screen capture)
- `lichess_game.py` — Uses Lichess Board API via `berserk` library

### Opponent Move Detection

- `commentator.py` (`Commentator_thread`) — Screen-captures the online board, uses Oriented Chamfer Matching (`classifier.py`) to detect piece changes
- `lichess_commentator.py` (`Lichess_commentator`) — Streams moves from Lichess API

### ML Models (ONNX, run via OpenCV DNN)

- `yolo_corner.onnx` — YOLOv8 model for detecting 4 board corners
- `cnn_piece.onnx` — CNN classifying a square as piece or empty
- `cnn_color.onnx` — CNN classifying piece color (white/black)

### Persisted State (pickle files, created at runtime)

- `constants.bin` — Board calibration data (corners, rotation, side-view compensation)
- `ssim.bin` — SSIM threshold values from initial frame
- `hog.bin` — KNN training data (HOG features, online-updated each game)
- `gui.bin` — GUI settings
- `promotion.bin` — Selected promotion piece

## Key Design Patterns

- **Subprocess isolation**: GUI and game logic run in separate processes, communicating via stdout
- **Thread-safe queues**: Webcam frames and TTS messages passed through `queue.Queue`
- **Multi-strategy degradation**: Move detection cascades through 5 methods for robustness
- **Online learning**: HOG/KNN classifier adapts to lighting changes during the game
- **Platform branching**: Camera API, TTS engine, and webcam enumeration branch on `platform.system()`

## No Tests

There is currently no test suite in this repository.
