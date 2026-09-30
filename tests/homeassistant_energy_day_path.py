from __future__ import annotations

import sys
from pathlib import Path


def add_app_path() -> None:
    root = Path(__file__).resolve().parents[1] / "homeassistant-energy-day"
    sys.path.insert(0, str(root))
