"""Every module Sage ships, looked up by id.

Modules are registered explicitly (``@register``) rather than discovered by
scanning packages, so the compiled executable sees them through ordinary
imports. Snapshots store only a module id; this is how revert finds the code.
"""

from __future__ import annotations

from core.modules.base import SageModule

MODULES: dict[str, type[SageModule]] = {}


def register[T: type[SageModule]](cls: T) -> T:
    if cls.id in MODULES:
        raise ValueError(f"Duplicate module id: {cls.id!r}")
    MODULES[cls.id] = cls
    return cls


def create(module_id: str) -> SageModule:
    """Instantiate a module with its real (Windows) backends. KeyError if unknown."""
    return MODULES[module_id]()
