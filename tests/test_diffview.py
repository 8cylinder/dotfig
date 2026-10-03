from __future__ import annotations

import asyncio
from pathlib import Path

from textual_diff_view import DiffView

from dotfig.diffview import DiffApp


def make_pair(tmp_path: Path) -> tuple[Path, Path]:
    original = tmp_path / "original"
    modified = tmp_path / "modified"
    original.write_text("old line\n")
    modified.write_text("new line\n")
    return original, modified


def test_diff_app_mounts_diff_view(tmp_path: Path) -> None:
    original, modified = make_pair(tmp_path)

    async def run() -> None:
        app = DiffApp(original, modified, split=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert len(app.query(DiffView)) == 1
            assert app.diff_view is not None
            assert app.diff_view.split is False

    asyncio.run(run())


def test_diff_app_toggles(tmp_path: Path) -> None:
    original, modified = make_pair(tmp_path)

    async def run() -> None:
        app = DiffApp(original, modified, split=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.diff_view is not None
            assert app.diff_view.split is True
            assert app.diff_view.annotations is True
            app.action_toggle_split()
            app.action_toggle_annotations()
            await pilot.pause()
            assert app.diff_view.split is False
            assert app.diff_view.annotations is False

    asyncio.run(run())
