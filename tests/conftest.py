from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from dotfig.config import Config


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    config = importlib.import_module("dotfig.config")
    monkeypatch.setattr(
        config,
        "user_config_dir",
        lambda *_args, **_kwargs: str(tmp_path / "config" / "dotfig"),
    )
    return tmp_path


@pytest.fixture
def cfg(home: Path) -> Config:
    root = home / "dotfig-root"
    root.mkdir()
    return Config(root=root)


@pytest.fixture
def diff_viewer(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, Path]]:
    """Stub the external diff tool and record what would be shown.

    Returns:
        A list of ``(original, modified)`` calls.

    """
    calls: list[tuple[Path, Path]] = []

    def fake_show_diff(original: Path, modified: Path) -> None:
        calls.append((original, modified))

    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "show_diff", fake_show_diff)
    monkeypatch.setattr(module, "_can_use_tui", lambda: True)
    return calls
