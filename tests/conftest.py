from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from dotfig.config import Config


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def cfg(home: Path) -> Config:
    root = home / "dotfig-root"
    root.mkdir()
    return Config(root=root)


@pytest.fixture
def diff_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Path, Path, bool]]:
    """Stub the textual diff viewer and record what would be shown.

    Returns:
        A list of ``(original, modified, split)`` calls.

    """
    calls: list[tuple[Path, Path, bool]] = []

    def fake_show_diff(
        original: Path, modified: Path, *, split: bool = False
    ) -> None:
        calls.append((original, modified, split))

    module = importlib.import_module("dotfig.cli")
    monkeypatch.setattr(module, "show_diff", fake_show_diff)
    monkeypatch.setattr(module, "_can_use_tui", lambda: True)
    return calls
