from importlib.metadata import version

import typer

from core.engine import installer
from core.platform.security import SecurityError

app = typer.Typer(help="Sage - Windows optimization toolkit.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Sage - Windows optimization toolkit."""


@app.command("version")
def show_version() -> None:
    """Show the installed Sage version."""
    typer.echo(f"sage {version('sage')}")


@app.command("install")
def install() -> None:
    """Create Sage's data directory, restricted to Administrators and SYSTEM (requires admin)."""
    try:
        data_dir = installer.install()
    except (installer.NotElevatedError, SecurityError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    typer.secho(f"Sage installed. Data directory: {data_dir}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
