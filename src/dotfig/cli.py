"""Command-line interface for managing a dotfig tree."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from . import core
from .config import Config, DotfigError, config_path

if TYPE_CHECKING:
    from collections.abc import Callable

console = Console()

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _handle_errors[**P](func: Callable[P, None]) -> Callable[P, None]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            func(*args, **kwargs)
        except DotfigError as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapper


@click.group(context_settings=CONTEXT_SETTINGS)
def cli() -> None:
    """Manage individual config files with a git-friendly dotfig tree."""


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
@click.option(
    "--force", is_flag=True, help="Overwrite an existing dotfig config."
)
@_handle_errors
def init(path: Path, *, force: bool) -> None:
    """Create PATH as the dotfig root and write the config file.

    Raises:
        ClickException: If the config exists and --force was not given.

    """
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
    home = Path.home()
    table = Table("source", "destination", "status")
    for entry in entries:
        if entry.status == "linked":
            color = "green"
        elif entry.status.startswith("wrong link"):
            color = "red"
        else:
            color = "yellow"
        table.add_row(
            escape(core.display_path(home, entry.stored)),
            escape(core.display_path(home, entry.source)),
            f"[{color}]{escape(entry.status)}[/]",
        )
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
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help="Show what would happen without changing anything.",
)
@click.option(
    "--diff",
    "show_diff",
    is_flag=True,
    help="Show a diff when the destination differs from the stored copy.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite a differing destination with the stored copy.",
)
@_handle_errors
def restore(file: Path, *, dry_run: bool, show_diff: bool, force: bool) -> None:
    """Restore FILE from the dotfig root."""
    cfg = Config.load()
    if show_diff:
        _show_diff(cfg, file)
    if force and not dry_run:
        _confirm_overwrite(cfg, file)
    console.print(core.restore(cfg, file, dry_run=dry_run, force=force))


def _differs(stored: Path, dest: Path) -> bool:
    return (
        stored.is_file()
        and dest.is_file()
        and not dest.is_symlink()
        and not core.contents_equal(dest, stored)
    )


def _show_diff(cfg: Config, file: Path) -> None:
    stored, dest = core.restore_paths(cfg, file)
    if _differs(stored, dest):
        console.print(
            Syntax(core.diff(stored, dest), "diff", theme="ansi_dark")
        )


def _confirm_overwrite(cfg: Config, file: Path) -> None:
    stored, dest = core.restore_paths(cfg, file)
    if not _differs(stored, dest):
        return
    while True:
        answer = str(
            click.prompt(
                f"This will overwrite {dest} with {stored}. Continue?",
                prompt_suffix=" [y/N/(d)iff]: ",
                default="n",
                show_default=False,
                show_choices=False,
                type=click.Choice(["y", "n", "d"], case_sensitive=False),
            )
        ).lower()
        if answer == "d":
            console.print(
                Syntax(core.diff(stored, dest), "diff", theme="ansi_dark")
            )
            continue
        if answer == "y":
            return
        raise click.Abort


def main() -> None:
    """Run the dotfig command-line interface."""
    cli()


__all__ = ["cli", "main"]
