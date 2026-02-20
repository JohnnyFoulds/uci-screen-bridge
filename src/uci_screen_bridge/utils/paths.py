from pathlib import Path
from importlib.resources import files


def model_path(filename: str) -> str:
    """Absolute path to a file bundled in the models package."""
    return str(files("uci_screen_bridge.models").joinpath(filename))


# __file__ = src/uci_screen_bridge/utils/paths.py
# parents[3] = project root
_DATA_DIR = Path(__file__).parents[3] / "data"


def data_path(filename: str) -> Path:
    """Path to a runtime-generated data file; creates data/ if needed."""
    _DATA_DIR.mkdir(exist_ok=True)
    return _DATA_DIR / filename
