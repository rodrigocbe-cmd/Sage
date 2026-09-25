"""One-time machine setup: create and lock down the data directory.

``sage install`` must run elevated. Every command that changes the system checks
the installation first and refuses to run on an unprotected data directory.
"""

from __future__ import annotations

from pathlib import Path

from core.engine.paths import default_data_dir
from core.platform import security


class NotElevatedError(Exception):
    pass


class NotInstalledError(Exception):
    pass


def require_admin() -> None:
    if not security.is_admin():
        raise NotElevatedError(
            "This command must be run from an elevated (Administrator) terminal."
        )


def install(data_dir: Path | None = None) -> Path:
    """Create the data directory restricted to Administrators and SYSTEM. Idempotent."""
    require_admin()
    data_dir = data_dir or default_data_dir()
    security.secure_directory(data_dir)
    check = security.check_directory(data_dir)
    if not check.secure:
        raise security.SecurityError(
            f"{data_dir} is still not secure after install: {'; '.join(check.problems)}"
        )
    return data_dir


def require_installed(data_dir: Path | None = None) -> None:
    data_dir = data_dir or default_data_dir()
    check = security.check_directory(data_dir)
    if not check.secure:
        raise NotInstalledError(
            f"Sage data directory is not installed or not protected ({'; '.join(check.problems)}). "
            "Run 'sage install' from an elevated terminal."
        )
