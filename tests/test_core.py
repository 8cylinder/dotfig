from __future__ import annotations

from pathlib import Path

import pytest

from dotfig import core
from dotfig.config import Config, DotfigError


def make_file(path: Path, content: str = "hello") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_stored_path_mirrors_home(cfg: Config, home: Path) -> None:
    file = home / ".config" / "app" / "conf"
    assert core.stored_path(cfg, file) == cfg.root / ".config" / "app" / "conf"


def test_stored_path_outside_home_raises(cfg: Config, tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere" / "file"
    with pytest.raises(DotfigError, match="outside"):
        core.stored_path(cfg, outside, home=tmp_path)


def test_store_moves_file_and_links(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "export X=1")
    message = core.store(cfg, file)
    stored = cfg.root / ".bashrc"
    assert "stored" in message
    assert stored.read_text() == "export X=1"
    assert file.is_symlink()
    assert file.resolve() == stored.resolve()


def test_store_creates_parent_dirs(cfg: Config, home: Path) -> None:
    file = make_file(home / ".config" / "app" / "conf", "data")
    core.store(cfg, file)
    assert (cfg.root / ".config" / "app" / "conf").is_file()
    assert file.is_symlink()


def test_store_already_stored_is_noop(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    assert core.store(cfg, file) == f"{file} is already stored"
    assert file.is_symlink()


def test_store_regular_file_matching_stored_becomes_link(
    cfg: Config, home: Path
) -> None:
    file = make_file(home / ".bashrc", "same")
    make_file(cfg.root / ".bashrc", "same")
    message = core.store(cfg, file)
    assert "linked" in message
    assert file.is_symlink()


def test_store_different_contents_raises(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "local")
    make_file(cfg.root / ".bashrc", "stored")
    with pytest.raises(DotfigError, match="different"):
        core.store(cfg, file)
    assert not file.is_symlink()
    assert file.read_text() == "local"


def test_store_missing_file_raises(cfg: Config, home: Path) -> None:
    with pytest.raises(DotfigError, match="does not exist"):
        core.store(cfg, home / ".nope")


def test_store_directory_raises(cfg: Config, home: Path) -> None:
    directory = home / ".config" / "app"
    directory.mkdir(parents=True)
    with pytest.raises(DotfigError, match="directory"):
        core.store(cfg, directory)


def test_store_foreign_symlink_raises(cfg: Config, home: Path) -> None:
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="symlink"):
        core.store(cfg, file)


def test_store_broken_link_raises(cfg: Config, home: Path) -> None:
    file = home / ".bashrc"
    file.symlink_to(cfg.root / ".bashrc")
    with pytest.raises(DotfigError, match="broken"):
        core.store(cfg, file)


def test_store_file_inside_root_raises(cfg: Config, home: Path) -> None:
    file = make_file(cfg.root / "nested" / "file")
    with pytest.raises(DotfigError, match="inside the dotfig root"):
        core.store(cfg, file)


def test_restore_missing_source_creates_link(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config" / "app" / "conf", "data")
    file = home / ".config" / "app" / "conf"
    core.restore(cfg, file)
    assert file.is_symlink()
    assert file.read_text() == "data"


def test_restore_regular_file_same_becomes_link(
    cfg: Config, home: Path
) -> None:
    file = make_file(home / ".bashrc", "same")
    make_file(cfg.root / ".bashrc", "same")
    core.restore(cfg, file)
    assert file.is_symlink()


def test_restore_different_contents_raises(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "local")
    make_file(cfg.root / ".bashrc", "stored")
    with pytest.raises(DotfigError, match="differs"):
        core.restore(cfg, file)
    assert file.read_text() == "local"


def test_restore_already_linked_is_noop(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    assert core.restore(cfg, file) == f"{file} is already restored"


def test_restore_without_stored_copy_raises(cfg: Config, home: Path) -> None:
    with pytest.raises(DotfigError, match="nothing to restore"):
        core.restore(cfg, home / ".bashrc")


def test_restore_foreign_symlink_raises(cfg: Config, home: Path) -> None:
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="symlink"):
        core.restore(cfg, file)


def test_list_managed_skips_git_and_reports_status(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".git" / "config")
    linked = make_file(home / ".bashrc")
    core.store(cfg, linked)
    make_file(cfg.root / ".gemrc")
    make_file(home / ".gemrc")
    make_file(cfg.root / ".vimrc")
    entries = core.list_managed(cfg)
    assert [(entry.source.name, entry.status) for entry in entries] == [
        (".bashrc", "linked"),
        (".gemrc", "not linked"),
        (".vimrc", "missing"),
    ]


def test_list_managed_wrong_link(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc")
    file = home / ".bashrc"
    file.symlink_to(home / "other")
    (entry,) = core.list_managed(cfg)
    assert entry.status.startswith("wrong link")


def test_list_managed_missing_root_raises(home: Path) -> None:
    cfg = Config(root=home / "does-not-exist")
    with pytest.raises(DotfigError, match="does not exist"):
        core.list_managed(cfg)
