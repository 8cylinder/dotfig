from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner, Result

from dotfig.cli import cli


def run(args: list[str]) -> Result:
    return CliRunner().invoke(cli, args)


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
    restored = run(["restore", str(config)])
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


def test_list_without_init_fails(home: Path) -> None:
    result = run(["list"])
    assert result.exit_code != 0
    assert "init" in output(result)


def test_list_empty_root(home: Path) -> None:
    assert run(["init", str(home / "tree")]).exit_code == 0
    result = run(["list"])
    assert result.exit_code == 0, output(result)
    assert "no stored config files" in output(result)
