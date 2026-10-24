"""Read and write the dotfig config file in the platform config directory."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "dotfig"
CONFIG_NAME = "config.toml"


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
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise DotfigError(f"{path} is not valid TOML: {exc}") from exc
        root = data.get("root")
        if not isinstance(root, str):
            raise DotfigError(f"{path} must contain a 'root' string")
        return cls(root=Path(root))

    def save(self, path: Path | None = None) -> None:
        """Write the config to disk, creating parent directories."""
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(
            [
                "# -*- mode: toml -*-",
                f"root = {toml_string(str(self.root))}",
                "",
            ]
        )
        path.write_text(text, encoding="utf-8")


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
