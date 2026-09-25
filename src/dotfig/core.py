"""Store config files in a dotfig tree and symlink them back into $HOME."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import Config, DotfigError

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class Entry:
    """A stored file and the state of its link back into $HOME."""

    source: Path
    stored: Path
    status: str


def absolute(path: Path) -> Path:
    """Make a path absolute without resolving symlinks.

    Returns:
        The expanded, absolute path.

    """
    expanded = Path(os.path.expandvars(str(path))).expanduser()
    return Path(os.path.abspath(expanded))


def _home(home: Path | None) -> Path:
    return absolute(home) if home is not None else Path.home()


def stored_path(cfg: Config, file: Path, *, home: Path | None = None) -> Path:
    """Map a file under $HOME to its location in the dotfig root.

    Returns:
        The path of the file's stored copy.

    Raises:
        DotfigError: If the file is outside $HOME.

    """
    file = absolute(file)
    base = _home(home)
    try:
        relative = file.relative_to(base)
    except ValueError:
        raise DotfigError(
            f"{file} is outside {base}; only files under $HOME are supported"
        ) from None
    return cfg.root / relative


def _link_target(file: Path) -> Path | None:
    if not file.is_symlink():
        return None
    try:
        target_path = file.readlink()
    except OSError:
        return None
    if not target_path.is_absolute():
        target_path = file.parent / target_path
    return absolute(target_path)


def _ensure_source(cfg: Config, file: Path) -> None:
    if file == cfg.root or cfg.root in file.parents:
        raise DotfigError(f"{file} is inside the dotfig root")


def digest(path: Path) -> bytes:
    """Hash a file with SHA-256.

    Returns:
        The raw SHA-256 digest of the file contents.

    """
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.digest()


def contents_equal(first: Path, second: Path) -> bool:
    """Compare two files by size and SHA-256 digest.

    Returns:
        Whether both files have identical contents.

    """
    if first.stat().st_size != second.stat().st_size:
        return False
    return digest(first) == digest(second)


def _link(stored: Path, source: Path) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    source.symlink_to(stored)


def store(cfg: Config, file: Path, *, home: Path | None = None) -> str:
    """Store a file by moving it into the root and linking it back.

    Returns:
        A message describing what was done.

    Raises:
        DotfigError: If the file cannot be stored safely.

    """
    file = absolute(file)
    _ensure_source(cfg, file)
    stored = stored_path(cfg, file, home=home)

    if file.is_symlink():
        target = _link_target(file)
        if target != stored:
            raise DotfigError(
                f"{file} is a symlink to {target}, not to the dotfig root"
            )
        if not stored.exists():
            raise DotfigError(f"{file} is a broken link; {stored} is missing")
        return f"{file} is already stored"

    if not file.exists():
        raise DotfigError(f"{file} does not exist")
    if not file.is_file():
        raise DotfigError(f"{file} is a directory; only files can be stored")

    if stored.exists() or stored.is_symlink():
        if stored.is_dir():
            raise DotfigError(f"{stored} already exists and is a directory")
        if contents_equal(file, stored):
            file.unlink()
            _link(stored, file)
            return f"{file} matches the stored copy; linked it"
        raise DotfigError(
            f"{stored} exists with different contents; refusing to overwrite it"
        )

    stored.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file), stored)
    _link(stored, file)
    return f"stored {file}"


def restore(cfg: Config, file: Path, *, home: Path | None = None) -> str:
    """Restore a file from the dotfig root by linking it back.

    Returns:
        A message describing what was done.

    Raises:
        DotfigError: If the stored copy is missing or the file conflicts.

    """
    file = absolute(file)
    _ensure_source(cfg, file)
    stored = stored_path(cfg, file, home=home)

    if not stored.is_file():
        raise DotfigError(f"no stored copy at {stored}; nothing to restore")

    if file.is_symlink():
        target = _link_target(file)
        if target != stored:
            raise DotfigError(
                f"{file} is a symlink to {target}, not to the dotfig root"
            )
        return f"{file} is already restored"

    if file.exists():
        if not file.is_file():
            raise DotfigError(f"{file} is a directory; refusing to replace it")
        if not contents_equal(file, stored):
            raise DotfigError(
                f"{file} differs from {stored}; refusing to overwrite it"
            )
        file.unlink()

    _link(stored, file)
    return f"restored {file}"


def _source_status(source: Path, stored: Path) -> str:
    if source.is_symlink():
        target = _link_target(source)
        if target == stored:
            return "linked"
        return f"wrong link -> {target}"
    if source.exists():
        return "not linked"
    return "missing"


def list_managed(cfg: Config, *, home: Path | None = None) -> list[Entry]:
    """List every file stored under the dotfig root.

    Returns:
        One entry per stored file, with its link status.

    Raises:
        DotfigError: If the dotfig root does not exist.

    """
    if not cfg.root.is_dir():
        raise DotfigError(
            f"dotfig root {cfg.root} does not exist; run 'dotfig init PATH'"
        )
    base = _home(home)
    entries: list[Entry] = []
    for dirpath, dirnames, filenames in os.walk(cfg.root):
        dirnames[:] = sorted(name for name in dirnames if name != ".git")
        for name in sorted(filenames):
            stored = Path(dirpath) / name
            source = base / stored.relative_to(cfg.root)
            entries.append(
                Entry(
                    source=source,
                    stored=stored,
                    status=_source_status(source, stored),
                )
            )
    return entries
