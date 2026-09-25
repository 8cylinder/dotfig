from __future__ import annotations

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
