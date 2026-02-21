"""UCI engine shim — bridges a Chess GUI to a web chess board via screen CV.

Entry point: UCIEngine.run() reads stdin and dispatches UCI commands.
"""
import sys
import time

from uci_screen_bridge.screen import calibration

ENGINE_NAME = "UCI Screen Bridge"
ENGINE_AUTHOR = "uci-screen-bridge contributors"

UCI_OPTIONS = """\
option name Side type combo default Auto var Auto var White var Black
option name CalibrationMethod type combo default Auto var Auto var Template
option name ScanInterval type spin default 500 min 100 max 2000
option name DragDrop type check default false
option name MoveTimeout type spin default 60 min 10 max 300
option name Recalibrate type button
option name TTSAlerts type check default true
option name PromotionStyle type combo default Auto var Auto var ChessCom var Lichess"""

# Number of outer retry attempts and inner polls in _run_guided_calibration.
_CALIBRATION_OUTER_ATTEMPTS = 3
_CALIBRATION_INNER_POLLS = 10   # 10 × 2s = 20s per attempt → 3 × 20s = 60s total


class UCIEngine:
    """Minimal UCI engine with guided board calibration."""

    def __init__(self, speech_thread=None):
        self._speech_thread = speech_thread

        # Options (defaults match UCI_OPTIONS above)
        self._side = "auto"               # "auto" | "white" | "black"
        self._calibration_method = "auto"  # "auto" | "template"
        self._scan_interval_ms = 500
        self._drag_drop = False
        self._move_timeout_s = 60
        self._tts_alerts = True
        self._promotion_style = "auto"

        # State
        self._recalibrate = False
        self._position = None
        self._we_play_white = None

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _emit(self, msg):
        print(msg, flush=True)

    def _tts(self, text):
        if self._tts_alerts and self._speech_thread is not None:
            self._speech_thread.put_text(text)

    # ------------------------------------------------------------------
    # UCI command handlers
    # ------------------------------------------------------------------

    def _handle_uci(self):
        self._emit(f"id name {ENGINE_NAME}")
        self._emit(f"id author {ENGINE_AUTHOR}")
        self._emit(UCI_OPTIONS)
        self._emit("uciok")

    def _handle_isready(self):
        if self._recalibrate or not calibration.is_fresh():
            position, we_play_white = self._run_guided_calibration()
            self._recalibrate = False
        else:
            position, we_play_white = calibration.load()
        self._position = position
        self._we_play_white = we_play_white
        self._emit("readyok")

    def _handle_setoption(self, command):
        """Parse: setoption name <Name> value <value>"""
        parts = command.split()
        try:
            name_idx = parts.index("name") + 1
        except ValueError:
            return
        name = parts[name_idx] if name_idx < len(parts) else ""

        value = None
        if "value" in parts:
            value_idx = parts.index("value") + 1
            value = " ".join(parts[value_idx:])

        lname = name.lower()
        if lname == "side":
            self._side = (value or "auto").lower()
        elif lname == "calibrationmethod":
            self._calibration_method = (value or "auto").lower()
        elif lname == "scaninterval":
            self._scan_interval_ms = int(value) if value else 500
        elif lname == "dragdrop":
            self._drag_drop = (value or "").lower() == "true"
        elif lname == "movetimeout":
            self._move_timeout_s = int(value) if value else 60
        elif lname == "recalibrate":
            self._recalibrate = True
        elif lname == "ttsalerts":
            self._tts_alerts = (value or "true").lower() == "true"
        elif lname == "promotionstyle":
            self._promotion_style = (value or "auto").lower()

    def _handle_ucinewgame(self):
        pass  # Board reset will be handled by position parsing (Phase 1)

    def _handle_quit(self):
        sys.exit(0)

    # ------------------------------------------------------------------
    # Guided calibration flow (FR2.6)
    # ------------------------------------------------------------------

    def _run_guided_calibration(self):
        """Poll for the web chess board with user-facing prompts.

        Emits info strings to the Chess GUI's engine panel.
        Returns (position, we_play_white) on success, or (None, None) on timeout.
        """
        self._emit("info string CALIBRATING: Please minimize your chess client.")
        self._emit(
            "info string CALIBRATING: Make sure only the web chess board is visible, then wait..."
        )
        self._tts("Please minimize your chess client and show the web chess board")

        position, we_play_white = None, None

        for attempt in range(_CALIBRATION_OUTER_ATTEMPTS):
            for _ in range(_CALIBRATION_INNER_POLLS):
                try:
                    position, we_play_white = calibration.detect_and_save(
                        method=self._calibration_method
                    )
                    break  # success
                except calibration.BoardNotFoundError:
                    time.sleep(2)

            if position is not None:
                break

            if attempt < _CALIBRATION_OUTER_ATTEMPTS - 1:
                self._emit(
                    f"info string CALIBRATING: Board not found, "
                    f"retrying ({attempt + 1}/{_CALIBRATION_OUTER_ATTEMPTS})..."
                )

        if position is None:
            self._emit(
                "info string ERROR: Chess board not found on screen. "
                "Please navigate to the chess board and use Recalibrate."
            )
            self._tts("Chess board not found")
            return None, None

        self._emit(
            "info string CALIBRATING: Chess board detected. "
            "You can reopen your chess client now."
        )
        self._tts("Board detected, you may reopen your chess client")
        return position, we_play_white

    # ------------------------------------------------------------------
    # Main UCI loop
    # ------------------------------------------------------------------

    def run(self):
        """Read UCI commands from stdin and dispatch them."""
        for line in sys.stdin:
            command = line.strip()
            if not command:
                continue

            if command == "uci":
                self._handle_uci()
            elif command == "isready":
                self._handle_isready()
            elif command == "ucinewgame":
                self._handle_ucinewgame()
            elif command.startswith("setoption"):
                self._handle_setoption(command)
            elif command == "quit":
                self._handle_quit()
            # Unknown commands are silently ignored (UCI spec)
