from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner, Result

from dotfig.cli import cli


def run(args: list[str], input_text: str | None = None) -> Result:
    return CliRunner().invoke(cli, args, input=input_text)


def output(result: Result) -> str:
    return result.output + result.stderr


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


def test_restore_diff_shows_changes(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--diff", ".bashrc"])
    assert result.exit_code != 0
    text = output(result)
    assert "-local" in text
    assert "+stored" in text
    assert config.read_text() == "local\n"

    no_diff = run(["restore", ".bashrc"])
    assert "-local" not in output(no_diff)


def test_restore_dry_run_diff(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    (home / ".bashrc").write_text("local\n")

    result = run(["restore", "--dry-run", "--diff", ".bashrc"])
    assert result.exit_code == 0, output(result)
    assert "-local" in output(result)
    assert "+stored" in output(result)


def test_restore_force_diff_shows_diff(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", "--diff", ".bashrc"], "y\n")
    assert result.exit_code == 0, output(result)
    text = output(result)
    assert "-local" in text
    assert "+stored" in text
    assert config.is_symlink()
    assert config.read_text() == "stored\n"


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


def test_restore_force_prompt_shows_diff_then_overwrites(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", ".bashrc"], "d\ny\n")
    assert result.exit_code == 0, output(result)
    text = output(result)
    assert "-local" in text
    assert "+stored" in text
    assert text.count("Continue? [y/N/(d)iff]") > 1
    assert config.is_symlink()
    assert config.read_text() == "stored\n"


def test_restore_force_prompt_diff_then_aborts(home: Path) -> None:
    root = home / "tree"
    assert run(["init", str(root)]).exit_code == 0
    (root / ".bashrc").write_text("stored\n")
    config = home / ".bashrc"
    config.write_text("local\n")

    result = run(["restore", "--force", ".bashrc"], "d\nn\n")
    assert result.exit_code != 0
    text = output(result)
    assert "-local" in text
    assert "+stored" in text
    assert text.count("Continue? [y/N/(d)iff]") > 1
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
