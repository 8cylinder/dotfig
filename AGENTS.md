# AGENTS.md

## Setup
- `uv` project, Python 3.13 pinned in `.python-version`. Run `uv sync` to create
  `.venv`; it also installs the `dev` dependency group (pytest).
- `ruff` and `ty` are declared in `[project.dependencies]` (not a dev group), so
  `uv sync` installs them.

## Commands
- Run CLI: `uv run dotfig`
- Tests: `uv run pytest` (single test: `uv run pytest tests/test_core.py -k
  store`)
- Lint / format: `uv run ruff check` / `uv run ruff format`
- Typecheck: `uv run ty check`

## Layout
- `src/dotfig/cli.py` -- click + rich commands; `core.py` -- store/restore/list
  state machine and path mapping; `config.py` -- `$HOME/.dotfig`
  load/save. Entry point `dotfig:main` in `src/dotfig/__init__.py`.
- README is the behavior spec for `core.py` (`init` / `list` / `store` /
  `restore`).
- `.dotfig` is TOML stored in a file with no `.toml` extension: read with stdlib
  `tomllib`, written by a hand-rolled escaper in `config.py` (no TOML writer
  dependency).

## Gotchas
- `core.absolute()` uses `os.path.abspath` on purpose: never use
  `Path.resolve()` on user paths, it follows symlinks and would break
  managed/symlink detection.
- Stored paths mirror `$HOME` under the root; `list_managed` skips `.git` so the
  root tree can itself be a git repo.
