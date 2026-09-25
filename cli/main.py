from importlib.metadata import version

import typer

app = typer.Typer(help="Sage - Windows optimization toolkit.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Sage - Windows optimization toolkit."""


@app.command("version")
def show_version() -> None:
    """Show the installed Sage version."""
    typer.echo(f"sage {version('sage')}")


if __name__ == "__main__":
    app()
