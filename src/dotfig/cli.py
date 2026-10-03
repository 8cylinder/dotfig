"""Command-line interface for managing a dotfig tree."""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.table import Table

from . import core
from .config import Config, DotfigError, config_path
from .diffview import show_diff

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


def _color_common(path: str, common: str) -> str:
    """Escape PATH, rendering its trailing COMMON part in cyan.

    Returns:
        Rich markup for PATH with the shared suffix highlighted.

    """
    if not common or not path.endswith(common):
        return escape(path)
    prefix = path[: len(path) - len(common)]
    return f"{escape(prefix)}[cyan]{escape(common)}[/cyan]"


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
        common = str(entry.stored.relative_to(cfg.root))
        table.add_row(
            _color_common(core.display_path(home, entry.stored), common),
            _color_common(core.display_path(home, entry.source), common),
            f"[{color}]{escape(entry.status)}[/]",
        )
    console.print(table)


@cli.command()
@click.argument("file", type=click.Path(path_type=Path))
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite a differing stored copy with FILE.",
)
@_handle_errors
def store(file: Path, *, force: bool) -> None:
    """Store FILE under the dotfig root and link it back."""
    cfg = Config.load()
    if force and not core.inside_root(cfg, file):
        stored = core.stored_path(cfg, file)
        if _store_conflicts(stored, file):
            _confirm_overwrite(target=file, current=stored)
    console.print(core.store(cfg, file, force=force))


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
    "--side-by-side",
    "side_by_side",
    is_flag=True,
    help="Show the diff as two columns: destination and stored.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite a differing destination with the stored copy.",
)
@_handle_errors
def restore(
    file: Path,
    *,
    dry_run: bool,
    show_diff: bool,
    side_by_side: bool,
    force: bool,
) -> None:
    """Restore FILE from the dotfig root."""
    cfg = Config.load()
    if show_diff or side_by_side:
        _show_diff(cfg, file, side_by_side=side_by_side)
    if force and not dry_run:
        stored, dest = core.restore_paths(cfg, file)
        if stored.is_file() and core.restore_conflict(stored, dest):
            _confirm_overwrite(
                target=stored, current=dest, side_by_side=side_by_side
            )
    console.print(core.restore(cfg, file, dry_run=dry_run, force=force))


def _store_conflicts(stored: Path, file: Path) -> bool:
    return (
        stored.is_file()
        and file.is_file()
        and not core.contents_equal(stored, file)
    )


def _show_diff(cfg: Config, file: Path, *, side_by_side: bool) -> None:
    stored, dest = core.restore_paths(cfg, file)
    if stored.is_file() and core.restore_conflict(stored, dest):
        _print_diff(stored, dest, side_by_side=side_by_side)


def _can_use_tui() -> bool:
    return all((sys.stdin.isatty(), sys.stdout.isatty()))


def _print_diff(target: Path, current: Path, *, side_by_side: bool) -> None:
    if not (target.is_file() and current.is_file()):
        console.print(f"cannot diff {current}; it is not a readable file")
        return
    if _can_use_tui():
        show_diff(current, target, split=side_by_side)
    elif side_by_side:
        _print_side_by_side(target, current)
    else:
        console.print(
            Syntax(core.diff(target, current), "diff", theme="ansi_dark")
        )


def _print_side_by_side(target: Path, current: Path) -> None:
    table = Table(
        "destination",
        "stored",
        show_header=True,
        box=box.MINIMAL,
        pad_edge=False,
    )
    for column in table.columns:
        column.no_wrap = True
        column.overflow = "ellipsis"
    for row in core.side_by_side(target, current):
        left = escape(row.dest) if row.dest is not None else ""
        right = escape(row.stored) if row.stored is not None else ""
        if row.changed:
            if row.dest is not None:
                left = f"[red]{left}[/red]"
            if row.stored is not None:
                right = f"[green]{right}[/green]"
        table.add_row(left, right)
    console.print(table)


def _confirm_overwrite(
    *, target: Path, current: Path, side_by_side: bool = False
) -> None:
    while True:
        answer = str(
            click.prompt(
                f"This will overwrite {current} with {target}. Continue?",
                prompt_suffix=" [y/N/(d)iff]: ",
                default="n",
                show_default=False,
                show_choices=False,
                type=click.Choice(["y", "n", "d"], case_sensitive=False),
            )
        ).lower()
        if answer == "d":
            _print_diff(target, current, side_by_side=side_by_side)
            continue
        if answer == "y":
            return
        raise click.Abort


def main() -> None:
    """Run the dotfig command-line interface."""
    cli()


__all__ = ["cli", "main"]
