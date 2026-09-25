"""Elevation checks and locking down Sage's data directory.

The data directory holds the snapshots an elevated ``revert`` writes back into
HKLM. If a standard user could edit them, they could choose what an admin
process writes, so the directory is restricted to Administrators and SYSTEM.
Groups are referenced by SID, because their names are localized
(e.g. "Administradores" on a Portuguese Windows).
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.platform import powershell

ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"
TRUSTED_SIDS = frozenset({ADMINISTRATORS_SID, SYSTEM_SID})

ICACLS = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "icacls.exe"


class SecurityError(Exception):
    pass


def is_admin() -> bool:
    """True if the current process is elevated."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def _icacls(*args: str) -> None:
    completed = subprocess.run([str(ICACLS), *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise SecurityError(f"icacls {' '.join(args)} failed: {detail}")


def secure_directory(path: Path) -> None:
    """Create ``path`` if needed and restrict its whole tree to Administrators and SYSTEM.

    Safe to run on a directory that already exists, even one pre-created by
    another user: ownership is taken back and every explicit permission is wiped.
    """
    path.mkdir(parents=True, exist_ok=True)
    target = str(path)
    admins, system = f"*{ADMINISTRATORS_SID}", f"*{SYSTEM_SID}"
    # Take ownership: an owner can always rewrite the ACL, so it must not be a standard user.
    _icacls(target, "/setowner", admins, "/T", "/C", "/Q")
    # Drop every explicit entry on the tree, leaving only inherited ones...
    _icacls(target, "/reset", "/T", "/C", "/Q")
    # ...then cut inheritance at the root and grant only the trusted groups; children inherit it.
    _icacls(
        target,
        "/inheritance:r",
        "/grant:r",
        f"{admins}:(OI)(CI)F",
        f"{system}:(OI)(CI)F",
        "/Q",
    )


@dataclass
class DirectoryCheck:
    secure: bool
    problems: list[str] = field(default_factory=list)


_ACL_SCRIPT = """
$acl = Get-Acl -LiteralPath {path}
$sidType = [Security.Principal.SecurityIdentifier]
[pscustomobject]@{{
    Owner     = $acl.GetOwner($sidType).Value
    Protected = $acl.AreAccessRulesProtected
    Rules     = @($acl.GetAccessRules($true, $true, $sidType) | ForEach-Object {{
        [pscustomobject]@{{ Sid = $_.IdentityReference.Value; Type = [string]$_.AccessControlType }}
    }})
}} | ConvertTo-Json -Depth 4 -Compress
"""


def check_directory(path: Path) -> DirectoryCheck:
    """Verify ``path`` is owned by, and only grants access to, Administrators and SYSTEM."""
    if not path.is_dir():
        return DirectoryCheck(False, [f"{path} does not exist"])
    try:
        acl = powershell.run_json(_ACL_SCRIPT.format(path=powershell.quote(path)))
    except powershell.PowerShellError as exc:
        return DirectoryCheck(False, [f"could not read permissions of {path}: {exc}"])

    problems = []
    if acl["Owner"] not in TRUSTED_SIDS:
        problems.append(f"owned by {acl['Owner']}")
    if not acl["Protected"]:
        problems.append("inherits permissions from its parent")
    for rule in acl["Rules"]:
        if rule["Type"] == "Allow" and rule["Sid"] not in TRUSTED_SIDS:
            problems.append(f"grants access to {rule['Sid']}")
    return DirectoryCheck(not problems, problems)
