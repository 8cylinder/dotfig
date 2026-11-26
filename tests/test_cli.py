from __future__ import annotations

import importlib
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import CliRunner, Result

from dotfig.cli import _color_common, _print_diff, cli
from dotfig.config import Config, config_path

if TYPE_CHECKING:
    import pytest


EXPECTED_MODE = 0o644


def run(args: list[str], input_text: str | None = None) -> Result:
    return CliRunner().invoke(cli, args, input=input_text, prog_name="dotfig")


def output(result: Result) -> str:
    return result.output


def test_color_common_marks_trailing_shared_path() -> None:
    common = ".config/cm/.env"
    assert _color_common("~/bin/dotfig/.config/cm/.env", common) == (
        "~/bin/dotfig/[cyan].config/cm/.env[/cyan]"
    )
    assert _color_common("~/.config/cm/.env", common) == (
        "~/[cyan].config/cm/.env[/cyan]"
    )


def test_color_common_accepts_another_color() -> None:
    assert _color_common("~/.config/cm/.env", ".config/cm/.env", "yellow") == (
        "~/[yellow].config/cm/.env[/yellow]"
    )


def test_color_common_leaves_other_paths_alone() -> None:
    assert _color_common("~/.bashrc", ".config") == "~/.bashrc"


def test_print_diff_opens_viewer(
    cfg: Config, tmp_path: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    target = tmp_path / "target"
    current = tmp_path / "current"
    target.write_text("new\n")
    current.write_text("old\n")

    _print_diff(cfg, host=current, store=target)

    assert diff_viewer == [(current, target)]


def test_print_diff_passes_configured_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    current = tmp_path / "current"
    target.write_text("new\n")
    current.write_text("old\n")
    calls: list[tuple[Path, Path, str | None]] = []

    def fake_show_diff(
        original: Path, modified: Path, *, tool: str | None = None
    ) -> None:
        calls.append((original, modified, tool))

    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "show_diff", fake_show_diff)
    monkeypatch.setattr(module, "_can_use_tui", lambda: True)
    cfg = Config(root=tmp_path / "root", diff_tool="diffuse")

    _print_diff(cfg, host=current, store=target)

    assert calls == [(current, target, "diffuse")]


def test_init_creates_root_and_config(home: Path) -> None:
    root = home / "tree"
    result = run(["init", str(root)])
    assert result.exit_code == 0, output(result)
    assert root.is_dir()
    assert config_path().is_file()
    assert str(root) in output(result)


def test_init_twice_requires_force(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    second = run(["init", str(root)])
    assert second.exit_code != 0
    assert "--force" in output(second)
    assert run(["init", str(root), "--force"]).exit_code == 0


def test_store_list_restore_flow(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")

    stored = run(["store", str(config)])
    assert stored.exit_code == 0, output(stored)
    assert not config.is_symlink()
    assert config.read_text() == "export X=1"
    assert (root / ".bashrc").read_text() == "export X=1"

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    assert ".bashrc" in output(listed)
    assert "✓" in output(listed)

    config.unlink()
    restored = run(["restore", "a"])
    assert restored.exit_code == 0, output(restored)
    assert not config.is_symlink()
    assert config.read_text() == "export X=1"


def test_store_accepts_id_for_stored_file(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")
    assert run(["store", str(config)]).exit_code == 0

    result = run(["store", "a"])
    assert result.exit_code == 0, output(result)
    assert "already stored" in output(result)
    assert (root / ".bashrc").read_text() == "export X=1"


def test_store_id_force_updates_stored_copy(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("old\n")
    assert run(["store", str(config)]).exit_code == 0
    config.write_text("new\n")

    result = run(["store", "a", "--force"], "y\n")
    assert result.exit_code == 0, output(result)
    assert "This will overwrite" in output(result)
    assert (root / ".bashrc").read_text() == "new\n"
    assert (root / ".bashrc.BAK").read_text() == "old\n"


def test_store_prefers_existing_path_over_id(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("stored\n")
    assert run(["store", str(config)]).exit_code == 0
    monkeypatch.chdir(home)
    named_like_id = home / "a"
    named_like_id.write_text("local\n")

    result = run(["store", "a"])
    assert result.exit_code == 0, output(result)
    assert (root / "a").read_text() == "local\n"
    assert (root / ".bashrc").read_text() == "stored\n"


def test_store_conflict_exits_nonzero(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("local")
    (root / ".bashrc").write_text("stored")
    result = run(["store", str(config)])
    assert result.exit_code != 0
    assert "different" in output(result)
    assert config.read_text() == "local"


def test_store_force_overwrites_stored(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("local\n")
    stored = root / ".bashrc"
    stored.write_text("stored\n")

    result = run(["store", "--force", str(config)], "y\n")
    assert result.exit_code == 0, output(result)
    assert "This will overwrite" in output(result)
    assert "Continue? [y/N/(d)iff]" in output(result)
    assert not config.is_symlink()
    assert config.read_text() == "local\n"
    assert stored.read_text() == "local\n"
    assert (root / ".bashrc.BAK").read_text() == "stored\n"


def test_store_force_prompt_shows_diff_then_aborts(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("local\n")
    stored = root / ".bashrc"
    stored.write_text("stored\n")

    result = run(["store", "--force", str(config)], "d\nn\n")
    assert result.exit_code != 0
    assert output(result).count("Continue? [y/N/(d)iff]") > 1
    assert diff_viewer == [(config, stored)]
    assert config.read_text() == "local\n"
    assert not config.is_symlink()
    assert stored.read_text() == "stored\n"
    assert not (root / ".bashrc.BAK").exists()


def test_store_path_inside_root_suggests_config_file(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".config" / "cm" / ".env"
    config.parent.mkdir(parents=True)
    config.write_text("stored\n")
    assert run(["store", str(config)]).exit_code == 0

    config.unlink()
    config.write_text("local\n")
    stored = root / ".config" / "cm" / ".env"

    result = run(["store", str(stored), "--force"], "y\n")
    assert result.exit_code != 0
    text = output(result)
    assert "inside the dotfig root" in text
    assert str(config) in text
    assert "Continue?" not in text
    assert config.read_text() == "local\n"
    assert stored.read_text() == "stored\n"


def test_store_symlink_refuses_with_break_hint(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    target = home / "elsewhere"
    target.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(target)

    result = run(["store", "--force", str(config)], "y\n")
    assert result.exit_code != 0
    text = output(result)
    assert "symlink" in text
    assert "break" in text
    assert "Continue?" not in text
    assert config.is_symlink()
    assert config.read_text() == "foreign\n"


def test_restore_conflict_exits_nonzero(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored")
    config = home / ".bashrc"
    config.write_text("local")
    result = run(["restore", "a"])
    assert result.exit_code != 0
    assert "differs" in output(result)
    assert config.read_text() == "local"
    assert not config.is_symlink()


def test_restore_dry_run_makes_no_changes(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored")

    result = run(["restore", "--dry-run", "a"])
    assert result.exit_code == 0, output(result)
    assert "would copy: yes" in output(result)
    assert not (home / ".bashrc").exists()

    short = run(["restore", "-d", "a"])
    assert short.exit_code == 0, output(short)
    assert "would copy: yes" in output(short)
    assert not (home / ".bashrc").exists()


def test_restore_diff_opens_viewer(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--diff", "a"])
    assert result.exit_code != 0
    assert config.read_text() == "local\n"
    assert diff_viewer == [(config, stored)]

    no_diff = run(["restore", "a"])
    assert no_diff.exit_code != 0
    assert len(diff_viewer) == 1


def test_diff_shows_store_and_host(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["diff", "a"])
    assert result.exit_code == 0, output(result)
    assert diff_viewer == [(config, stored)]


def test_diff_uses_configured_tool(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")
    with config_path().open("a", encoding="utf-8") as handle:
        handle.write('diff_tool = "diffuse"\n')
    calls: list[tuple[Path, Path, str | None]] = []

    def fake_show_diff(
        original: Path, modified: Path, *, tool: str | None = None
    ) -> None:
        calls.append((original, modified, tool))

    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "show_diff", fake_show_diff)
    monkeypatch.setattr(module, "_can_use_tui", lambda: True)

    result = run(["diff", "a"])
    assert result.exit_code == 0, output(result)
    assert calls == [(config, stored, "diffuse")]


def test_diff_reports_matching_files(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("same\n")
    assert run(["store", str(config)]).exit_code == 0

    result = run(["diff", "a"])
    assert result.exit_code == 0, output(result)
    assert "matches the stored copy" in output(result)
    assert diff_viewer == []


def test_diff_missing_host_fails(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")

    result = run(["diff", "a"])
    assert result.exit_code != 0
    assert "does not exist" in output(result)


def test_diff_rejects_unknown_id(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")

    result = run(["diff", "z"])
    assert result.exit_code != 0
    assert "unknown entry id" in output(result)


def test_diff_requires_terminal(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    (home / ".bashrc").write_text("local\n")
    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "_can_use_tui", lambda: False)

    result = run(["diff", "a"])
    assert result.exit_code != 0
    assert "terminal" in output(result)


def test_restore_diff_requires_terminal(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    (home / ".bashrc").write_text("local\n")
    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "_can_use_tui", lambda: False)

    result = run(["restore", "--diff", "a"])
    assert result.exit_code != 0
    assert "terminal" in output(result)


def test_restore_diff_reports_missing_diff_tools(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    (home / ".bashrc").write_text("local\n")
    module = importlib.import_module("dotfig.cli")
    diffview = importlib.import_module("dotfig.diffview")
    monkeypatch.setattr(module, "_can_use_tui", lambda: True)
    monkeypatch.setattr(diffview.shutil, "which", lambda _: None)

    result = run(["restore", "--diff", "a"])
    assert result.exit_code != 0
    assert "no diff command" in output(result)


def test_restore_dry_run_diff(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--dry-run", "--diff", "a"])
    assert result.exit_code == 0, output(result)
    assert diff_viewer == [(config, stored)]


def test_restore_force_diff_opens_viewer(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "--diff", "a"], "y\n")
    assert result.exit_code == 0, output(result)
    assert diff_viewer == [(config, stored)]
    assert not config.is_symlink()
    assert config.read_text() == "stored\n"


def test_restore_force_symlink_replaces(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    foreign = home / "elsewhere"
    foreign.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(foreign)

    result = run(["restore", "--force", "a"], "y\n")
    assert result.exit_code == 0, output(result)
    assert "This will overwrite" in output(result)
    assert not config.is_symlink()
    assert config.read_text() == "stored\n"
    assert foreign.read_text() == "foreign\n"
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_symlink_diff_then_replaces(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    foreign = home / "elsewhere"
    foreign.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(foreign)

    result = run(["restore", "--force", "--diff", "a"], "y\n")
    assert result.exit_code == 0, output(result)
    assert diff_viewer == [(config, stored)]
    assert not config.is_symlink()
    assert config.read_text() == "stored\n"
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_symlink_prompt_aborts(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    foreign = home / "elsewhere"
    foreign.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(foreign)

    result = run(["restore", "--force", "a"], "n\n")
    assert result.exit_code != 0
    assert "Continue?" in output(result)
    assert config.is_symlink()
    assert config.read_text() == "foreign\n"
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_dry_run_symlink_reports_replace(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    foreign = home / "elsewhere"
    foreign.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(foreign)

    result = run(["restore", "--dry-run", "--force", "a"])
    assert result.exit_code == 0, output(result)
    assert "would copy: yes (replace symlink with a copy" in output(result)
    assert "Continue?" not in output(result)
    assert config.is_symlink()
    assert config.read_text() == "foreign\n"


def test_restore_force_overwrites_different_contents(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "a"], "y\n")
    assert result.exit_code == 0, output(result)
    assert "This will overwrite" in output(result)
    assert "Continue? [y/N/(d)iff]" in output(result)
    assert not config.is_symlink()
    assert config.read_text() == "stored\n"
    assert (home / ".bashrc.BAK").read_text() == "local\n"


def test_restore_force_prompt_shows_diff_then_overwrites(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "a"], "d\ny\n")
    assert result.exit_code == 0, output(result)
    assert output(result).count("Continue? [y/N/(d)iff]") > 1
    assert diff_viewer == [(config, stored)]
    assert not config.is_symlink()
    assert config.read_text() == "stored\n"


def test_restore_force_prompt_diff_then_aborts(
    home: Path, diff_viewer: list[tuple[Path, Path]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "a"], "d\nn\n")
    assert result.exit_code != 0
    assert output(result).count("Continue? [y/N/(d)iff]") > 1
    assert diff_viewer == [(config, stored)]
    assert config.read_text() == "local\n"
    assert not config.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_prompt_aborts(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "a"], "n\n")
    assert result.exit_code != 0
    assert "Continue?" in output(result)
    assert config.read_text() == "local\n"
    assert not config.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_without_conflict_does_not_prompt(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")

    result = run(["restore", "--force", "a"])
    assert result.exit_code == 0, output(result)
    assert "Continue?" not in output(result)
    assert not (home / ".bashrc").is_symlink()
    assert (home / ".bashrc").read_text() == "stored\n"


def test_list_without_init_fails(home: Path) -> None:
    result = run(["list"])
    assert result.exit_code != 0
    assert "init" in output(result)


def test_break_replaces_managed_symlink_with_copy(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.symlink_to(stored)

    result = run(["break", "a"])
    assert result.exit_code == 0, output(result)
    assert "broke" in output(result)
    assert not config.is_symlink()
    assert config.read_text() == "stored\n"
    assert stored.read_text() == "stored\n"


def test_break_requires_symlink(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    (home / ".bashrc").write_text("stored\n")

    result = run(["break", "a"])
    assert result.exit_code != 0
    assert "not a symlink" in output(result)


def test_break_is_hidden_from_help(home: Path) -> None:
    result = run(["--help"])
    assert result.exit_code == 0, output(result)
    assert "break" not in output(result)


def test_list_empty_root_pipe_is_silent(home: Path) -> None:
    assert run(["init", str(home / "tree")]).exit_code == 0
    result = run(["list"])
    assert result.exit_code == 0, output(result)
    assert not output(result)


def test_list_empty_root_terminal_reports_empty(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(["init", str(home / "tree")]).exit_code == 0
    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "_stdout_is_tty", lambda: True)

    result = run(["list"])
    assert result.exit_code == 0, output(result)
    assert "no stored config files" in output(result)


def test_list_pipe_is_tab_separated(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")
    assert run(["store", str(config)]).exit_code == 0

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    assert listed.output.splitlines() == [
        f"a\t{home}/.bashrc\t{root}/.bashrc\t✓"
    ]


def test_list_pipe_adds_state_when_a_host_differs(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    changed = home / ".bashrc"
    changed.write_text("stored")
    assert run(["store", str(changed)]).exit_code == 0
    unchanged = home / ".vimrc"
    unchanged.write_text("same")
    assert run(["store", str(unchanged)]).exit_code == 0
    changed.write_text("local")

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    assert listed.output.splitlines() == [
        f"a\t{home}/.bashrc\t{root}/.bashrc\t✗\tdiffers",
        f"b\t{home}/.vimrc\t{root}/.vimrc\t✓\t-",
    ]


def test_list_terminal_shows_state_for_problems(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".gemrc").write_text("stored")
    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "_stdout_is_tty", lambda: True)

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    text = output(listed)
    assert "State" in text
    assert "missing" in text


def test_list_terminal_shows_table(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")
    assert run(["store", str(config)]).exit_code == 0
    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "_stdout_is_tty", lambda: True)

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    text = output(listed)
    assert "ID" in text
    assert "Store" in text
    assert "Host" in text
    assert "Status" in text
    assert "State" not in text
    assert "~/tree/.bashrc" in text
    assert "~/.bashrc" in text
    assert "✓" in text


def test_list_color_always_colors_differing_paths_yellow(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("stored\n")
    assert run(["store", str(config)]).exit_code == 0
    config.write_text("local\n")

    listed = run(["--color", "always", "list"])
    assert listed.exit_code == 0, output(listed)
    assert "\x1b[33m" in listed.stdout
    assert "\x1b[36m" not in listed.stdout


def test_restore_rejects_unknown_id(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored")

    for ref in ("z", ".bashrc"):
        result = run(["restore", ref])
        assert result.exit_code != 0
        assert "unknown entry id" in output(result)
        assert "dotfig list" in output(result)


def test_list_and_restore_two_letter_ids(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    for index in range(27):
        (root / f"file{index:02d}").write_text(str(index))

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    assert "aa" in output(listed)

    first = run(["restore", "a"])
    assert first.exit_code == 0, output(first)
    assert not (home / "file00").is_symlink()
    assert (home / "file00").read_text() == "0"

    last = run(["restore", "aa"])
    assert last.exit_code == 0, output(last)
    assert not (home / "file26").is_symlink()
    assert (home / "file26").read_text() == "26"


def test_no_args_lists_entries(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")
    assert run(["store", str(config)]).exit_code == 0

    result = run([])
    assert result.exit_code == 0, output(result)
    assert result.output == run(["list"]).output
    assert str(config) in output(result)


def test_no_args_without_init_fails(home: Path) -> None:
    result = run([])
    assert result.exit_code != 0
    assert "init" in output(result)


def test_completions_writes_bash_script(home: Path) -> None:
    result = run(["--completions"])
    assert result.exit_code == 0, output(result)
    script = home / "data" / "bash-completion" / "completions" / "dotfig.bash"
    assert script.is_file()
    assert "_dotfig_complete" in script.read_text()
    assert result.stdout.strip() == str(script)
    assert "source " + str(script) in result.stderr
    assert "2.18" in result.stderr


def test_completions_overwrites_existing_file(home: Path) -> None:
    script = home / "data" / "bash-completion" / "completions" / "dotfig.bash"
    script.parent.mkdir(parents=True)
    script.write_text("stale")
    result = run(["--completions"])
    assert result.exit_code == 0, output(result)
    assert script.read_text() != "stale"
    assert script.stat().st_mode & 0o777 == EXPECTED_MODE


def test_completions_prefers_bash_completion_user_dir(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = home / "bash-completion-user"
    monkeypatch.setenv("BASH_COMPLETION_USER_DIR", f":{target}:")
    result = run(["--completions"])
    assert result.exit_code == 0, output(result)
    script = target / "bash-completion" / "completions" / "dotfig.bash"
    assert script.is_file()
    assert result.stdout.strip() == str(script)


def test_completions_falls_back_to_local_share(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)

    result = run(["--completions"])
    assert result.exit_code == 0, output(result)
    script = (
        home
        / ".local"
        / "share"
        / "bash-completion"
        / "completions"
        / "dotfig.bash"
    )
    assert script.is_file()
    assert result.stdout.strip() == str(script)


def test_completions_ignores_subcommand(home: Path) -> None:
    result = run(["--completions", "store", "--force"])
    assert result.exit_code == 0, output(result)
    script = home / "data" / "bash-completion" / "completions" / "dotfig.bash"
    assert script.is_file()


def test_completions_warns_for_old_bash(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("dotfig.completions")
    monkeypatch.setattr(module, "_bash_version", lambda: (3, 2))

    result = run(["--completions"])
    assert result.exit_code == 0, output(result)
    assert "bash 3.2 is too old" in result.stderr
    script = home / "data" / "bash-completion" / "completions" / "dotfig.bash"
    assert script.is_file()


def test_completions_warns_when_bash_is_missing(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = importlib.import_module("dotfig.completions")
    monkeypatch.setattr(module, "_bash_version", lambda: None)

    result = run(["--completions"])
    assert result.exit_code == 0, output(result)
    assert "bash was not found" in result.stderr


def test_completions_excludes_hidden_commands(home: Path) -> None:
    assert run(["--completions"]).exit_code == 0
    script = home / "data" / "bash-completion" / "completions" / "dotfig.bash"
    text = script.read_text()
    assert "break)" not in text
    assert "break " not in text


def test_color_always_emits_ansi(home: Path) -> None:
    result = run(["--color", "always", "init", str(home / "tree")])
    assert result.exit_code == 0, output(result)
    assert "\x1b[" in result.stdout


def test_color_never_emits_no_ansi(home: Path) -> None:
    result = run(["--color", "never", "init", str(home / "tree")])
    assert result.exit_code == 0, output(result)
    assert "\x1b[" not in result.stdout + result.stderr


def test_color_auto_emits_no_ansi_when_captured(home: Path) -> None:
    result = run(["--color", "auto", "init", str(home / "tree")])
    assert result.exit_code == 0, output(result)
    assert "\x1b[" not in result.stdout + result.stderr


def test_force_color_is_honored_in_auto_mode(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    result = run(["--color", "auto", "init", str(home / "tree")])
    assert result.exit_code == 0, output(result)
    assert "\x1b[" in result.stdout


def test_no_color_is_honored_in_auto_mode(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    result = run(
        ["--color", "auto", "--color", "always", "init", str(home / "tree")]
    )
    assert result.exit_code == 0, output(result)


def test_markup_in_user_input_is_escaped(home: Path) -> None:
    path = home / "[red]tree"
    result = run(["--color", "never", "init", str(path)])
    assert result.exit_code == 0, output(result)
    assert "[red]tree" in result.stdout


def test_errors_go_to_stderr(home: Path) -> None:
    result = run(["list"])
    assert result.exit_code != 0
    assert not result.stdout
    assert "error:" in result.stderr


def test_normal_output_goes_to_stdout(home: Path) -> None:
    result = run(["init", str(home / "tree")])
    assert result.exit_code == 0, output(result)
    assert "initialized" in result.stdout
    assert not result.stderr


def test_help_flags_for_every_command() -> None:
    commands = ("init", "list", "diff", "store", "restore")
    for command in commands:
        for flag in ("-h", "--help"):
            result = run([command, flag])
            assert result.exit_code == 0, (command, flag, output(result))
            assert "Usage" in result.output
            assert "\x1b[" not in result.output
    for flag in ("-h", "--help"):
        result = run([flag])
        assert result.exit_code == 0, output(result)
        assert "Usage" in result.output
        assert "\x1b[" not in result.output


def test_version_output_has_no_ansi() -> None:
    result = run(["--version"])
    assert result.exit_code == 0, output(result)
    assert "\x1b[" not in result.output


def test_config_flag_does_not_create_the_file(home: Path) -> None:
    result = run(["--config"])
    assert result.exit_code == 0, output(result)
    assert not config_path().exists()
    assert not config_path().parent.exists()


def test_config_output_has_no_ansi(home: Path) -> None:
    result = run(["--color", "always", "--config"])
    assert result.exit_code == 0, output(result)
    assert "\x1b[" not in result.output
    assert result.stdout.strip() == str(config_path())


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject.open("rb") as handle:
        expected = tomllib.load(handle)["project"]["version"]

    result = run(["--version"])

    assert result.exit_code == 0, output(result)
    assert result.output.strip() == f"dotfig, version {expected}"


def test_force_color_in_auto_mode_formats_list_for_people(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")
    assert run(["store", str(config)]).exit_code == 0
    monkeypatch.setenv("FORCE_COLOR", "1")

    listed = run(["--color", "auto", "list"])

    assert listed.exit_code == 0, output(listed)
    assert "ID" in listed.stdout
    assert "\x1b[" in listed.stdout
