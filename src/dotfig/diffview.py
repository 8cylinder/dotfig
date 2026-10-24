"""Show file differences with gdiff, falling back to plain diff."""

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


def show_diff(original: Path, modified: Path) -> None:
    """Display ORIGINAL and MODIFIED in gdiff, or plain diff without gdiff.

    Raises:
        DotfigError: If neither gdiff nor diff is available, or the tool fails.

    """
    original = _diff_path(original)
    modified = _diff_path(modified)

    gdiff = shutil.which("gdiff")
    if gdiff is not None:
        completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [gdiff, str(original), str(modified)],
            check=False,
        )
        if completed.returncode != 0:
            raise DotfigError(
                f"gdiff exited with status {completed.returncode}"
            )
        return

    diff = shutil.which("diff")
    if diff is None:
        raise DotfigError(
            "gdiff is not installed and no diff command was found on PATH"
        )
    completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [diff, "-u", str(original), str(modified)],
        check=False,
    )
    if completed.returncode > 1:
        raise DotfigError(f"diff exited with status {completed.returncode}")
