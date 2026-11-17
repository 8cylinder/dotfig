"""Show file differences with a configured tool, falling back to plain diff."""

from __future__ import annotations

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from typing import TYPE_CHECKING

from .config import DotfigError

if TYPE_CHECKING:
    from pathlib import Path


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
