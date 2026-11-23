from __future__ import annotations

import shlex
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path
from typing import TYPE_CHECKING

import click

from dotfig.cli import cli
from dotfig.completions import (
    _bash_version,
    completion_path,
    generate_bash,
    install_bash_completion,
)

if TYPE_CHECKING:
    import pytest

EXPECTED_MODE = 0o644


@click.group()
def demo() -> None:
    """Define a demo group for completion tests."""


@demo.command()
@click.option("--choice", type=click.Choice(["alpha", "beta"]))
@click.option("--count", type=int)
@click.option("--secret", hidden=True)
@click.option("--folder", type=click.Path(file_okay=False))
@click.option("--target", type=click.Path())
@click.option(
    "--pair", type=click.Tuple([click.Choice(["one", "two"]), click.Path()])
)
@click.argument("paths", nargs=-1, type=click.Path())
def files(
    choice: str | None,
    count: int | None,
    secret: str | None,
    folder: str | None,
    target: str | None,
    pair: tuple[str, str] | None,
    paths: tuple[str, ...],
) -> None:
    """Exercise option and argument completion."""


@demo.command(hidden=True)
def concealed() -> None:
    """Never offer this command."""


def complete(
    script: str,
    function: str,
    words: list[str],
    cword: int,
    cwd: Path,
) -> list[str]:
    """Run FUNCTION in bash and return the generated COMPREPLY entries.

    Returns:
        The completion replies, one per line.

    """
    script_dir = cwd.parent / f"{cwd.name}-scripts"
    script_dir.mkdir(exist_ok=True)
    path = script_dir / "completion.bash"
    path.write_text(script)
    array = " ".join(shlex.quote(word) for word in words)
    command = (
        f"source {shlex.quote(str(path))}\n"
        f"COMP_WORDS=({array})\n"
        f"COMP_CWORD={cword}\n"
        f"{function}\n"
        "if (( ${#COMPREPLY[@]} > 0 )); then\n"
        '    printf "%s\\n" "${COMPREPLY[@]}"\n'
        "fi\n"
    )
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["bash", "--norc", "--noprofile", "-c", command],  # ruff: ignore[start-process-with-partial-path]
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def dotfig_complete(
    words: list[str],
    cword: int,
    cwd: Path,
    *,
    script: str | None = None,
) -> list[str]:
    text = script or generate_bash(cli, "dotfig", "0.3.0")
    return complete(text, "_dotfig_complete", words, cword, cwd)


def demo_complete(words: list[str], cword: int, cwd: Path) -> list[str]:
    script = generate_bash(demo, "demo", "1.0")
    return complete(script, "_demo_complete", words, cword, cwd)


def test_destination_prefers_bash_completion_user_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("BASH_COMPLETION_USER_DIR", f":{first}:{second}")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    assert completion_path("dotfig") == (
        first / "bash-completion" / "completions" / "dotfig.bash"
    )


def test_destination_uses_xdg_data_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    assert completion_path("dotfig") == (
        tmp_path / "data" / "bash-completion" / "completions" / "dotfig.bash"
    )


def test_destination_falls_back_to_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert completion_path("dotfig") == (
        tmp_path
        / ".local"
        / "share"
        / "bash-completion"
        / "completions"
        / "dotfig.bash"
    )


def test_install_creates_parents_and_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
    path = completion_path("dotfig")
    path.parent.mkdir(parents=True)
    path.write_text("stale")

    result = install_bash_completion(cli, "dotfig", "0.3.0")

    assert result == path
    assert path.read_text() != "stale"
    assert path.stat().st_mode & 0o777 == EXPECTED_MODE


def test_install_prints_only_the_path_to_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)

    path = install_bash_completion(cli, "dotfig", "0.3.0")

    captured = capsys.readouterr()
    assert captured.out == f"{path}\n"
    assert str(path) in captured.err
    assert "Automatic loading needs bash-completion 2.18" in captured.err


def test_script_passes_bash_syntax_check(tmp_path: Path) -> None:
    script = tmp_path / "completion.bash"
    script.write_text(generate_bash(cli, "dotfig", "0.3.0"))

    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["bash", "-n", str(script)],  # ruff: ignore[start-process-with-partial-path]
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_header_names_app_and_version(tmp_path: Path) -> None:
    text = generate_bash(cli, "dotfig", "0.3.0")
    assert text.startswith("# bash completion for dotfig 0.3.0")
    assert "do not edit" in text


def test_subcommand_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", ""], 1, tmp_path)

    assert replies == ["init", "list", "diff", "store", "restore"]
    assert "break" not in replies


def test_subcommand_prefix_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "st"], 1, tmp_path)

    assert replies == ["store"]


def test_root_option_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "--"], 1, tmp_path)

    assert "--help" in replies
    assert "--version" in replies
    assert "--config" in replies
    assert "--completions" in replies
    assert "--color" in replies


def test_short_option_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "restore", "-"], 2, tmp_path)

    assert "-h" in replies
    assert "-d" in replies


def test_subcommand_option_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "store", "--"], 2, tmp_path)

    assert "--help" in replies
    assert "--force" in replies
    assert "--version" not in replies
    assert "--config" not in replies


def test_choice_value_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "--color", ""], 2, tmp_path)

    assert replies == ["auto", "always", "never"]


def test_choice_prefix_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "--color", "al"], 2, tmp_path)

    assert replies == ["always"]


def test_equals_value_completion(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "--color=al"], 1, tmp_path)

    assert replies == ["--color=always"]


def test_hidden_option_is_not_offered(tmp_path: Path) -> None:
    replies = demo_complete(["demo", "files", "--"], 2, tmp_path)

    assert "--secret" not in replies
    assert "--choice" in replies


def test_hidden_command_is_not_offered(tmp_path: Path) -> None:
    replies = demo_complete(["demo", ""], 1, tmp_path)

    assert "concealed" not in replies
    assert "files" in replies


def test_choice_option_value_completion(tmp_path: Path) -> None:
    replies = demo_complete(["demo", "files", "--choice", ""], 3, tmp_path)

    assert replies == ["alpha", "beta"]


def test_integer_option_has_no_suggestions(tmp_path: Path) -> None:
    replies = demo_complete(["demo", "files", "--count", ""], 3, tmp_path)

    assert replies == []


def test_file_completion(tmp_path: Path) -> None:
    (tmp_path / "alpha.conf").write_text("a")
    (tmp_path / "beta.conf").write_text("b")

    replies = demo_complete(["demo", "files", "al"], 2, tmp_path)

    assert replies == ["alpha.conf"]


def test_file_option_completion(tmp_path: Path) -> None:
    (tmp_path / "alpha.conf").write_text("a")

    replies = demo_complete(["demo", "files", "--target", "al"], 3, tmp_path)

    assert replies == ["alpha.conf"]


def test_directory_option_completion(tmp_path: Path) -> None:
    (tmp_path / "folder").mkdir()
    (tmp_path / "alpha.conf").write_text("a")

    replies = demo_complete(["demo", "files", "--folder", ""], 3, tmp_path)

    assert replies == ["folder"]


def test_equals_file_completion(tmp_path: Path) -> None:
    (tmp_path / "alpha.conf").write_text("a")

    replies = demo_complete(["demo", "files", "--target=al"], 2, tmp_path)

    assert replies == ["--target=alpha.conf"]


def test_tuple_first_value_completion(tmp_path: Path) -> None:
    replies = demo_complete(["demo", "files", "--pair", ""], 3, tmp_path)

    assert replies == ["one", "two"]


def test_tuple_second_value_completion(tmp_path: Path) -> None:
    (tmp_path / "alpha.conf").write_text("a")

    replies = demo_complete(["demo", "files", "--pair", "one", ""], 4, tmp_path)

    assert replies == ["alpha.conf"]


def test_variadic_argument_uses_last_type(tmp_path: Path) -> None:
    (tmp_path / "alpha.conf").write_text("a")
    (tmp_path / "beta.conf").write_text("b")

    replies = demo_complete(["demo", "files", "alpha.conf", "be"], 3, tmp_path)

    assert replies == ["beta.conf"]


def test_no_options_after_double_dash(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "--", ""], 2, tmp_path)

    assert replies == []


def test_old_bash_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
    monkeypatch.setattr("dotfig.completions._bash_version", lambda: (3, 2))

    install_bash_completion(cli, "dotfig", "0.3.0")

    assert "bash 3.2 is too old" in capsys.readouterr().err


def test_missing_bash_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
    monkeypatch.setattr("dotfig.completions._bash_version", lambda: None)

    install_bash_completion(cli, "dotfig", "0.3.0")

    assert "bash was not found" in capsys.readouterr().err


def test_bash_version_returns_a_version() -> None:
    version = _bash_version()
    assert version is None or version >= (4, 0)


def test_parent_options_are_not_offered_after_subcommand(
    tmp_path: Path,
) -> None:
    replies = dotfig_complete(["dotfig", "list", "--"], 2, tmp_path)

    assert "--color" not in replies
    assert "--version" not in replies


def test_help_options_are_offered_for_subcommands(tmp_path: Path) -> None:
    replies = dotfig_complete(["dotfig", "diff", "-"], 2, tmp_path)

    assert "-h" in replies
    assert "--help" in replies
