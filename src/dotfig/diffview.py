"""Show file differences with a configured tool, falling back to plain diff."""

from __future__ import annotations

import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from typing import TYPE_CHECKING, Literal

from .config import DotfigError

if TYPE_CHECKING:
    from pathlib import Path

SyncDirection = Literal["to_store", "to_host"]

_ASK = {
    "panels": [
        {
            "label": "Host",
            "button_text": "To store -->",
            "return_value": "to_store",
        },
        {
            "label": "Store",
            "button_text": "<-- To host",
            "return_value": "to_host",
        },
    ]
}


def _diff_path(path: Path) -> Path:
    """Follow a symlink so its target contents are diffed, not the link text.

    Returns:
        The resolved path when PATH is a symlink, otherwise PATH unchanged.

    """
    return path.resolve() if path.is_symlink() else path


def show_diff(
    original: Path, modified: Path, *, tool: str | None = None
) -> None:
    """Display ORIGINAL and MODIFIED with TOOL, or plain diff without it.

    Raises:
        DotfigError: If no diff command is available, or the tool fails.

    """
    original = _diff_path(original)
    modified = _diff_path(modified)

    if tool:
        executable = shutil.which(tool)
        if executable is not None:
            completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                [executable, str(original), str(modified)],
                check=False,
            )
            if completed.returncode != 0:
                raise DotfigError(
                    f"{tool} exited with status {completed.returncode}"
                )
            return

    diff = shutil.which("diff")
    if diff is None:
        if tool is None:
            raise DotfigError("no diff command was found on PATH")
        raise DotfigError(
            f"no diff command was found on PATH (configured diff_tool "
            f"{tool!r} is not installed)"
        )
    completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [diff, "-u", str(original), str(modified)],
        check=False,
    )
    if completed.returncode > 1:
        raise DotfigError(f"diff exited with status {completed.returncode}")


def ask_sync_direction(
    original: Path, modified: Path, *, tool: str | None = None
) -> SyncDirection | None:
    """Ask which way to copy between ORIGINAL and MODIFIED.

    ORIGINAL is the host side and MODIFIED is the store side. The selected
    return value is captured from stdout while the diff UI stays on stderr.

    Returns:
        ``"to_store"`` when the host should overwrite the store,
        ``"to_host"`` for the reverse, or ``None`` when the user cancels.

    Raises:
        DotfigError: If the tool is missing, fails, or returns an unknown
            value.

    """
    original = _diff_path(original)
    modified = _diff_path(modified)
    name = tool or "diffuse"
    executable = shutil.which(name)
    if executable is None:
        if tool is None:
            raise DotfigError(
                "diffuse was not found on PATH; install diffuse to use "
                "'dotfig sync'"
            )
        raise DotfigError(
            f"diff tool {tool!r} was not found on PATH; 'dotfig sync' needs "
            "diffuse"
        )
    completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            executable,
            "--ask",
            json.dumps(_ASK),
            str(original),
            str(modified),
        ],
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise DotfigError(f"{name} exited with status {completed.returncode}")
    choice = completed.stdout.rstrip("\n")
    if not choice:
        return None
    if choice == "to_store":
        return "to_store"
    if choice == "to_host":
        return "to_host"
    raise DotfigError(f"unexpected {name} result: {choice!r}")
