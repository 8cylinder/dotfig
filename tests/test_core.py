from __future__ import annotations

from pathlib import Path

import pytest

from dotfig import core
from dotfig.config import Config, DotfigError


def make_file(path: Path, content: str = "hello") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_store_path_mirrors_home(cfg: Config, home: Path) -> None:
    file = home / ".config" / "app" / "conf"
    assert core.store_path(cfg, file) == cfg.root / ".config" / "app" / "conf"


def test_store_path_outside_home_raises(cfg: Config, tmp_path: Path) -> None:
    outside = tmp_path.parent / "elsewhere" / "file"
    with pytest.raises(DotfigError, match="outside"):
        core.store_path(cfg, outside, home=tmp_path)


def test_store_copies_file(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "export X=1")
    message = core.store(cfg, file)
    store = cfg.root / ".bashrc"
    assert "stored" in message
    assert store.read_text() == "export X=1"
    assert not file.is_symlink()
    assert file.read_text() == "export X=1"


def test_store_creates_parent_dirs(cfg: Config, home: Path) -> None:
    file = make_file(home / ".config" / "app" / "conf", "data")
    core.store(cfg, file)
    assert (cfg.root / ".config" / "app" / "conf").is_file()
    assert not file.is_symlink()
    assert file.read_text() == "data"


def test_store_already_stored_is_noop(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    assert core.store(cfg, file) == f"{file} is already stored"
    assert not file.is_symlink()


def test_store_matching_copy_is_noop(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "same")
    make_file(cfg.root / ".bashrc", "same")
    message = core.store(cfg, file)
    assert "already stored" in message
    assert not file.is_symlink()
    assert file.read_text() == "same"


def test_store_different_contents_raises(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "local")
    make_file(cfg.root / ".bashrc", "stored")
    with pytest.raises(DotfigError, match="different"):
        core.store(cfg, file)
    assert not file.is_symlink()
    assert file.read_text() == "local"


def test_store_force_overwrites_stored(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "local")
    store = make_file(cfg.root / ".bashrc", "stored")
    message = core.store(cfg, file, force=True)
    assert not file.is_symlink()
    assert file.read_text() == "local"
    assert store.read_text() == "local"
    backup = cfg.root / ".bashrc.BAK"
    assert backup.read_text() == "stored"
    assert "backed up" in message


def test_store_missing_file_raises(cfg: Config, home: Path) -> None:
    with pytest.raises(DotfigError, match="does not exist"):
        core.store(cfg, home / ".nope")


def test_store_directory_raises(cfg: Config, home: Path) -> None:
    directory = home / ".config" / "app"
    directory.mkdir(parents=True)
    with pytest.raises(DotfigError, match="directory"):
        core.store(cfg, directory)


def test_store_symlink_raises(cfg: Config, home: Path) -> None:
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="break"):
        core.store(cfg, file)
    assert file.is_symlink()


def test_store_broken_symlink_raises(cfg: Config, home: Path) -> None:
    file = home / ".bashrc"
    file.symlink_to(cfg.root / ".bashrc")
    with pytest.raises(DotfigError, match="break"):
        core.store(cfg, file)
    assert file.is_symlink()


def test_store_file_inside_root_raises(cfg: Config, home: Path) -> None:
    file = make_file(cfg.root / "nested" / "file")
    with pytest.raises(DotfigError, match="inside the dotfig root") as excinfo:
        core.store(cfg, file, home=home)
    assert str(home / "nested" / "file") in str(excinfo.value)


def test_store_root_dir_raises(cfg: Config, home: Path) -> None:
    with pytest.raises(DotfigError, match="root dir") as excinfo:
        core.store(cfg, cfg.root, home=home)
    assert str(home) in str(excinfo.value)


def test_resolve_store_relative_to_root(cfg: Config) -> None:
    assert core.resolve_store(cfg, Path(".config") / "app" / "conf") == (
        cfg.root / ".config" / "app" / "conf"
    )


def test_resolve_store_absolute_inside_root(cfg: Config) -> None:
    store = cfg.root / ".bashrc"
    assert core.resolve_store(cfg, store) == store


def test_resolve_store_outside_root_raises(cfg: Config) -> None:
    with pytest.raises(DotfigError, match="inside the dotfig root"):
        core.resolve_store(cfg, Path("..") / "escape")


def test_restore_missing_host_creates_copy(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config" / "app" / "conf", "data")
    core.restore(cfg, Path(".config") / "app" / "conf")
    file = home / ".config" / "app" / "conf"
    assert not file.is_symlink()
    assert file.read_text() == "data"


def test_restore_regular_file_same_is_noop(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "same")
    file = make_file(home / ".bashrc", "same")
    message = core.restore(cfg, Path(".bashrc"))
    assert "already restored" in message
    assert not file.is_symlink()
    assert file.read_text() == "same"
    assert not (home / ".bashrc.BAK").exists()


def test_restore_different_contents_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    file = make_file(home / ".bashrc", "local")
    with pytest.raises(DotfigError, match="differs"):
        core.restore(cfg, Path(".bashrc"))
    assert file.read_text() == "local"
    assert not file.is_symlink()


def test_restore_already_copied_is_noop(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    assert core.restore(cfg, Path(".bashrc")) == f"{file} is already restored"


def test_restore_without_stored_copy_raises(cfg: Config) -> None:
    with pytest.raises(DotfigError, match="nothing to restore"):
        core.restore(cfg, Path(".bashrc"))


def test_restore_symlink_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="break"):
        core.restore(cfg, Path(".bashrc"))
    assert file.is_symlink()
    assert file.read_text() == "hello"


def test_restore_symlink_force_still_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="break"):
        core.restore(cfg, Path(".bashrc"), force=True)
    assert file.is_symlink()
    assert file.readlink() == target
    assert not (home / ".bashrc.BAK").exists()


def test_restore_conflict_detection(cfg: Config, home: Path) -> None:
    store = make_file(cfg.root / ".bashrc", "stored")
    assert not core.restore_conflict(store, home / ".bashrc")
    make_file(home / ".bashrc", "stored")
    assert not core.restore_conflict(store, home / ".bashrc")
    make_file(home / ".bashrc", "other")
    assert core.restore_conflict(store, home / ".bashrc")
    foreign = make_file(home / "foreign")
    link = home / ".bashrc"
    link.unlink()
    link.symlink_to(foreign)
    assert not core.restore_conflict(store, link)
    link.unlink()
    link.symlink_to(store)
    assert not core.restore_conflict(store, link)


def test_restore_force_dry_run_symlink_still_refused(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    report = core.restore(cfg, Path(".bashrc"), dry_run=True, force=True)
    assert "would copy: no" in report
    assert "symlink" in report
    assert file.is_symlink()
    assert file.readlink() == target


def test_restore_directory_host_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config", "stored")
    (home / ".config").mkdir()
    with pytest.raises(DotfigError, match="directory"):
        core.restore(cfg, Path(".config"))


def test_restore_dry_run_missing_host(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config" / "app" / "conf", "data")
    report = core.restore(cfg, Path(".config") / "app" / "conf", dry_run=True)
    assert "exists: no" in report
    assert "same: n/a" in report
    assert "would copy: yes" in report
    assert not (home / ".config").exists()


def test_restore_dry_run_same_contents(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "same")
    file = make_file(home / ".bashrc", "same")
    report = core.restore(cfg, Path(".bashrc"), dry_run=True)
    assert "exists: yes" in report
    assert "same: yes" in report
    assert "would copy: no (already restored)" in report
    assert "back up" not in report
    assert file.read_text() == "same"
    assert not file.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_restore_dry_run_different_contents(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    file = make_file(home / ".bashrc", "local")
    report = core.restore(cfg, Path(".bashrc"), dry_run=True)
    assert "exists: yes" in report
    assert "same: no" in report
    assert "would copy: no" in report
    assert file.read_text() == "local"
    assert not file.is_symlink()


def test_restore_dry_run_already_copied(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    report = core.restore(cfg, Path(".bashrc"), dry_run=True)
    assert "exists: yes" in report
    assert "same: yes" in report
    assert "would copy: no" in report
    assert "already restored" in report


def test_restore_force_overwrites_different_contents(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".bashrc", "stored\n")
    file = make_file(home / ".bashrc", "local\n")
    message = core.restore(cfg, Path(".bashrc"), force=True)
    assert not file.is_symlink()
    assert file.read_text() == "stored\n"
    backup = home / ".bashrc.BAK"
    assert backup.read_text() == "local\n"
    assert "backed up" in message


def test_restore_force_dry_run_reports_overwrite(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".bashrc", "stored\n")
    file = make_file(home / ".bashrc", "local\n")
    report = core.restore(cfg, Path(".bashrc"), dry_run=True, force=True)
    assert "would copy: yes" in report
    assert "back up" in report
    assert file.read_text() == "local\n"
    assert not file.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_list_managed_skips_git_and_reports_matches(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".git" / "config")
    copied = make_file(home / ".bashrc")
    core.store(cfg, copied)
    make_file(cfg.root / ".gemrc", "stored")
    make_file(home / ".gemrc", "local")
    make_file(cfg.root / ".vimrc")
    entries = core.list_managed(cfg)
    assert [(entry.host.name, entry.matches) for entry in entries] == [
        (".bashrc", True),
        (".gemrc", False),
        (".vimrc", False),
    ]


def test_list_managed_symlink_is_not_a_match(cfg: Config, home: Path) -> None:
    store = make_file(cfg.root / ".bashrc")
    file = home / ".bashrc"
    file.symlink_to(store)
    (entry,) = core.list_managed(cfg)
    assert not entry.matches


def test_list_managed_wrong_link_is_not_a_match(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".bashrc")
    file = home / ".bashrc"
    file.symlink_to(home / "other")
    (entry,) = core.list_managed(cfg)
    assert not entry.matches


def test_break_link_replaces_symlink_with_copy(cfg: Config, home: Path) -> None:
    store = make_file(cfg.root / ".bashrc", "data")
    file = home / ".bashrc"
    file.symlink_to(store)
    message = core.break_link(cfg, Path(".bashrc"))
    assert "broke" in message
    assert not file.is_symlink()
    assert file.read_text() == "data"
    assert store.read_text() == "data"


def test_break_link_requires_symlink(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "data")
    make_file(home / ".bashrc", "data")
    with pytest.raises(DotfigError, match="not a symlink"):
        core.break_link(cfg, Path(".bashrc"))


def test_break_link_foreign_symlink_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "data")
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="not to the dotfig root"):
        core.break_link(cfg, Path(".bashrc"))
    assert file.is_symlink()
    assert file.readlink() == target


def test_break_link_missing_store_raises(cfg: Config, home: Path) -> None:
    file = home / ".bashrc"
    file.symlink_to(cfg.root / ".bashrc")
    with pytest.raises(DotfigError, match="nothing to break"):
        core.break_link(cfg, Path(".bashrc"))
    assert file.is_symlink()


def test_display_path_uses_home_tilde(cfg: Config, home: Path) -> None:
    stored = cfg.root / ".config" / "app" / "conf"
    assert core.display_path(home, stored) == (
        f"~/{cfg.root.name}/.config/app/conf"
    )
    host = home / ".config" / "app" / "conf"
    assert core.display_path(home, host) == "~/.config/app/conf"
    assert core.display_path(home, home / "elsewhere") == "~/elsewhere"


def test_display_path_outside_home_is_absolute(tmp_path: Path) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "other" / "file"
    assert core.display_path(home, outside) == str(outside)


def test_list_managed_missing_root_raises(home: Path) -> None:
    cfg = Config(root=home / "does-not-exist")
    with pytest.raises(DotfigError, match="does not exist"):
        core.list_managed(cfg)


def test_entry_id_sequence() -> None:
    indexes = (0, 1, 25, 26, 27, 51, 52)
    assert [core.entry_id(index) for index in indexes] == [
        "a",
        "b",
        "z",
        "aa",
        "ab",
        "az",
        "ba",
    ]


def test_entry_id_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        core.entry_id(-1)


def test_find_entry_resolves_ids(cfg: Config) -> None:
    make_file(cfg.root / ".bashrc")
    make_file(cfg.root / ".vimrc")
    entries = core.list_managed(cfg)

    assert core.find_entry(entries, "a").host.name == ".bashrc"
    assert core.find_entry(entries, "B").host.name == ".vimrc"


def test_find_entry_unknown_id_raises(cfg: Config) -> None:
    make_file(cfg.root / ".bashrc")
    with pytest.raises(DotfigError, match="unknown entry id"):
        core.find_entry(core.list_managed(cfg), "z")
