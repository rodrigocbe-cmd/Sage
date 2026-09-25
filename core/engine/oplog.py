"""Append-only log of every operation that changed (or tried to change) the system.

One JSON object per line in ``<data dir>/logs/operations.jsonl``, so it can be
tailed, grepped or loaded by the GUI later.
"""

from __future__ import annotations

import getpass
import json
from pathlib import Path

from core.engine.paths import default_data_dir
from core.modules.base import ModuleResult


class OperationLog:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.path = (data_dir or default_data_dir()) / "logs" / "operations.jsonl"

    def record(self, result: ModuleResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = result.model_dump(mode="json")
        entry["user"] = getpass.getuser()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
