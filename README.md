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
- `tests/` — unit and integration tests
