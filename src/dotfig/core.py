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


def inside_root(cfg: Config, file: Path) -> bool:
    """Check whether FILE is the dotfig root or lies inside it.

    Returns:
        Whether FILE is inside the dotfig root.

    """
    target = absolute(file)
    return target == cfg.root or cfg.root in target.parents


def _ensure_source(
    cfg: Config, file: Path, *, home: Path | None = None
) -> None:
    if not inside_root(cfg, file):
        return
    base = _home(home)
    if file == cfg.root:
        raise DotfigError(
            f"{file} is the dotfig root dir; store the config file under "
            f"{base} instead"
        )
    mirror = base / file.relative_to(cfg.root)
    raise DotfigError(
        f"{file} is inside the dotfig root {cfg.root}; did you mean to store "
        f"the config file at {mirror}?"
    )


def resolve_stored(cfg: Config, file: Path) -> Path:
    """Resolve a restore argument to a path inside the dotfig root.

    FILE is treated as relative to the dotfig root unless it is already an
    absolute path, in which case it must itself be inside the root.

    Returns:
        The absolute path of the stored file.

    Raises:
        DotfigError: If FILE resolves to a path outside the dotfig root.

    """
    expanded = Path(os.path.expandvars(str(file))).expanduser()
    candidate = expanded if expanded.is_absolute() else cfg.root / expanded
    stored = absolute(candidate)
    if stored != cfg.root and cfg.root not in stored.parents:
        raise DotfigError(f"{file} is not inside the dotfig root {cfg.root}")
    return stored


def restore_paths(
    cfg: Config, file: Path, *, home: Path | None = None
) -> tuple[Path, Path]:
    """Resolve FILE to its stored copy and its destination under $HOME.

    Returns:
        A ``(stored, dest)`` pair.

    """
    stored = resolve_stored(cfg, file)
    dest = _home(home) / stored.relative_to(cfg.root)
    return stored, dest


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


def restore_conflict(stored: Path, dest: Path) -> bool:
    """Check whether restoring over DEST would replace a conflicting file.

    A conflict is a regular file whose contents differ from STORED, or a
    symlink that does not point at STORED.

    Returns:
        Whether DEST conflicts with STORED.

    """
    if dest.is_symlink():
        return _link_target(dest) != stored
    if dest.is_file():
        return not contents_equal(dest, stored)
    return False


def _link(stored: Path, source: Path) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    source.symlink_to(stored)


def store(
    cfg: Config, file: Path, *, home: Path | None = None, force: bool = False
) -> str:
    """Store a file by moving it into the root and linking it back.

    Returns:
        A message describing what was done.

    Raises:
        DotfigError: If the file cannot be stored safely.

    """
    file = absolute(file)
    _ensure_source(cfg, file, home=home)
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
        if not force:
            raise DotfigError(
                f"{stored} exists with different contents; "
                "refusing to overwrite it"
            )
        backup = stored.with_name(f"{stored.name}.BAK")
        stored.rename(backup)
        shutil.move(str(file), stored)
        _link(stored, file)
        return f"backed up {backup} and stored {file}"

    stored.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file), stored)
    _link(stored, file)
    return f"stored {file}"


def _dry_run_report(stored: Path, dest: Path, *, force: bool = False) -> str:
    """Describe what restore would do, without changing anything.

    Returns:
        A report of the destination state and the planned action.

    """
    exists = dest.is_symlink() or dest.exists()
    if dest.is_symlink():
        target = _link_target(dest)
        if target == stored:
            same = "yes"
            action = f"no (already linked to {stored})"
        elif force:
            same = "no"
            backup = dest.with_name(f"{dest.name}.BAK")
            action = f"yes (back up to {backup}, then link to {stored})"
        else:
            same = "no"
            action = f"no (points to {target}, not the dotfig root)"
    elif dest.is_dir():
        same = "no"
        action = "no (destination is a directory)"
    elif dest.is_file():
        if contents_equal(dest, stored):
            same = "yes"
            backup = dest.with_name(f"{dest.name}.BAK")
            action = f"yes (back up to {backup}, then link to {stored})"
        else:
            same = "no"
            if force:
                backup = dest.with_name(f"{dest.name}.BAK")
                action = f"yes (back up to {backup}, then link to {stored})"
            else:
                action = "no (contents differ from stored)"
    else:
        same = "n/a"
        action = f"yes (link to {stored})"
    return "\n".join(
        [
            f"destination: {dest}",
            f"exists: {'yes' if exists else 'no'}",
            f"same: {same}",
            f"would symlink: {action}",
        ]
    )


def restore(
    cfg: Config,
    file: Path,
    *,
    home: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    """Restore a stored file by linking it back into $HOME.

    FILE names a file inside the dotfig root, relative to the root or as an
    absolute path under it. The mirrored path under $HOME is recreated.

    Returns:
        A message describing what was done, or a report of what would be done
        when DRY_RUN is set.

    Raises:
        DotfigError: If the stored copy is missing or the destination conflicts.

    """
    stored, dest = restore_paths(cfg, file, home=home)

    if not stored.is_file():
        raise DotfigError(f"no stored copy at {stored}; nothing to restore")

    if dry_run:
        return _dry_run_report(stored, dest, force=force)

    if dest.is_symlink():
        target = _link_target(dest)
        if target != stored:
            if not force:
                raise DotfigError(
                    f"{dest} is a symlink to {target}, not to the dotfig root"
                )
            backup = dest.with_name(f"{dest.name}.BAK")
            dest.rename(backup)
            _link(stored, dest)
            return f"backed up {backup} and restored {dest}"
        return f"{dest} is already restored"

    if dest.exists():
        if not dest.is_file():
            raise DotfigError(f"{dest} is a directory; refusing to replace it")
        if not contents_equal(dest, stored) and not force:
            raise DotfigError(
                f"{dest} differs from {stored}; refusing to overwrite it"
            )
        backup = dest.with_name(f"{dest.name}.BAK")
        dest.rename(backup)
        _link(stored, dest)
        return f"backed up {backup} and restored {dest}"

    _link(stored, dest)
    return f"restored {dest}"


def _source_status(source: Path, stored: Path) -> str:
    if source.is_symlink():
        target = _link_target(source)
        if target == stored:
            return "linked"
        return f"wrong link -> {target}"
    if source.exists():
        return "not linked"
    return "missing"


def display_path(home: Path, path: Path) -> str:
    """Render a path relative to the home directory.

    Returns:
        PATH as ``~/...`` when it is under HOME, otherwise its absolute path.

    """
    try:
        relative = path.relative_to(home)
    except ValueError:
        return str(path)
    if relative == Path():
        return "~"
    return str(Path("~") / relative)


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
