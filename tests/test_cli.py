from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from click.testing import CliRunner, Result

from dotfig.cli import _color_common, _print_diff, cli

if TYPE_CHECKING:
    import pytest


def run(args: list[str], input_text: str | None = None) -> Result:
    return CliRunner().invoke(cli, args, input=input_text)


def output(result: Result) -> str:
    return result.output + result.stderr


def test_color_common_marks_trailing_shared_path() -> None:
    common = ".config/cm/.env"
    assert _color_common("~/bin/dotfig/.config/cm/.env", common) == (
        "~/bin/dotfig/[cyan].config/cm/.env[/cyan]"
    )
    assert _color_common("~/.config/cm/.env", common) == (
        "~/[cyan].config/cm/.env[/cyan]"
    )


def test_color_common_leaves_other_paths_alone() -> None:
    assert _color_common("~/.bashrc", ".config") == "~/.bashrc"


def test_print_diff_opens_viewer(
    tmp_path: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    target = tmp_path / "target"
    current = tmp_path / "current"
    target.write_text("new\n")
    current.write_text("old\n")

    _print_diff(target, current, side_by_side=True)

    assert diff_viewer == [(current, target, True)]


def test_init_creates_root_and_config(home: Path) -> None:
    root = home / "tree"
    result = run(["init", str(root)])
    assert result.exit_code == 0, output(result)
    assert root.is_dir()
    assert (home / ".dotfig").is_file()
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
    assert config.is_symlink()
    assert (root / ".bashrc").read_text() == "export X=1"

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    assert ".bashrc" in output(listed)
    assert "linked" in output(listed)

    config.unlink()
    restored = run(["restore", ".bashrc"])
    assert restored.exit_code == 0, output(restored)
    assert config.is_symlink()


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
    assert config.is_symlink()
    assert stored.read_text() == "local\n"
    assert (root / ".bashrc.BAK").read_text() == "stored\n"


def test_store_force_prompt_shows_diff_then_aborts(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
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
    assert diff_viewer == [(stored, config, False)]
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


def test_restore_conflict_exits_nonzero(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored")
    config = home / ".bashrc"
    config.write_text("local")
    result = run(["restore", ".bashrc"])
    assert result.exit_code != 0
    assert "differs" in output(result)
    assert config.read_text() == "local"
    assert not config.is_symlink()


def test_restore_dry_run_makes_no_changes(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored")

    result = run(["restore", "--dry-run", ".bashrc"])
    assert result.exit_code == 0, output(result)
    assert "would symlink: yes" in output(result)
    assert not (home / ".bashrc").exists()

    short = run(["restore", "-d", ".bashrc"])
    assert short.exit_code == 0, output(short)
    assert "would symlink: yes" in output(short)
    assert not (home / ".bashrc").exists()


def test_restore_diff_opens_viewer(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--diff", ".bashrc"])
    assert result.exit_code != 0
    assert config.read_text() == "local\n"
    assert diff_viewer == [(config, stored, False)]

    no_diff = run(["restore", ".bashrc"])
    assert no_diff.exit_code != 0
    assert len(diff_viewer) == 1


def test_restore_diff_requires_terminal(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    (home / ".bashrc").write_text("local\n")
    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "_can_use_tui", lambda: False)

    result = run(["restore", "--diff", ".bashrc"])
    assert result.exit_code != 0
    assert "terminal" in output(result)


def test_restore_dry_run_diff(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--dry-run", "--diff", ".bashrc"])
    assert result.exit_code == 0, output(result)
    assert diff_viewer == [(config, stored, False)]


def test_restore_force_diff_opens_viewer(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "--diff", ".bashrc"], "y\n")
    assert result.exit_code == 0, output(result)
    assert diff_viewer == [(config, stored, False)]
    assert config.is_symlink()
    assert config.read_text() == "stored\n"


def test_restore_force_foreign_symlink_prompts(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    foreign = home / "elsewhere"
    foreign.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(foreign)

    result = run(["restore", "--force", ".bashrc"], "y\n")
    assert result.exit_code == 0, output(result)
    assert "This will overwrite" in output(result)
    assert config.is_symlink()
    assert config.read_text() == "stored\n"
    assert (home / ".bashrc.BAK").is_symlink()


def test_restore_force_foreign_symlink_diff_then_aborts(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    foreign = home / "elsewhere"
    foreign.write_text("foreign\n")
    config = home / ".bashrc"
    config.symlink_to(foreign)

    result = run(["restore", "--force", ".bashrc"], "d\nn\n")
    assert result.exit_code != 0
    assert diff_viewer == [(config, stored, False)]
    assert config.is_symlink()
    assert config.read_text() == "foreign\n"
    assert not (home / ".bashrc.BAK").exists()


def test_restore_side_by_side_opens_split_viewer(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--side-by-side", ".bashrc"])
    assert result.exit_code != 0
    assert config.read_text() == "local\n"
    assert diff_viewer == [(config, stored, True)]


def test_restore_force_side_by_side_prompt_diff(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "--side-by-side", ".bashrc"], "d\ny\n")
    assert result.exit_code == 0, output(result)
    assert config.is_symlink()
    assert config.read_text() == "stored\n"
    assert diff_viewer
    assert all(split for _, _, split in diff_viewer)
    assert diff_viewer[-1] == (config, stored, True)


def test_restore_force_overwrites_different_contents(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", ".bashrc"], "y\n")
    assert result.exit_code == 0, output(result)
    assert "This will overwrite" in output(result)
    assert "Continue? [y/N/(d)iff]" in output(result)
    assert config.is_symlink()
    assert config.read_text() == "stored\n"
    assert (home / ".bashrc.BAK").read_text() == "local\n"


def test_restore_force_prompt_shows_diff_then_overwrites(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", ".bashrc"], "d\ny\n")
    assert result.exit_code == 0, output(result)
    assert output(result).count("Continue? [y/N/(d)iff]") > 1
    assert diff_viewer == [(config, stored, False)]
    assert config.is_symlink()
    assert config.read_text() == "stored\n"


def test_restore_force_prompt_diff_then_aborts(
    home: Path, diff_viewer: list[tuple[Path, Path, bool]]
) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    stored = root / ".bashrc"
    stored.write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", ".bashrc"], "d\nn\n")
    assert result.exit_code != 0
    assert output(result).count("Continue? [y/N/(d)iff]") > 1
    assert diff_viewer == [(config, stored, False)]
    assert config.read_text() == "local\n"
    assert not config.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_prompt_aborts(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", ".bashrc"], "n\n")
    assert result.exit_code != 0
    assert "Continue?" in output(result)
    assert config.read_text() == "local\n"
    assert not config.is_symlink()
    assert not (home / ".bashrc.BAK").exists()


def test_restore_force_without_conflict_does_not_prompt(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")

    result = run(["restore", "--force", ".bashrc"])
    assert result.exit_code == 0, output(result)
    assert "Continue?" not in output(result)
    assert (home / ".bashrc").is_symlink()


def test_list_without_init_fails(home: Path) -> None:
    result = run(["list"])
    assert result.exit_code != 0
    assert "init" in output(result)


def test_list_empty_root(home: Path) -> None:
    assert run(["init", str(home / "tree")]).exit_code == 0
    result = run(["list"])
    assert result.exit_code == 0, output(result)
    assert "no stored config files" in output(result)


def test_list_shows_source_and_destination(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    config = home / ".bashrc"
    config.write_text("export X=1")
    assert run(["store", str(config)]).exit_code == 0

    listed = run(["list"])
    assert listed.exit_code == 0, output(listed)
    text = output(listed)
    assert "source" in text
    assert "destination" in text
    assert "~/tree/.bashrc" in text
    assert "~/.bashrc" in text
    assert "linked" in text


def test_completion_install_bash(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = home / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))

    result = run(["install-completions", "bash"])
    assert result.exit_code == 0, output(result)
    script = data / "bash-completion" / "completions" / "dotfig"
    assert script.is_file()
    assert "_dotfig_completion" in script.read_text()
    text = output(result)
    assert "created" in text
    assert f"source {script}" in text


def test_completion_install_reports_overwrite(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = home / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))

    assert run(["install-completions", "bash"]).exit_code == 0
    second = run(["install-completions", "bash"])
    assert second.exit_code == 0, output(second)
    assert "overwrote" in output(second)


def test_completion_install_defaults_to_shell_env(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = home / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("SHELL", "/usr/bin/fish")

    result = run(["install-completions"])
    assert result.exit_code == 0, output(result)
    script = config / "fish" / "completions" / "dotfig.fish"
    assert script.is_file()
    assert "_dotfig_completion" in script.read_text()
