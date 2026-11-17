from __future__ import annotations

from pathlib import Path

import pytest

from dotfig.config import Config, DotfigError, config_path, toml_string


def test_config_path_uses_platform_config_dir(home: Path) -> None:
    assert config_path() == home / "config" / "dotfig" / "config.toml"


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "root"
    path = tmp_path / "config"
    Config(root=root).save(path=path)
    assert Config.load(path=path).root == root


def test_save_and_load_round_trip_with_diff_tool(tmp_path: Path) -> None:
    root = tmp_path / "root"
    path = tmp_path / "config"
    Config(root=root, diff_tool="diffuse").save(path=path)
    loaded = Config.load(path=path)
    assert loaded.root == root
    assert loaded.diff_tool == "diffuse"


def test_save_writes_toml_with_mode_comment(tmp_path: Path) -> None:
    path = tmp_path / "config"
    Config(root=tmp_path / "root").save(path=path)
    text = path.read_text()
    assert text.startswith("# -*- mode: toml -*-\n")
    assert "root = " in text
    assert "diff_tool" not in text


def test_save_escapes_quotes_and_backslashes(tmp_path: Path) -> None:
    root = tmp_path / 'we"ird\\root'
    root.mkdir()
    path = tmp_path / "config"
    Config(root=root).save(path=path)
    assert Config.load(path=path).root == root


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(DotfigError, match="init"):
        Config.load(path=tmp_path / "missing")


def test_load_invalid_toml_raises(tmp_path: Path) -> None:
    path = tmp_path / "config"
    path.write_text("root = [")
    with pytest.raises(DotfigError, match="valid TOML"):
        Config.load(path=path)


def test_load_without_root_raises(tmp_path: Path) -> None:
    path = tmp_path / "config"
    path.write_text('other = "x"\n')
    with pytest.raises(DotfigError, match="'root'"):
        Config.load(path=path)


def test_load_without_diff_tool_defaults_to_none(tmp_path: Path) -> None:
    path = tmp_path / "config"
    path.write_text(f'root = "{tmp_path / "root"}"\n')
    assert Config.load(path=path).diff_tool is None


def test_load_invalid_diff_tool_raises(tmp_path: Path) -> None:
    path = tmp_path / "config"
    path.write_text(f'root = "{tmp_path / "root"}"\ndiff_tool = 1\n')
    with pytest.raises(DotfigError, match="'diff_tool'"):
        Config.load(path=path)


def test_load_empty_diff_tool_raises(tmp_path: Path) -> None:
    path = tmp_path / "config"
    path.write_text(f'root = "{tmp_path / "root"}"\ndiff_tool = "  "\n')
    with pytest.raises(DotfigError, match="'diff_tool'"):
        Config.load(path=path)


def test_load_expands_environment_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MY_ROOT", str(tmp_path / "tree"))
    path = tmp_path / "config"
    path.write_text('root = "$MY_ROOT"\n')
    assert Config.load(path=path).root == tmp_path / "tree"


def test_load_expands_tilde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / "config"
    path.write_text('root = "~/tree"\n')
    assert Config.load(path=path).root == tmp_path / "tree"


def test_relative_root_rejected() -> None:
    with pytest.raises(DotfigError, match="absolute"):
        Config(root=Path("relative/root"))


def test_toml_string_escapes() -> None:
    assert toml_string('a"b\\c') == '"a\\"b\\\\c"'
