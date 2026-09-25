"""Build Sage from source.

1. Deletes the previous build (``build/`` and ``dist/``), if any.
2. Compiles the app with PyInstaller into ``dist/sage/sage.exe``.
3. Smoke-tests the executable.
4. Compiles the setup wizard with Inno Setup into ``dist/installer/sage-setup-<version>.exe``.

Usage (from the project's virtual environment)::

    python builder.py                  # full build
    python builder.py --skip-installer # only the compiled app, no Inno Setup needed
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "sage"
INSTALLER_DIR = DIST_DIR / "installer"
ENTRY_POINT = ROOT / "cli" / "__main__.py"
ISS_SCRIPT = ROOT / "installer" / "sage.iss"

ISCC_CANDIDATES = [
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6",
]


class BuildError(Exception):
    pass


def step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def get_version() -> str:
    sys.path.insert(0, str(ROOT))
    from core import __version__

    return __version__


def clean() -> None:
    step("Removing previous build")

    def force_remove(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)  # PyInstaller output can contain read-only files
        func(path)

    for directory in (BUILD_DIR, DIST_DIR):
        if directory.parent != ROOT:  # never delete anything outside the project
            raise BuildError(f"Refusing to delete {directory}")
        if directory.exists():
            shutil.rmtree(directory, onexc=force_remove)
            print(f"    deleted {directory.relative_to(ROOT)}")
        else:
            print(f"    {directory.relative_to(ROOT)} not present")


def compile_app() -> None:
    step("Compiling sage.exe with PyInstaller")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ENTRY_POINT),
        "--name", "sage",
        # One folder, not one file: a onefile exe unpacks itself into %TEMP% on
        # every run and can leave that copy behind if it crashes.
        "--onedir",
        "--console",
        "--noconfirm",
        "--clean",
        "--log-level", "WARN",
        "--paths", str(ROOT),
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        # Modules are only reached through the catalog; make sure all are bundled.
        "--collect-submodules", "core.modules",
        "--exclude-module", "tests",
        "--exclude-module", "pytest",
        "--exclude-module", "PyInstaller",
    ]  # fmt: skip
    if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:
        raise BuildError("PyInstaller failed")
    if not (APP_DIR / "sage.exe").exists():
        raise BuildError(f"PyInstaller finished but {APP_DIR / 'sage.exe'} is missing")


def smoke_test(version: str) -> None:
    step("Smoke-testing the executable")
    exe = APP_DIR / "sage.exe"
    try:
        completed = subprocess.run(
            [str(exe), "version"], capture_output=True, text=True, timeout=60, check=False
        )
    except PermissionError:
        # Unsigned executables can be blocked by endpoint security on managed machines.
        print(f"    WARNING: Windows refused to run {exe} (access denied).")
        print("    The build is complete, but it could not be verified on this machine.")
        return
    output = completed.stdout.strip()
    if completed.returncode != 0 or output != f"sage {version}":
        raise BuildError(f"Smoke test failed: exit {completed.returncode}, output {output!r}")
    print(f"    {output}")


def find_iscc() -> Path:
    if found := shutil.which("ISCC"):
        return Path(found)
    for folder in ISCC_CANDIDATES:
        if (folder / "ISCC.exe").exists():
            return folder / "ISCC.exe"
    raise BuildError(
        "Inno Setup 6 (ISCC.exe) not found. Install it with:\n"
        "    winget install JRSoftware.InnoSetup\n"
        "or build only the app with: python builder.py --skip-installer"
    )


def compile_installer(version: str) -> Path:
    step("Compiling the setup wizard with Inno Setup")
    command = [
        str(find_iscc()),
        f"/DAppVersion={version}",
        f"/DSourceDir={APP_DIR}",
        f"/O{INSTALLER_DIR}",
        "/Q",
        str(ISS_SCRIPT),
    ]
    if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:
        raise BuildError("Inno Setup failed")
    setup = INSTALLER_DIR / f"sage-setup-{version}.exe"
    if not setup.exists():
        raise BuildError(f"Inno Setup finished but {setup} is missing")
    return setup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skip-installer", action="store_true", help="build only the app, not the setup wizard"
    )
    args = parser.parse_args()

    if sys.platform != "win32":
        print("Sage can only be built on Windows.", file=sys.stderr)
        return 1

    version = get_version()
    print(f"Building Sage {version}")
    try:
        clean()
        compile_app()
        smoke_test(version)
        setup = None if args.skip_installer else compile_installer(version)
    except BuildError as exc:
        print(f"\nBUILD FAILED: {exc}", file=sys.stderr)
        return 1

    step("Done")
    print(f"    App:       {APP_DIR / 'sage.exe'}")
    if setup:
        print(f"    Installer: {setup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
