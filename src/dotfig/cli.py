"""Command-line interface for managing a dotfig tree."""

from __future__ import annotations

import functools
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, cast

import click
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import core
from .completions import completions_callback
from .config import Config, DotfigError, config_path
from .diffview import show_diff

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

COLORS = ("auto", "always", "never")


def _help_settings(
    context_settings: Mapping[str, object] | None,
) -> dict[str, object]:
    settings = dict(context_settings or {})
    settings.setdefault("help_option_names", ["-h", "--help"])
    return settings


class AppCommand(click.Command):
    """A command with the app's shared help options."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # ruff: ignore[any-type]
        """Build the command with ``-h`` and ``--help`` enabled."""
        raw = kwargs.pop("context_settings", None)
        super().__init__(
            *args,
            context_settings=_help_settings(
                cast("Mapping[str, object] | None", raw)
            ),
            **kwargs,
        )


class AppGroup(click.Group):
    """A command group with the app's shared help options."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # ruff: ignore[any-type]
        """Build the group with ``-h`` and ``--help`` enabled."""
        raw = kwargs.pop("context_settings", None)
        super().__init__(
            *args,
            context_settings=_help_settings(
                cast("Mapping[str, object] | None", raw)
            ),
            **kwargs,
        )


@dataclass(frozen=True)
class Output:
    """The consoles and color decision for one invocation."""

    console: Console
    err_console: Console
    color: str

    def human(self) -> bool:
        """Whether stdout should be formatted for a person.

        Returns:
            Whether stdout is a terminal, color is forced on, or
            FORCE_COLOR selects human output in auto mode.

        """
        if self.color == "always":
            return True
        if self.color == "never":
            return _stdout_is_tty()
        if os.environ.get("FORCE_COLOR"):
            return True
        return _stdout_is_tty()


def _stdout_is_tty() -> bool:
    return bool(sys.stdout.isatty())


def _make_console(mode: str, *, stderr: bool = False) -> Console:
    if mode == "always":
        return Console(stderr=stderr, force_terminal=True, no_color=False)
    if mode == "never":
        return Console(stderr=stderr, force_terminal=False, no_color=True)
    if os.environ.get("FORCE_COLOR"):
        return Console(stderr=stderr, force_terminal=True, no_color=False)
    if os.environ.get("TERM") == "dumb":
        return Console(stderr=stderr, force_terminal=False, no_color=True)
    if os.environ.get("NO_COLOR"):
        return Console(stderr=stderr, no_color=True)
    return Console(stderr=stderr)


def _click_color(mode: str) -> bool | None:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return None


def _output() -> Output:
    ctx = click.get_current_context(silent=True)
    if ctx is not None and isinstance(ctx.obj, Output):
        return ctx.obj
    return Output(
        console=_make_console("auto"),
        err_console=_make_console("auto", stderr=True),
        color="auto",
    )


def _error(message: str) -> NoReturn:
    _output().err_console.print(
        f"[red]error:[/red] {escape(message)}", soft_wrap=True
    )
    raise click.exceptions.Exit(1)


def _diff_paths(cfg: Config, entry: core.Entry) -> tuple[Path, Path]:
    store, host = core.restore_paths(cfg, entry.store)
    if not store.is_file():
        raise DotfigError(f"no stored copy at {store}; nothing to diff")
    if not host.exists():
        raise DotfigError(f"{host} does not exist; nothing to diff")
    if not host.is_file():
        raise DotfigError(f"{host} is not a file; nothing to diff")
    return store, host


def _print_result(message: str) -> None:
    output = _output()
    if "\n" in message:
        output.console.print(escape(message), soft_wrap=True)
        return
    output.console.print(f"[green]ok[/green] {escape(message)}")


def _handle_errors[**P](func: Callable[P, None]) -> Callable[P, None]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            func(*args, **kwargs)
        except DotfigError as exc:
            _error(str(exc))

    return wrapper


def _set_color(
    ctx: click.Context,
    _param: click.Parameter | None,
    value: str,
) -> str:
    """Apply the color choice to Click's own output.

    Returns:
        The unchanged option value for Click's parameter handling.

    """
    if not ctx.resilient_parsing:
        ctx.color = _click_color(value)
    return value


def _print_config(
    ctx: click.Context,
    _param: click.Parameter | None,
    value: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
) -> None:
    """Print the config file path and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(config_path())
    ctx.exit()


@click.group(
    cls=AppGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    epilog=(
        "\b\nExamples:\n\n"
        "\b\n"
        "  dotfig init ~/dotfiles\n"
        "  dotfig store ~/.bashrc\n"
        "  dotfig list\n"
        "  dotfig restore a"
    ),
)
@click.version_option(package_name="dotfig", prog_name="dotfig")
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
    callback=completions_callback,
    help="Write bash completions and exit.",
)
@click.option(
    "--color",
    type=click.Choice(COLORS, case_sensitive=False),
    default="auto",
    show_default=True,
    is_eager=True,
    callback=_set_color,
    help="Control colored output.",
)
@click.pass_context
def cli(ctx: click.Context, color: str) -> None:
    """Manage individual config files with a git-friendly dotfig tree."""
    ctx.color = _click_color(color)
    ctx.obj = Output(
        console=_make_console(color),
        err_console=_make_console(color, stderr=True),
        color=color,
    )
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_command)


@cli.command(cls=AppCommand)
@click.argument("path", type=click.Path(path_type=Path))
@click.option(
    "--force", is_flag=True, help="Overwrite an existing dotfig config."
)
@_handle_errors
def init(path: Path, *, force: bool) -> None:
    """Create PATH as the dotfig root and write the config file."""
    cfg_path = config_path()
    _ensure_new_config(cfg_path, force=force)
    root = core.absolute(path)
    root.mkdir(parents=True, exist_ok=True)
    Config(root=root).save()
    output = _output()
    output.console.print(
        f"[green]ok[/green] initialized dotfig root at {escape(str(root))}"
    )
    output.console.print(f"[green]ok[/green] wrote {escape(str(cfg_path))}")


def _ensure_new_config(cfg_path: Path, *, force: bool) -> None:
    if cfg_path.exists() and not force:
        raise DotfigError(
            f"{cfg_path} already exists; use --force to overwrite it"
        )


def _color_common(path: str, common: str, color: str = "cyan") -> str:
    """Escape PATH, rendering its trailing COMMON part in COLOR.

    Returns:
        Rich markup for PATH with the shared suffix highlighted.

    """
    if not common or not path.endswith(common):
        return escape(path)
    prefix = path[: len(path) - len(common)]
    return f"{escape(prefix)}[{color}]{escape(common)}[/{color}]"


@cli.command(name="list", cls=AppCommand)
@_handle_errors
def list_command() -> None:
    """List stored config files with IDs and a match status."""
    output = _output()
    cfg = Config.load()
    entries = core.list_managed(cfg)
    if not entries:
        if output.human():
            output.console.print("no stored config files")
        return
    home = Path.home()
    if not output.human():
        for index, entry in enumerate(entries):
            symbol = "✓" if entry.matches else "✗"
            click.echo(
                "\t".join(
                    (
                        core.entry_id(index),
                        core.display_path(home, entry.store),
                        core.display_path(home, entry.host),
                        symbol,
                    )
                )
            )
        return
    table = Table(
        "ID",
        "Store",
        "Host",
        "Status",
        box=box.SIMPLE_HEAD,
        show_edge=False,
        pad_edge=False,
    )
    for index, entry in enumerate(entries):
        symbol = "✓" if entry.matches else "✗"
        color = "green" if entry.matches else "red"
        path_color = "cyan" if entry.matches else "yellow"
        common = str(entry.store.relative_to(cfg.root))
        table.add_row(
            core.entry_id(index),
            _color_common(
                core.display_path(home, entry.store), common, path_color
            ),
            _color_common(
                core.display_path(home, entry.host), common, path_color
            ),
            f"[{color}]{symbol}[/]",
        )
    output.console.print(table)


@cli.command(cls=AppCommand)
@click.argument("entry_id", metavar="ID")
@_handle_errors
def diff(entry_id: str) -> None:
    """Show differences between the entry with ID and its host path.

    ID is the identifier shown by 'dotfig list'.
    """
    cfg = Config.load()
    entry = core.find_entry(core.list_managed(cfg), entry_id)
    store, host = _diff_paths(cfg, entry)
    if core.contents_equal(store, host):
        _output().console.print(
            f"{escape(str(host))} matches the stored copy", soft_wrap=True
        )
        return
    _print_diff(cfg, store, host)


@cli.command(cls=AppCommand)
@click.argument("file", metavar="FILE|ID", type=click.Path(path_type=Path))
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite a differing stored copy with FILE.",
)
@_handle_errors
def store(file: Path, *, force: bool) -> None:
    """Store FILE under the dotfig root and link it back.

    FILE may also be the ID of a file that is already stored.
    """
    cfg = Config.load()
    file = _resolve_store_target(cfg, file)
    if force and not core.inside_root(cfg, file):
        stored = core.store_path(cfg, file)
        if _store_conflicts(stored, file):
            _confirm_overwrite(cfg, target=file, current=stored)
    _print_result(core.store(cfg, file, force=force))


def _resolve_store_target(cfg: Config, file: Path) -> Path:
    """Resolve FILE to a host path, accepting a list ID.

    Returns:
        FILE unchanged when it names an existing path, the host path of the
        entry whose list ID is FILE when one matches, or FILE otherwise.

    """
    if file.exists() or file.is_symlink() or not cfg.root.is_dir():
        return file
    try:
        return core.find_entry(core.list_managed(cfg), str(file)).host
    except DotfigError:
        return file


@cli.command(cls=AppCommand)
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
    help="Show a diff when the host path differs from the stored copy.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite a differing host path or symlink with the stored copy.",
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
        _show_diff(cfg, entry.store)
    if force and not dry_run:
        stored, host = core.restore_paths(cfg, entry.store)
        if stored.is_file() and core.restore_conflict(stored, host):
            _confirm_overwrite(cfg, target=stored, current=host)
    _print_result(core.restore(cfg, entry.store, dry_run=dry_run, force=force))


@cli.command(name="break", cls=AppCommand, hidden=True)
@click.argument("entry_id", metavar="ID")
@_handle_errors
def break_command(entry_id: str) -> None:
    """Replace a managed host symlink with a copy of the stored file."""
    cfg = Config.load()
    entry = core.find_entry(core.list_managed(cfg), entry_id)
    _print_result(core.break_link(cfg, entry.store))


def _store_conflicts(store: Path, file: Path) -> bool:
    return (
        not file.is_symlink()
        and store.is_file()
        and file.is_file()
        and not core.contents_equal(store, file)
    )


def _show_diff(cfg: Config, file: Path) -> None:
    store, host = core.restore_paths(cfg, file)
    if (
        store.is_file()
        and host.is_file()
        and not core.contents_equal(store, host)
    ):
        _print_diff(cfg, store, host)


def _can_use_tui() -> bool:
    return all((sys.stdin.isatty(), sys.stdout.isatty()))


def _print_diff(cfg: Config, target: Path, current: Path) -> None:
    """Show the difference between CURRENT and TARGET.

    Raises:
        DotfigError: If stdout/stdin are not an interactive terminal, or the
            diff tool fails.

    """
    if not _can_use_tui():
        raise DotfigError("showing a diff requires an interactive terminal")
    show_diff(current, target, tool=cfg.diff_tool)


def _confirm_overwrite(cfg: Config, *, target: Path, current: Path) -> None:
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
            _print_diff(cfg, target, current)
            continue
        if answer == "y":
            return
        raise click.Abort


def main() -> None:
    """Run the dotfig command-line interface."""
    cli()


__all__ = ["cli", "main"]
