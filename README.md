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

## Usage

```powershell
sage --help
# or, if the sage.exe launcher is blocked by endpoint security:
python -m cli --help
```

Commands that change the system must run from an elevated (Administrator) terminal.

## Layout

- `core/` — engine: modules, executor, rollback, Windows platform bindings
- `cli/` — command-line interface
- `scripts/` — PowerShell scripts called by the core (auditable, versioned)
- `tests/` — unit and integration tests
