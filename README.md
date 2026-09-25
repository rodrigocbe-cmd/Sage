# Sage

Windows optimization toolkit. Every tweak is an isolated module that knows how to
apply, revert and report its own status, and every change is snapshotted before it
is made so it can be undone.

## Setup

Requires Python 3.12+ on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Then, once per machine, from an elevated (Administrator) terminal:

```powershell
sage install
```

This creates `%ProgramData%\Sage` (snapshots and operation log) and restricts it to
Administrators and SYSTEM. Snapshots are what `revert` writes back into the registry
as admin, so a standard user must not be able to edit them. Commands that change the
system refuse to run until this is done; `--dry-run` works without it.

## Usage

```powershell
sage --help
# or, if the sage.exe launcher is blocked by endpoint security:
python -m cli --help
```

Commands that change the system must run from an elevated (Administrator) terminal.

## Building the installer

```powershell
winget install JRSoftware.InnoSetup   # once
python builder.py                     # or --skip-installer for just the app
```

`builder.py` deletes the previous `build/` and `dist/`, compiles `dist/sage/sage.exe`
with PyInstaller, smoke-tests it and compiles `dist/installer/sage-setup-<version>.exe`
from `installer/sage.iss`.

The setup wizard installs to `Program Files\Sage`, optionally adds it to `PATH` and runs
`sage install`. Uninstalling (Settings > Apps) offers to revert every applied tweak
first, then removes the app folder, `%ProgramData%\Sage` (snapshots and logs), the
`PATH` entry and the uninstall entry. Nothing Sage created is left behind.

## Tests

```powershell
pytest -m "not integration"   # pure unit tests, touch nothing
pytest                        # also real registry (throwaway HKCU keys) and ACL checks
```

Run the full suite from an elevated terminal to include the data-directory lockdown test.

## Layout

- `core/` — engine: modules, executor, rollback, Windows platform bindings
- `cli/` — command-line interface
- `scripts/` — PowerShell scripts called by the core (auditable, versioned)
- `installer/` — Inno Setup script for the setup wizard and uninstaller
- `builder.py` — clean build of the app and the installer
- `tests/` — unit and integration tests
