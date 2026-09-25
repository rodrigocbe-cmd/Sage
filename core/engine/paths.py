"""Where Sage keeps its machine-wide data (snapshots, operation log)."""

from __future__ import annotations

import os
from pathlib import Path


def default_data_dir() -> Path:
    if override := os.environ.get("SAGE_DATA_DIR"):
        return Path(override)
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Sage"
