"""Store config files in a dotfig tree and copy them back into $HOME."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .config import Config, DotfigError

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class Entry:
    """A stored file and whether the host copy matches it."""

    host: Path
    store: Path
    matches: bool


def entry_id(index: int) -> str:
    """Return the lowercase list ID for a zero-based INDEX.

    Returns:
        The ID as ``a`` through ``z``, then ``aa``, ``ab``, and so on.

    Raises:
        ValueError: If INDEX is negative.

    """
    if index < 0:
        raise ValueError("index must be non-negative")
    chars: list[str] = []
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        chars.append(chr(ord("a") + remainder))
    return "".join(reversed(chars))


def absolute(path: Path) -> Path:
    """Make a path absolute without resolving symlinks.

    Returns:
        The expanded, absolute path.

    """
    expanded = Path(os.path.expandvars(str(path))).expanduser()
    return Path(os.path.abspath(expanded))


def _home(home: Path | None) -> Path:
    return absolute(home) if home is not None else Path.home()


def store_path(cfg: Config, file: Path, *, home: Path | None = None) -> Path:
    """Map a host file under $HOME to its location in the dotfig root.

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


def _ensure_host(cfg: Config, file: Path, *, home: Path | None = None) -> None:
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


def resolve_store(cfg: Config, file: Path) -> Path:
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
    store = absolute(candidate)
    if store != cfg.root and cfg.root not in store.parents:
        raise DotfigError(f"{file} is not inside the dotfig root {cfg.root}")
    return store


def restore_paths(
    cfg: Config, file: Path, *, home: Path | None = None
) -> tuple[Path, Path]:
    """Resolve FILE to its store path and its host path under $HOME.

    Returns:
        A ``(store, host)`` pair.

    """
    store = resolve_store(cfg, file)
    host = _home(home) / store.relative_to(cfg.root)
    return store, host


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


def restore_conflict(store: Path, host: Path) -> bool:
    """Check whether restoring over HOST would replace a differing file.

    Symlinks are not treated as conflicts here because restore refuses them;
    the caller should direct the user to ``dotfig break`` instead.

    Returns:
        Whether HOST is a regular file whose contents differ from STORE.

    """
    if host.is_symlink() or not host.is_file():
        return False
    return not contents_equal(host, store)


def _replace_symlink_with_copy(store: Path, host: Path) -> None:
    with tempfile.NamedTemporaryFile(
        dir=host.parent,
        prefix=f".{host.name}.",
        suffix=".break",
        delete=False,
    ) as handle:
        temp = Path(handle.name)
    try:
        shutil.copy2(store, temp)
        temp.replace(host)
    finally:
        temp.unlink(missing_ok=True)


def store(
    cfg: Config, file: Path, *, home: Path | None = None, force: bool = False
) -> str:
    """Store a file by copying it into the root.

    Returns:
        A message describing what was done.

    Raises:
        DotfigError: If the file cannot be stored safely.

    """
    file = absolute(file)
    _ensure_host(cfg, file, home=home)
    store = store_path(cfg, file, home=home)

    if file.is_symlink():
        raise DotfigError(
            f"{file} is a symlink; run 'dotfig list' and 'dotfig break ID' "
            "to replace it with a copy"
        )
    if not file.exists():
        raise DotfigError(f"{file} does not exist")
    if not file.is_file():
        raise DotfigError(f"{file} is a directory; only files can be stored")

    if store.is_symlink():
        raise DotfigError(f"{store} is a symlink; refusing to overwrite it")
    if store.is_dir():
        raise DotfigError(f"{store} already exists and is a directory")
    if store.exists():
        if contents_equal(file, store):
            return f"{file} is already stored"
        if not force:
            raise DotfigError(
                f"{store} exists with different contents; "
                "refusing to overwrite it"
            )
        backup = store.with_name(f"{store.name}.BAK")
        store.rename(backup)
        shutil.copy2(file, store)
        return f"backed up {backup} and stored {file}"

    store.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, store)
    return f"stored {file}"


def _dry_run_report(store: Path, host: Path, *, force: bool = False) -> str:
    """Describe what restore would do, without changing anything.

    Returns:
        A report of the host state and the planned action.

    """
    exists = host.is_symlink() or host.exists()
    if host.is_symlink():
        target = _link_target(host)
        same = "yes" if target == store else "no"
        action = "no (host is a symlink; run 'dotfig break ID' first)"
    elif host.is_dir():
        same = "no"
        action = "no (host is a directory)"
    elif host.is_file():
        if contents_equal(host, store):
            same = "yes"
            action = "no (already restored)"
        else:
            same = "no"
            if force:
                backup = host.with_name(f"{host.name}.BAK")
                action = f"yes (back up to {backup}, then copy from {store})"
            else:
                action = "no (contents differ from stored)"
    else:
        same = "n/a"
        action = f"yes (copy from {store})"
    return "\n".join(
        [
            f"host: {host}",
            f"exists: {'yes' if exists else 'no'}",
            f"same: {same}",
            f"would copy: {action}",
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
    """Restore a stored file by copying it back into $HOME.

    FILE names a file inside the dotfig root, relative to the root or as an
    absolute path under it. The mirrored path under $HOME is recreated.

    Returns:
        A message describing what was done, or a report of what would be done
        when DRY_RUN is set.

    Raises:
        DotfigError: If the stored copy is missing or the host path conflicts.

    """
    store, host = restore_paths(cfg, file, home=home)

    if not store.is_file():
        raise DotfigError(f"no stored copy at {store}; nothing to restore")

    if dry_run:
        return _dry_run_report(store, host, force=force)

    if host.is_symlink():
        raise DotfigError(
            f"{host} is a symlink; run 'dotfig list' and 'dotfig break ID' "
            "to replace it with a copy"
        )

    if host.exists():
        if not host.is_file():
            raise DotfigError(f"{host} is a directory; refusing to replace it")
        if contents_equal(host, store):
            return f"{host} is already restored"
        if not force:
            raise DotfigError(
                f"{host} differs from {store}; refusing to overwrite it"
            )
        backup = host.with_name(f"{host.name}.BAK")
        host.rename(backup)
        shutil.copy2(store, host)
        return f"backed up {backup} and restored {host}"

    host.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(store, host)
    return f"restored {host}"


def break_link(cfg: Config, file: Path, *, home: Path | None = None) -> str:
    """Replace a managed host symlink with a copy of the stored file.

    Returns:
        A message describing what was done.

    Raises:
        DotfigError: If the stored copy is missing, HOST is not a symlink, or
            the link does not point at the stored copy.

    """
    store, host = restore_paths(cfg, file, home=home)
    if not store.is_file():
        raise DotfigError(f"no stored copy at {store}; nothing to break")
    if not host.is_symlink():
        raise DotfigError(f"{host} is not a symlink; nothing to break")
    target = _link_target(host)
    if target != store:
        raise DotfigError(
            f"{host} is a symlink to {target}, not to the dotfig root"
        )
    _replace_symlink_with_copy(store, host)
    return f"broke link at {host}; copied {store}"


def _matches(host: Path, store: Path) -> bool:
    if host.is_symlink() or not host.is_file():
        return False
    if not store.is_file():
        return False
    return contents_equal(host, store)


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
        One entry per stored file, with whether the host copy matches.

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
            if name.endswith(".BAK"):
                continue
            store = Path(dirpath) / name
            host = base / store.relative_to(cfg.root)
            entries.append(
                Entry(
                    host=host,
                    store=store,
                    matches=_matches(host, store),
                )
            )
    return entries


def find_entry(entries: list[Entry], ref: str) -> Entry:
    """Return the entry whose list ID is REF.

    Returns:
        The matching entry.

    Raises:
        DotfigError: If REF is not a current list ID.

    """
    wanted = ref.strip().lower()
    for index, entry in enumerate(entries):
        if entry_id(index) == wanted:
            return entry
    raise DotfigError(
        f"unknown entry id {ref!r}; run 'dotfig list' to see the ids"
    )
