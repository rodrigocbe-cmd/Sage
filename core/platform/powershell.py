"""Run Windows PowerShell 5.1 scripts from Python.

Always uses the absolute path to powershell.exe (never a PATH lookup), since Sage
runs elevated and must not pick up a planted binary. Scripts are passed with
-EncodedCommand, so quoting and newlines survive intact.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

POWERSHELL = (
    Path(os.environ.get("SystemRoot", r"C:\Windows"))
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)

_PRELUDE = (
    "$ErrorActionPreference = 'Stop'\n"
    "$ProgressPreference = 'SilentlyContinue'\n"
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8\n"
)


class PowerShellError(Exception):
    pass


def quote(value: str | os.PathLike[str]) -> str:
    """Quote a value as a PowerShell single-quoted string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def run(script: str, timeout: float = 60) -> str:
    """Run a script and return its stdout. Raises PowerShellError on a non-zero exit."""
    encoded = base64.b64encode((_PRELUDE + script).encode("utf-16-le")).decode("ascii")
    try:
        completed = subprocess.run(
            [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PowerShellError(f"Could not run PowerShell: {exc}") from exc
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PowerShellError(stderr or stdout or f"exit code {completed.returncode}")
    return stdout


def run_json(script: str, timeout: float = 60) -> Any:
    """Run a script whose output is JSON (end it with ``| ConvertTo-Json``) and parse it."""
    output = run(script, timeout)
    try:
        return json.loads(output) if output else None
    except json.JSONDecodeError as exc:
        raise PowerShellError(f"Expected JSON from PowerShell, got: {output[:200]!r}") from exc
