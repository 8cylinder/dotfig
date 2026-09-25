from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import core
from .config import Config, DotfigError, config_path

console = Console()


def _handle_errors[**P](func: Callable[P, None]) -> Callable[P, None]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            func(*args, **kwargs)
        except DotfigError as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapper


@click.group()
def cli() -> None:
    """Manage individual config files with a git-friendly dotfig tree."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite an existing dotfig config.")
@_handle_errors
def init(path: Path, force: bool) -> None:
    """Create PATH as the dotfig root and write the config file."""
    cfg_path = config_path()
    if cfg_path.exists() and not force:
        raise click.ClickException(
            f"{cfg_path} already exists; use --force to overwrite it"
        )
    root = core.absolute(path)
    root.mkdir(parents=True, exist_ok=True)
    Config(root=root).save()
    console.print(f"initialized dotfig root at {root}")
    console.print(f"wrote {cfg_path}")


@cli.command(name="list")
@_handle_errors
def list_command() -> None:
    """List stored config files and whether each source is linked."""
    cfg = Config.load()
    entries = core.list_managed(cfg)
    if not entries:
        console.print("no stored config files")
        return
    table = Table("source", "status")
    for entry in entries:
        if entry.status == "linked":
            color = "green"
        elif entry.status.startswith("wrong link"):
            color = "red"
        else:
            color = "yellow"
        table.add_row(escape(str(entry.source)), f"[{color}]{escape(entry.status)}[/]")
    console.print(table)


@cli.command()
@click.argument("file", type=click.Path(path_type=Path))
@_handle_errors
def store(file: Path) -> None:
    """Store FILE under the dotfig root and link it back."""
    cfg = Config.load()
    console.print(core.store(cfg, file))


@cli.command()
@click.argument("file", type=click.Path(path_type=Path))
@_handle_errors
def restore(file: Path) -> None:
    """Restore FILE from the dotfig root."""
    cfg = Config.load()
    console.print(core.restore(cfg, file))


__all__ = ["cli"]
