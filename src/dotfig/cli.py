"""Command-line interface for managing a dotfig tree."""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from click.shell_completion import get_completion_class
from rich.console import Console
from rich.markup import escape
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


def _print_config(
    ctx: click.Context,
    _param: click.Parameter,
    value: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
) -> None:
    """Print the config file path and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(config_path())
    ctx.exit()


def _bash_completion_path() -> Path:
    """Return the bash completion script path.

    Returns:
        The path under ``$XDG_DATA_HOME`` or ``~/.local/share``.

    """
    data = Path(
        os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    )
    return data / "bash-completion" / "completions" / "dotfig"


def _bash_version() -> tuple[int, int] | None:
    """Return the installed bash major and minor version.

    Returns:
        The parsed version, or ``None`` when bash cannot be inspected.

    """
    bash = shutil.which("bash")
    if bash is None:
        return None
    try:
        completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [bash, "--norc", "-c", 'printf "%s\\n" "$BASH_VERSION"'],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    match = re.match(r"^(\d+)\.(\d+)", completed.stdout)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _warn_old_bash(version: tuple[int, int]) -> None:
    """Warn that VERSION is too old for Click's bash completion script."""
    click.secho(
        f"warning: bash {version[0]}.{version[1]} is too old for completions; "
        "bash 4.4 or newer is required, so the script may not work. On macOS, "
        "install a newer bash (for example with Homebrew) and use it as your "
        "shell.",
        fg="yellow",
        err=True,
    )


def _bash_completion_script() -> str:
    """Generate a bash completion script without Click's version check.

    Returns:
        The bash completion script for this command.

    Raises:
        DotfigError: If Click has no bash completion support.

    """
    complete_class = get_completion_class("bash")
    if complete_class is None:
        raise DotfigError("bash completion is not available")
    completion = complete_class(cli, {}, "dotfig", "_DOTFIG_COMPLETE")
    return completion.source_template % completion.source_vars()


def _write_completions(
    ctx: click.Context,
    _param: click.Parameter,
    value: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
) -> None:
    """Write the bash completion script and exit."""
    if not value or ctx.resilient_parsing:
        return
    version = _bash_version()
    if version is not None and version < (4, 4):
        _warn_old_bash(version)
    path = _bash_completion_path()
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_bash_completion_script(), encoding="utf-8")
    console.print(f"{'overwrote' if existed else 'created'} {path}")
    console.print("to enable completion in this shell, run:", soft_wrap=True)
    console.print(f"  source {path}", soft_wrap=True)
    ctx.exit()


@click.group(
    context_settings=CONTEXT_SETTINGS,
    invoke_without_command=True,
    no_args_is_help=False,
)
@click.version_option(package_name="dotfig")
@click.option(
    "--config",
    "show_config",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_config,
    help="Print the config file path and exit.",
)
@click.option(
    "--completions",
    "write_completions",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_write_completions,
    help="Write bash completions and exit.",
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Manage individual config files with a git-friendly dotfig tree."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_command)


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
    """List stored config files with IDs and whether each source is linked."""
    cfg = Config.load()
    entries = core.list_managed(cfg)
    if not entries:
        console.print("no stored config files")
        return
    home = Path.home()
    table = Table("id", "source", "destination", "status")
    for index, entry in enumerate(entries):
        if entry.status == "linked":
            color = "green"
        elif entry.status.startswith("wrong link"):
            color = "red"
        else:
            color = "yellow"
        common = str(entry.stored.relative_to(cfg.root))
        table.add_row(
            core.entry_id(index),
            _color_common(core.display_path(home, entry.stored), common),
            _color_common(core.display_path(home, entry.source), common),
            f"[{color}]{escape(entry.status)}[/]",
        )
    console.print(table)


@cli.command()
@click.argument("entry_id", metavar="ID")
@_handle_errors
def diff(entry_id: str) -> None:
    """Show differences between the entry with ID and its destination.

    ID is the identifier shown by 'dotfig list'.

    Raises:
        DotfigError: If the stored copy or destination is missing, the
            destination is not a file, or stdout/stdin are not an interactive
            terminal.

    """
    cfg = Config.load()
    entry = core.find_entry(core.list_managed(cfg), entry_id)
    stored, dest = core.restore_paths(cfg, entry.stored)
    if not stored.is_file():
        raise DotfigError(f"no stored copy at {stored}; nothing to diff")
    if not dest.exists():
        raise DotfigError(f"{dest} does not exist; nothing to diff")
    if not dest.is_file():
        raise DotfigError(f"{dest} is not a file; nothing to diff")
    if core.contents_equal(stored, dest):
        console.print(f"{dest} matches the stored copy", soft_wrap=True)
        return
    _print_diff(stored, dest)


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
@click.argument("entry_id", metavar="ID")
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
def restore(
    entry_id: str,
    *,
    dry_run: bool,
    show_diff: bool,
    force: bool,
) -> None:
    """Restore the entry with ID from the dotfig root.

    ID is the identifier shown by 'dotfig list'.
    """
    cfg = Config.load()
    entry = core.find_entry(core.list_managed(cfg), entry_id)
    if show_diff:
        _show_diff(cfg, entry.stored)
    if force and not dry_run:
        stored, dest = core.restore_paths(cfg, entry.stored)
        if stored.is_file() and core.restore_conflict(stored, dest):
            _confirm_overwrite(target=stored, current=dest)
    console.print(core.restore(cfg, entry.stored, dry_run=dry_run, force=force))


def _store_conflicts(stored: Path, file: Path) -> bool:
    return (
        stored.is_file()
        and file.is_file()
        and not core.contents_equal(stored, file)
    )


def _show_diff(cfg: Config, file: Path) -> None:
    stored, dest = core.restore_paths(cfg, file)
    if stored.is_file() and core.restore_conflict(stored, dest):
        _print_diff(stored, dest)


def _can_use_tui() -> bool:
    return all((sys.stdin.isatty(), sys.stdout.isatty()))


def _print_diff(target: Path, current: Path) -> None:
    """Show the difference between CURRENT and TARGET.

    Raises:
        DotfigError: If stdout/stdin are not an interactive terminal, or the
            diff tool fails.

    """
    if not _can_use_tui():
        raise DotfigError("showing a diff requires an interactive terminal")
    show_diff(current, target)


def _confirm_overwrite(*, target: Path, current: Path) -> None:
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
            _print_diff(target, current)
            continue
        if answer == "y":
            return
        raise click.Abort


def main() -> None:
    """Run the dotfig command-line interface."""
    cli()


__all__ = ["cli", "main"]
