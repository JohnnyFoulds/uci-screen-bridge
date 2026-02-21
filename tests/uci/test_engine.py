"""Tests for UCIEngine guided calibration flow (FR2.6).

All calibration-related tests mock the screen layer so they run headlessly.
"""
from unittest.mock import MagicMock

import pytest

from uci_screen_bridge.screen.calibration import BoardNotFoundError
from uci_screen_bridge.uci.engine import UCIEngine


class _FakePosition:
    """Minimal board-position stand-in."""
    def __init__(self):
        self.minX, self.minY, self.maxX, self.maxY = 100, 100, 900, 900


@pytest.fixture
def fake_position():
    return _FakePosition()


# ---------------------------------------------------------------------------
# Cached calibration — immediate readyok
# ---------------------------------------------------------------------------

def test_isready_with_cached_calibration_is_immediate(mocker, capsys, fake_position):
    """When calibration is fresh, isready emits readyok with no CALIBRATING: lines."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=True)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.load",
                 return_value=(fake_position, True))

    engine = UCIEngine()
    engine._handle_isready()

    out = capsys.readouterr().out
    assert "readyok" in out
    assert "CALIBRATING" not in out


# ---------------------------------------------------------------------------
# No cached calibration — guided flow triggers
# ---------------------------------------------------------------------------

def test_isready_without_cache_emits_calibrating_prompt(mocker, capsys, fake_position):
    """When no fresh calibration exists, isready emits the CALIBRATING: prompt."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=False)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 return_value=(fake_position, True))
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    engine = UCIEngine()
    engine._handle_isready()

    out = capsys.readouterr().out
    assert "CALIBRATING: Please minimize your chess client" in out
    assert "readyok" in out


def test_guided_calibration_emits_success_message(mocker, capsys, fake_position):
    """When detect_and_save succeeds on the first poll, the 'board detected' message appears."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=False)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 return_value=(fake_position, True))
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    engine = UCIEngine()
    engine._handle_isready()

    out = capsys.readouterr().out
    assert "Chess board detected" in out
    assert "readyok" in out


def test_guided_calibration_retries_on_failure_then_succeeds(mocker, capsys, fake_position):
    """detect_and_save failing twice then succeeding still emits 'board detected' and readyok."""
    side_effects = [BoardNotFoundError(), BoardNotFoundError(), (fake_position, True)]
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=False)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 side_effect=side_effects)
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    engine = UCIEngine()
    engine._handle_isready()

    out = capsys.readouterr().out
    assert "Chess board detected" in out
    assert "readyok" in out


def test_guided_calibration_timeout_emits_error(mocker, capsys):
    """When all polls time out, ERROR: is emitted and readyok is still sent."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=False)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 side_effect=BoardNotFoundError())
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    engine = UCIEngine()
    engine._handle_isready()

    out = capsys.readouterr().out
    assert "ERROR:" in out
    assert "readyok" in out
    assert "Chess board detected" not in out


# ---------------------------------------------------------------------------
# Recalibrate option
# ---------------------------------------------------------------------------

def test_recalibrate_reruns_guided_flow(mocker, capsys, fake_position):
    """Setting _recalibrate=True triggers the guided flow even when calibration is fresh."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=True)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 return_value=(fake_position, True))
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    engine = UCIEngine()
    engine._recalibrate = True
    engine._handle_isready()

    out = capsys.readouterr().out
    assert "CALIBRATING: Please minimize" in out
    assert "readyok" in out


def test_recalibrate_flag_cleared_after_isready(mocker, fake_position):
    """After isready with Recalibrate, the flag is reset to False."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=True)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 return_value=(fake_position, True))
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    engine = UCIEngine()
    engine._recalibrate = True
    engine._handle_isready()

    assert engine._recalibrate is False


# ---------------------------------------------------------------------------
# TTS alerts
# ---------------------------------------------------------------------------

def test_tts_called_on_calibration_prompt(mocker, capsys, fake_position):
    """With TTSAlerts=true, speech thread receives the 'minimize' phrase."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=False)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 return_value=(fake_position, True))
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    speech = MagicMock()
    engine = UCIEngine(speech_thread=speech)
    engine._tts_alerts = True
    engine._handle_isready()

    texts_spoken = [call.args[0].lower() for call in speech.put_text.call_args_list]
    assert any("minimize" in t or "chess client" in t for t in texts_spoken)


def test_tts_not_called_when_disabled(mocker, capsys, fake_position):
    """With TTSAlerts=false, no TTS call is made during guided calibration."""
    mocker.patch("uci_screen_bridge.uci.engine.calibration.is_fresh", return_value=False)
    mocker.patch("uci_screen_bridge.uci.engine.calibration.detect_and_save",
                 return_value=(fake_position, True))
    mocker.patch("uci_screen_bridge.uci.engine.time.sleep")

    speech = MagicMock()
    engine = UCIEngine(speech_thread=speech)
    engine._tts_alerts = False
    engine._handle_isready()

    speech.put_text.assert_not_called()
