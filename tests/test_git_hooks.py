from __future__ import annotations

import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path

HOOK = Path(__file__).parent.parent / ".githooks" / "pre-commit"
BASH = shutil.which("bash") or "/bin/bash"


def tools_directory(directory: Path) -> Path:
    """Create a PATH with only the commands the hook needs.

    Returns:
        The directory to put on PATH.

    """
    bin_dir = directory / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name in ("cat", "head"):
        target = shutil.which(name)
        link = bin_dir / name
        if target is not None and not link.exists():
            link.symlink_to(target)
    return bin_dir


def make_gitleaks(
    directory: Path,
    *,
    version: str = "8.30.1",
    exit_code: int = 0,
) -> Path:
    """Write a stub gitleaks that records its arguments.

    Returns:
        The path of the stub executable.

    """
    log = directory / "calls.log"
    stub = directory / "gitleaks"
    stub.write_text(
        f"#!{BASH}\n"
        'if [ "${1:-}" = version ]; then\n'
        f"    printf '%s\\n' {version}\n"
        "    exit 0\n"
        "fi\n"
        f'printf "%s\\n" "$*" >> {log}\n'
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)
    return log


def run_hook(directory: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PATH": str(directory),
    }
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [BASH, str(HOOK)],
        cwd=HOOK.parent.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_hook_parses() -> None:
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            BASH,
            "-n",
            str(HOOK),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_hook_is_executable() -> None:
    assert HOOK.stat().st_mode & 0o111


def test_missing_gitleaks_fails(tmp_path: Path) -> None:
    result = run_hook(tools_directory(tmp_path))

    assert result.returncode == 1
    assert "gitleaks is not installed" in result.stderr
    assert "github.com/gitleaks/gitleaks#installing" in result.stderr


def test_old_gitleaks_fails(tmp_path: Path) -> None:
    make_gitleaks(tools_directory(tmp_path), version="8.16.0")

    result = run_hook(tools_directory(tmp_path))

    assert result.returncode == 1
    assert "8.19" in result.stderr
    assert "found: 8.16.0" in result.stderr


def test_supported_gitleaks_scans_staged_changes(tmp_path: Path) -> None:
    log = make_gitleaks(tools_directory(tmp_path))

    result = run_hook(tools_directory(tmp_path))

    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        "git --staged --redact --no-banner --verbose"
    ]


def test_gitleaks_failure_fails_the_hook(tmp_path: Path) -> None:
    make_gitleaks(tools_directory(tmp_path), exit_code=1)

    result = run_hook(tools_directory(tmp_path))

    assert result.returncode == 1
