"""Read and write the dotfig config file in the platform config directory."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import click
from platformdirs import user_config_dir

APP_NAME = "dotfig"
CONFIG_NAME = "config.toml"
KNOWN_KEYS = frozenset({"root", "diff_tool"})


class DotfigError(Exception):
    """User-facing error; the CLI prints the message and exits non-zero."""


def config_path() -> Path:
    """Return the platform-specific path to the dotfig config file.

    Returns:
        The path to ``config.toml`` in the user's config directory.

    """
    return Path(user_config_dir(APP_NAME, appauthor=False)) / CONFIG_NAME


@dataclass(frozen=True)
class Config:
    """The dotfig root configured for a user."""

    root: Path
    diff_tool: str | None = None

    def __post_init__(self) -> None:
        """Normalize the root path and require it to be absolute.

        Raises:
            DotfigError: If the root is not an absolute path.

        """
        root = Path(os.path.expandvars(str(self.root))).expanduser()
        if not root.is_absolute():
            raise DotfigError(f"dotfig root must be an absolute path: {root}")
        object.__setattr__(self, "root", root)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load the config from disk.

        Returns:
            The parsed config.

        Raises:
            DotfigError: If the config is missing, invalid, or lacks a root.

        """
        path = path or config_path()
        if not path.is_file():
            raise DotfigError(f"{path} not found; run 'dotfig init PATH' first")
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise DotfigError(f"{path} is not valid TOML: {exc}") from exc
        unknown = sorted(set(data) - KNOWN_KEYS)
        if unknown:
            keys = ", ".join(unknown)
            click.echo(
                f"warning: ignoring unknown config key(s) in {path}: {keys}",
                err=True,
            )
        root = data.get("root")
        if not isinstance(root, str):
            raise DotfigError(f"{path} must contain a 'root' string")
        diff_tool = data.get("diff_tool")
        if diff_tool is not None and (
            not isinstance(diff_tool, str) or not diff_tool.strip()
        ):
            raise DotfigError(
                f"{path} must contain a non-empty 'diff_tool' string"
            )
        root_path = Path(os.path.expandvars(root)).expanduser()
        if not root_path.is_absolute():
            root_path = path.parent / root_path
        return cls(root=root_path, diff_tool=diff_tool)

    def save(self, path: Path | None = None) -> None:
        """Write the config to disk, creating parent directories."""
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# -*- mode: toml -*-",
            f"root = {toml_string(str(self.root))}",
        ]
        if self.diff_tool is not None:
            lines.append(f"diff_tool = {toml_string(self.diff_tool)}")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        path.chmod(0o600)


def toml_string(value: str) -> str:
    """Quote and escape a string as a TOML basic string.

    Returns:
        The value as a quoted TOML string.

    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'
