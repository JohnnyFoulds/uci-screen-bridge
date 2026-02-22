# UCI Screen Bridge

A UCI engine shim that lets electronic board users play on any chess website by connecting their Chess GUI (BearChess, Fritz, Arena) to any chess board visible on the computer screen.

## Overview

**Problem solved:** Electronic board users (e.g. Chessnut Air via DGT/UCI drivers) are typically limited to Lichess. This bridge opens up Chess.com, YouTube, puzzle apps, and any other website or app that displays a chess board.

**How it works:**
1. Chess GUI sends player moves via UCI `position` commands → bridge simulates mouse clicks on the target screen window
2. Bridge CV-scans the screen for opponent moves → sends detected move back as UCI `bestmove` → GUI triggers board LEDs and registers the opponent's move
3. Chess GUI drives the hardware (piece LEDs, move input); bridge handles all screen interaction

```
[ Electronic Board ] ──> [ Chess GUI (BearChess/Fritz/Arena) ]
                                       │  UCI stdin/stdout
                                       ▼
                            [ UCI Screen Bridge ]
                                       │
                           ┌───────────┴───────────┐
                      Screen Clicks           CV Screen Scan
                           │                       │
                           ▼                       ▼
                  [ Chess Website / App (Chess.com, Lichess, …) ]
```

## Installation

```bash
# Create the conda environment (Python 3.12, named "uci-screen-bridge")
make venv
conda activate uci-screen-bridge

# Install the package in editable mode (required before running)
make install
```

Alternatively, install dependencies directly:

```bash
pip install -r requirements.txt
pip install -e .
```

## Usage

1. Open the target chess website or app in a browser
2. Configure your Chess GUI to use `uci-screen-bridge-engine` as a UCI engine (point it to the installed console script)
3. Start a game in the Chess GUI — the bridge auto-detects the board on screen at startup
4. Play moves on your electronic board; the bridge clicks them on screen and reports opponent moves back to the GUI

To re-run board detection manually:

```bash
python -m uci_screen_bridge.calibrate
```

## Board Detection

The bridge auto-detects the chess board on screen using Hough-line detection (`auto_find_chessboard()`). No template images or user action required. The detected board position is saved to `data/board_position.bin` and reused on subsequent starts.

If auto-detect fails (e.g. unusual board styling), set the UCI option `CalibrationMethod` to `Template` in your Chess GUI to use the bundled template images instead.

## Configuration (UCI Options)

All settings are exposed as UCI options and are visible directly in your Chess GUI's engine configuration dialog:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `Side` | combo | `Auto` | Which color we play: `Auto` (detected from screen), `White`, or `Black` |
| `CalibrationMethod` | combo | `Auto` | Board detection: `Auto` (Hough-line) or `Template` (bundled images) |
| `ScanInterval` | spin | `500` | Milliseconds between CV scans for opponent moves |
| `DragDrop` | check | `false` | Use drag-and-drop instead of two-click for move execution |
| `MoveTimeout` | spin | `60` | Seconds to wait for opponent move before emitting `bestmove 0000` |
| `Recalibrate` | button | — | Re-detect the board on screen without restarting |
| `TTSAlerts` | check | `true` | Enable audio alerts for critical events (board not found, move failed) |
| `PromotionStyle` | combo | `Auto` | Promotion dialog handling: `Auto`, `ChessCom`, or `Lichess` |

## Development

Full specification and TDD implementation plan: [`docs/requirements/screen-bridge.md`](docs/requirements/screen-bridge.md)

This project follows strict TDD — tests are written before implementation. Run the test suite:

```bash
make test        # Tier 1 + Tier 2 — headless, no screen required (CI)
make test-full   # All tiers including Tier 3 (requires a display and browser)
```

## Required Libraries

Dependencies are listed in `requirements.txt` and installed automatically via `make install` or `pip install -r requirements.txt`:

- opencv-python
- python-chess
- pyautogui
- mss
- numpy
- pyttsx3
- scikit-image
- pygrabber
- berserk
