"""Persistent snapshots taken before a module changes anything.

Each module has at most one *active* snapshot: the state of the machine before
Sage first applied it. Applying the same module again must not recapture, or
the snapshot would hold Sage's own values and revert would restore nothing.
After a successful revert the active snapshot is moved to the archive, kept for
auditing.

Layout under the data dir (``%ProgramData%\\Sage`` by default, or ``SAGE_DATA_DIR``)::

    snapshots/active/<module_id>.json
    snapshots/archive/<module_id>-<timestamp>.json

Snapshot data is stored as plain JSON: pydantic models such as ``RegValue`` are
dumped to dicts, so ``revert`` receives dicts and re-validates what it needs.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pydantic_core import to_jsonable_python

from core.modules.base import Snapshot

SCHEMA_VERSION = 1
_MODULE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def default_data_dir() -> Path:
    if override := os.environ.get("SAGE_DATA_DIR"):
        return Path(override)
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Sage"


class SnapshotError(Exception):
    pass


class SnapshotExistsError(SnapshotError):
    pass


class SnapshotRecord(BaseModel):
    schema_version: int = SCHEMA_VERSION
    module_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any]


class SnapshotStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        root = (data_dir or default_data_dir()) / "snapshots"
        self.active_dir = root / "active"
        self.archive_dir = root / "archive"

    def _active_path(self, module_id: str) -> Path:
        if not _MODULE_ID.match(module_id):
            raise SnapshotError(f"Invalid module id: {module_id!r}")
        return self.active_dir / f"{module_id}.json"

    def active(self, module_id: str) -> SnapshotRecord | None:
        path = self._active_path(module_id)
        if not path.exists():
            return None
        return self._load(path)

    def save(self, module_id: str, data: Snapshot, overwrite: bool = False) -> SnapshotRecord:
        path = self._active_path(module_id)
        if path.exists() and not overwrite:
            raise SnapshotExistsError(
                f"Module {module_id!r} already has an active snapshot; "
                "revert it first or pass overwrite=True"
            )
        record = SnapshotRecord(module_id=module_id, data=to_jsonable_python(data))
        self._write_atomic(path, record.model_dump_json(indent=2))
        return record

    def archive(self, module_id: str) -> Path | None:
        """Move the active snapshot to the archive. Returns the new path, or None if none."""
        path = self._active_path(module_id)
        if not path.exists():
            return None
        record = self._load(path)
        stamp = record.created_at.strftime("%Y%m%dT%H%M%S%fZ")
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        target = self.archive_dir / f"{module_id}-{stamp}.json"
        os.replace(path, target)
        return target

    def list_active(self) -> list[SnapshotRecord]:
        if not self.active_dir.exists():
            return []
        return [self._load(path) for path in sorted(self.active_dir.glob("*.json"))]

    @staticmethod
    def _load(path: Path) -> SnapshotRecord:
        try:
            return SnapshotRecord.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise SnapshotError(f"Corrupted or unreadable snapshot: {path}") from exc

    @staticmethod
    def _write_atomic(path: Path, content: str) -> None:
        # Write next to the target and swap in, so a crash never leaves a half-written
        # snapshot where the original state used to be.
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
