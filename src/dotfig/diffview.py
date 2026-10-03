"""Show file differences with the textual-diff-view widget."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual import containers, widgets
from textual.app import App, ComposeResult
from textual_diff_view import DiffView, LoadError

if TYPE_CHECKING:
    from pathlib import Path


class DiffApp(App[int]):
    """A Textual app that displays a diff between two files."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("space", "toggle_split", "Split"),
        ("a", "toggle_annotations", "Annotations"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, original: Path, modified: Path, *, split: bool) -> None:
        """Create the app.

        Args:
            original: Path to the original file.
            modified: Path to the modified file.
            split: Start in split (side-by-side) view when True.

        """
        super().__init__()
        self.original = original
        self.modified = modified
        self.split = split
        self.annotations = True
        self.diff_view: DiffView | None = None

    @override
    def compose(self) -> ComposeResult:
        """Lay out the scrollable diff area and the key footer.

        Yields:
            The diff scroll container and the key-binding footer.

        """
        yield containers.VerticalScroll(id="diff")
        yield widgets.Footer()

    async def on_mount(self) -> None:
        """Load the two files and mount the diff widget."""
        try:
            diff_view = await DiffView.load(
                self.original,
                self.modified,
                split=self.split,
                annotations=self.annotations,
            )
        except LoadError as error:
            self.notify(
                str(error), title="Failed to load diff", severity="error"
            )
            self.exit(1)
            return
        self.diff_view = diff_view
        await self.query_one("#diff", containers.VerticalScroll).mount(
            diff_view
        )

    def action_toggle_split(self) -> None:
        """Toggle between unified and split layouts."""
        if self.diff_view is not None:
            self.diff_view.split = not self.diff_view.split

    def action_toggle_annotations(self) -> None:
        """Toggle the +/- annotations."""
        if self.diff_view is not None:
            self.diff_view.annotations = not self.diff_view.annotations


def show_diff(original: Path, modified: Path, *, split: bool = False) -> None:
    """Display ORIGINAL and MODIFIED in an interactive diff viewer.

    Args:
        original: Path to the original file.
        modified: Path to the modified file.
        split: Start in split (side-by-side) view when True.

    """
    DiffApp(original, modified, split=split).run()
