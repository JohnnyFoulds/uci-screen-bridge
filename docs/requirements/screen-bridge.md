# Project: UCI Screen Bridge (Universal Chess Interface to Computer Vision)

## 1. Executive Summary
**Goal:** Develop a Python-based application that acts as a standard UCI Chess Engine but functions as a bridge between a Chess GUI (e.g., BearChess, Fritz) and any visible chessboard on the computer screen (e.g., Chess.com, Lichess, YouTube, or obscure puzzle apps).

**Problem Solved:** Allows users with electronic chess boards (specifically the Chessnut Air via standard DGT/UCI drivers) to play against *any* app or website by using their preferred GUI as the hardware manager.

**Mechanism:**
1.  **Input:** Receives moves from the GUI via UCI protocol (simulating user hardware input) $\rightarrow$ Simulates Mouse Clicks on the screen.
2.  **Output:** Monitors screen pixels for opponent moves via Computer Vision (CV) $\rightarrow$ Sends moves back to GUI via UCI `bestmove` command to trigger board LEDs.

---

## 2. System Architecture

```text
[ Physical Board ] <--> [ Drivers ] <--> [ Chess GUI (BearChess/Fritz) ]
                                                |
                                          (UCI Protocol)
                                                v
                                     [ UCI Screen Bridge (Python) ]
                                        /                \
                                  (Mouse Click)      (Computer Vision)
                                      /                    \
                            [ Web Browser / 3rd Party App Window ]
```

---

## 3. Functional Requirements (FR)

### FR1: UCI Protocol Compliance
The software must run as a standalone executable (or script) that communicates via Standard Input/Output (stdin/stdout) using the Universal Chess Interface (UCI) protocol.
*   **FR1.1:** Must respond to `uci`, `isready`, `ucinewgame`.
*   **FR1.2:** Must handle `position [fen | startpos] moves ...` to track the internal game state.
*   **FR1.3:** Must handle the `go` command to initiate screen scanning (waiting for the opponent's move).
*   **FR1.4:** Must output `bestmove [move]` when a move is detected on the screen.

### FR2: Board Calibration
*   **FR2.1:** Upon startup or via a specific custom command, the user must be able to define the board coordinates on the screen.
*   **FR2.2:** Support for clicking "Top-Left" and "Bottom-Right" corners to define the grid.
*   **FR2.3:** Calculate the center coordinates of all 64 squares based on the defined area.

### FR3: Move Execution (GUI $\to$ Screen)
*   **FR3.1:** When the GUI sends a `position ... moves ...` update that includes a new move by the *player* (the human using the physical board), the system must translate that algebraic move (e.g., `e2e4`) into screen coordinates.
*   **FR3.2:** Perform a simulated mouse click sequence: Click Source Square $\rightarrow$ Click Destination Square.

### FR4: Move Detection (Screen $\to$ GUI)
*   **FR4.1:** When the GUI sends the `go` command, the system enters a "Scanning Loop."
*   **FR4.2:** Capture screenshots of the defined board area at a set interval (e.g., 0.5s).
*   **FR4.3:** Compare the current state to the expected internal state to detect differences (piece movements).
*   **FR4.4:** Identify the algebraic move (e.g., `e7e5`) made on the screen and output it as `bestmove e7e5`.

---

## 4. Technical Requirements (TR)

### TR1: Tech Stack
*   **Language:** Python 3.10+
*   **Libraries:**
    *   `python-chess`: For internal board state tracking and move validation.
    *   `opencv-python` (cv2): For image processing and board detection.
    *   `pyautogui` or `mouse`: For simulating input.
    *   `mss` or `d3dshot`: For ultra-fast screen capturing.
    *   `numpy`: For pixel array manipulation.

### TR2: Internal Logic (The "Fake Engine" Loop)
The application must maintain an internal `chess.Board()` object.
1.  **Receive `position`:** Update internal `chess.Board` with the moves list.
2.  **Check Turn:**
    *   If it is the **Human's turn** (according to the received position): Compare the last move in the position list to the last known move. If it's new, execute the Mouse Click.
    *   If it is the **Computer's turn**: Start the CV loop. Wait until the pixels on the screen change to match a valid legal move for the current position.

### TR3: Computer Vision Strategy
*   **Reference:** Utilize the logic from `karayaman/Play-online-chess-with-real-chess-board`.
*   **Detection Method:**
    *   Do not use complex Neural Networks (YOLO) if possible, to keep it lightweight.
    *   **Difference Method:** Take a baseline snapshot. When `go` is received, look for changes in squares.
    *   **Logic:** If "Source Square" pixels change (piece leaves) AND "Dest Square" pixels change (piece arrives), validate against `legal_moves` from the `python-chess` library.

### TR4: Anti-Cheat & Safety
*   **TR4.1:** Mouse movements should have a slight random delay (humanization) to prevent the web browser from flagging the input as a bot.
*   **TR4.2:** The software functions as a relay, not a calculator. It must **not** contain any chess evaluation logic (Stockfish).

---

## 5. Reference Code Snippets

Use these snippets as the foundation for the prompt.

### A. The UCI Loop Structure
```python
import sys
import chess

class UCIScreenBridge:
    def __init__(self):
        self.board = chess.Board()
        self.engine_name = "ScreenBridge 1.0"
        
    def listen(self):
        while True:
            try:
                command = input().strip()
                if not command: continue
            except EOFError:
                break
                
            if command == "uci":
                print(f"id name {self.engine_name}")
                print("id author User")
                print("uciok")
                sys.stdout.flush()
                
            elif command == "isready":
                print("readyok")
                sys.stdout.flush()
                
            elif command.startswith("position"):
                self._handle_position(command)
                
            elif command.startswith("go"):
                self._handle_go(command)
                
            elif command == "quit":
                break

    def _handle_position(self, command):
        # Logic to parse "position startpos moves e2e4..."
        # Update self.board
        # Detect if the last move needs to be clicked on screen
        pass

    def _handle_go(self, command):
        # Start CV loop to watch for opponent move
        # detected_move = self.scanner.wait_for_move(self.board)
        # print(f"bestmove {detected_move}")
        # sys.stdout.flush()
        pass

if __name__ == "__main__":
    app = UCIScreenBridge()
    app.listen()
```

### B. Screen Calibration & Coordinate Logic
```python
import pyautogui

class ScreenMapper:
    def __init__(self):
        self.top_left = (0, 0)
        self.bottom_right = (0, 0)
        self.square_size = 0
        
    def calibrate(self):
        # Implementation to capture mouse clicks for corners
        pass
        
    def get_square_center(self, square_idx):
        # Convert 0-63 index to (x, y) coordinates
        # File (col) = square_idx % 8
        # Rank (row) = square_idx // 8
        # Calculate pixels based on square_size
        return (x, y)
```

## 6. Implementation Steps for the AI

1.  **Setup Environment:** Create a `requirements.txt` with `python-chess`, `opencv-python`, `pyautogui`, `mss`.
2.  **Develop Scanner:** Create a standalone script `scanner.py` that can successfully detect a board on a screenshot and identify pieces.
3.  **Develop UCI Wrapper:** Create `main.py` that implements the UCI loop class above.
4.  **Integration:** Connect the Scanner to the `_handle_go` method and the Mouse Clicker to the `_handle_position` method.
5.  **Testing:** Test with a GUI (like Arena or BearChess) using a localized browser window as the "opponent."