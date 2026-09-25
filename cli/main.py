import typer

from core import __version__
from core.engine import catalog, installer
from core.engine.executor import Executor
from core.engine.rollback import SnapshotError
from core.platform.security import SecurityError

# No shell completion: installing it writes into the user's PowerShell profile,
# which would outlive an uninstall.
app = typer.Typer(
    help="Sage - Windows optimization toolkit.", no_args_is_help=True, add_completion=False
)


def fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=True)
    return typer.Exit(1)


@app.callback()
def main() -> None:
    """Sage - Windows optimization toolkit."""


@app.command("version")
def show_version() -> None:
    """Show the installed Sage version."""
    typer.echo(f"sage {__version__}")


@app.command("install")
def install() -> None:
    """Create Sage's data directory, restricted to Administrators and SYSTEM (requires admin)."""
    try:
        data_dir = installer.install()
    except (installer.NotElevatedError, SecurityError) as exc:
        raise fail(str(exc)) from exc
    typer.secho(f"Sage installed. Data directory: {data_dir}", fg=typer.colors.GREEN)


@app.command("revert-all")
def revert_all() -> None:
    """Revert every tweak Sage applied on this machine (requires admin). Used by the uninstaller."""
    executor = Executor()
    try:
        results = executor.revert_all(catalog.create)
    except (installer.NotElevatedError, installer.NotInstalledError, SnapshotError) as exc:
        raise fail(str(exc)) from exc

    if not results:
        typer.echo("Nothing to revert.")
        return
    for result in results:
        mark = "OK  " if result.success else "FAIL"
        typer.echo(f"[{mark}] {result.module_id} {result.message}".rstrip())
    if not all(result.success for result in results):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
