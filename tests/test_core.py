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


def test_store_force_overwrites_stored(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc", "local")
    stored = make_file(cfg.root / ".bashrc", "stored")
    message = core.store(cfg, file, force=True)
    assert file.is_symlink()
    assert stored.read_text() == "local"
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
    with pytest.raises(DotfigError, match="inside the dotfig root") as excinfo:
        core.store(cfg, file, home=home)
    assert str(home / "nested" / "file") in str(excinfo.value)


def test_store_root_dir_raises(cfg: Config, home: Path) -> None:
    with pytest.raises(DotfigError, match="root dir") as excinfo:
        core.store(cfg, cfg.root, home=home)
    assert str(home) in str(excinfo.value)


def test_resolve_stored_relative_to_root(cfg: Config) -> None:
    assert core.resolve_stored(cfg, Path(".config") / "app" / "conf") == (
        cfg.root / ".config" / "app" / "conf"
    )


def test_resolve_stored_absolute_inside_root(cfg: Config) -> None:
    stored = cfg.root / ".bashrc"
    assert core.resolve_stored(cfg, stored) == stored


def test_resolve_stored_outside_root_raises(cfg: Config) -> None:
    with pytest.raises(DotfigError, match="inside the dotfig root"):
        core.resolve_stored(cfg, Path("..") / "escape")


def test_restore_missing_source_creates_link(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config" / "app" / "conf", "data")
    core.restore(cfg, Path(".config") / "app" / "conf")
    file = home / ".config" / "app" / "conf"
    assert file.is_symlink()
    assert file.read_text() == "data"


def test_restore_regular_file_same_is_backed_up(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".bashrc", "same")
    file = make_file(home / ".bashrc", "same")
    core.restore(cfg, Path(".bashrc"))
    assert file.is_symlink()
    assert file.read_text() == "same"
    backup = home / ".bashrc.BAK"
    assert backup.read_text() == "same"
    assert not backup.is_symlink()


def test_restore_different_contents_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    file = make_file(home / ".bashrc", "local")
    with pytest.raises(DotfigError, match="differs"):
        core.restore(cfg, Path(".bashrc"))
    assert file.read_text() == "local"
    assert not file.is_symlink()


def test_restore_already_linked_is_noop(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    assert core.restore(cfg, Path(".bashrc")) == f"{file} is already restored"


def test_restore_without_stored_copy_raises(cfg: Config) -> None:
    with pytest.raises(DotfigError, match="nothing to restore"):
        core.restore(cfg, Path(".bashrc"))


def test_restore_foreign_symlink_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    target = make_file(home / "elsewhere")
    file = home / ".bashrc"
    file.symlink_to(target)
    with pytest.raises(DotfigError, match="symlink"):
        core.restore(cfg, Path(".bashrc"))


def test_restore_directory_destination_raises(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config", "stored")
    (home / ".config").mkdir()
    with pytest.raises(DotfigError, match="directory"):
        core.restore(cfg, Path(".config"))


def test_restore_dry_run_missing_destination(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".config" / "app" / "conf", "data")
    report = core.restore(cfg, Path(".config") / "app" / "conf", dry_run=True)
    assert "exists: no" in report
    assert "same: n/a" in report
    assert "would symlink: yes" in report
    assert not (home / ".config").exists()


def test_restore_dry_run_same_contents(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "same")
    file = make_file(home / ".bashrc", "same")
    report = core.restore(cfg, Path(".bashrc"), dry_run=True)
    assert "exists: yes" in report
    assert "same: yes" in report
    assert "would symlink: yes" in report
    assert "back up" in report
    assert file.read_text() == "same"
    assert not file.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_restore_dry_run_different_contents(cfg: Config, home: Path) -> None:
    make_file(cfg.root / ".bashrc", "stored")
    file = make_file(home / ".bashrc", "local")
    report = core.restore(cfg, Path(".bashrc"), dry_run=True)
    assert "exists: yes" in report
    assert "same: no" in report
    assert "would symlink: no" in report
    assert file.read_text() == "local"
    assert not file.is_symlink()


def test_restore_dry_run_already_linked(cfg: Config, home: Path) -> None:
    file = make_file(home / ".bashrc")
    core.store(cfg, file)
    report = core.restore(cfg, Path(".bashrc"), dry_run=True)
    assert "exists: yes" in report
    assert "same: yes" in report
    assert "would symlink: no" in report
    assert "already linked" in report


def test_diff_shows_changes(tmp_path: Path) -> None:
    stored = make_file(tmp_path / "stored", "new\n")
    dest = make_file(tmp_path / "dest", "old\n")
    result = core.diff(stored, dest)
    assert "-old" in result
    assert "+new" in result


def test_diff_identical_files_is_empty(tmp_path: Path) -> None:
    stored = make_file(tmp_path / "stored", "same\n")
    dest = make_file(tmp_path / "dest", "same\n")
    assert not core.diff(stored, dest)


def test_side_by_side_aligns_replaced_lines(tmp_path: Path) -> None:
    stored = make_file(tmp_path / "stored", "a\nnew\nc\n")
    dest = make_file(tmp_path / "dest", "a\nold\nc\n")
    rows = core.side_by_side(stored, dest)
    assert [(row.dest, row.stored, row.changed) for row in rows] == [
        ("a", "a", False),
        ("old", "new", True),
        ("c", "c", False),
    ]


def test_side_by_side_marks_deleted_lines(tmp_path: Path) -> None:
    stored = make_file(tmp_path / "stored", "a\nc\n")
    dest = make_file(tmp_path / "dest", "a\nb\nc\n")
    rows = core.side_by_side(stored, dest)
    assert [(row.dest, row.stored, row.changed) for row in rows] == [
        ("a", "a", False),
        ("b", None, True),
        ("c", "c", False),
    ]


def test_side_by_side_marks_inserted_lines(tmp_path: Path) -> None:
    stored = make_file(tmp_path / "stored", "a\nb\nc\n")
    dest = make_file(tmp_path / "dest", "a\nc\n")
    rows = core.side_by_side(stored, dest)
    assert [(row.dest, row.stored, row.changed) for row in rows] == [
        ("a", "a", False),
        (None, "b", True),
        ("c", "c", False),
    ]


def test_restore_force_overwrites_different_contents(
    cfg: Config, home: Path
) -> None:
    make_file(cfg.root / ".bashrc", "stored\n")
    file = make_file(home / ".bashrc", "local\n")
    message = core.restore(cfg, Path(".bashrc"), force=True)
    assert file.is_symlink()
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
    assert "would symlink: yes" in report
    assert "back up" in report
    assert file.read_text() == "local\n"
    assert not file.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


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


def test_display_path_uses_home_tilde(cfg: Config, home: Path) -> None:
    stored = cfg.root / ".config" / "app" / "conf"
    assert core.display_path(home, stored) == (
        f"~/{cfg.root.name}/.config/app/conf"
    )
    source = home / ".config" / "app" / "conf"
    assert core.display_path(home, source) == "~/.config/app/conf"
    assert core.display_path(home, home / "elsewhere") == "~/elsewhere"


def test_display_path_outside_home_is_absolute(tmp_path: Path) -> None:
    home = tmp_path / "home"
    outside = tmp_path / "other" / "file"
    assert core.display_path(home, outside) == str(outside)


def test_list_managed_missing_root_raises(home: Path) -> None:
    cfg = Config(root=home / "does-not-exist")
    with pytest.raises(DotfigError, match="does not exist"):
        core.list_managed(cfg)
