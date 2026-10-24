from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path

import pytest

from dotfig import diffview
from dotfig.config import DotfigError


def make_pair(tmp_path: Path) -> tuple[Path, Path]:
    original = tmp_path / "original"
    modified = tmp_path / "modified"
    original.write_text("old line\n")
    modified.write_text("new line\n")
    return original, modified


def fake_run(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(
        args: list[str], *, check: bool
    ) -> subprocess.CompletedProcess[bytes]:
        assert check is False
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode)

    monkeypatch.setattr(diffview.subprocess, "run", run)
    return calls


def test_show_diff_uses_gdiff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, modified = make_pair(tmp_path)
    calls = fake_run(monkeypatch, 0)
    monkeypatch.setattr(diffview.shutil, "which", lambda _: "/usr/bin/gdiff")

    diffview.show_diff(original, modified)

    assert calls == [["/usr/bin/gdiff", str(original), str(modified)]]


def test_show_diff_falls_back_when_gdiff_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, modified = make_pair(tmp_path)
    calls = fake_run(monkeypatch, 1)
    monkeypatch.setattr(
        diffview.shutil,
        "which",
        lambda name: "/usr/bin/diff" if name == "diff" else None,
    )

    diffview.show_diff(original, modified)

    assert calls == [["/usr/bin/diff", "-u", str(original), str(modified)]]


def test_show_diff_raises_when_no_tool_is_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, modified = make_pair(tmp_path)
    monkeypatch.setattr(diffview.shutil, "which", lambda _: None)

    with pytest.raises(DotfigError, match="no diff command"):
        diffview.show_diff(original, modified)


def test_show_diff_raises_when_gdiff_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, modified = make_pair(tmp_path)
    fake_run(monkeypatch, 2)
    monkeypatch.setattr(diffview.shutil, "which", lambda _: "/usr/bin/gdiff")

    with pytest.raises(DotfigError, match="gdiff exited with status 2"):
        diffview.show_diff(original, modified)


def test_show_diff_raises_when_diff_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, modified = make_pair(tmp_path)
    fake_run(monkeypatch, 2)
    monkeypatch.setattr(
        diffview.shutil,
        "which",
        lambda name: "/usr/bin/diff" if name == "diff" else None,
    )

    with pytest.raises(DotfigError, match="diff exited with status 2"):
        diffview.show_diff(original, modified)


def test_show_diff_resolves_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.write_text("linked\n")
    link = tmp_path / "link"
    link.symlink_to(target)
    _, modified = make_pair(tmp_path)
    calls = fake_run(monkeypatch, 0)
    monkeypatch.setattr(diffview.shutil, "which", lambda _: "/usr/bin/gdiff")

    diffview.show_diff(link, modified)

    assert calls == [["/usr/bin/gdiff", str(target), str(modified)]]
