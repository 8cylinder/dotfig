# AGENTS.md

## Setup
- `uv` project, Python 3.13 pinned in `.python-version`. Run `make sync` (or
  `uv sync --all-groups`) to create `.venv`; it installs the `dev` dependency
  group.
- `ruff`, `ty`, `pytest`, `pytest-cov`, and the Sphinx man-page dependencies are
  in `[dependency-groups].dev`, not runtime dependencies.
- Tests enforce 90% branch coverage via `pytest-cov`; the full suite currently
  runs at about 94%.

## Commands
- Use the `Makefile` (`make help` is the default target): `make sync`, `make
  hooks`, `make fmt`, `make fmt-check`, `make lint`, `make lint-check`, `make
  type`, `make test`, `make man`, `make check`, `make ci`, `make build`,
  `make install`, `make install-completions`, `make install-man`,
  `make uninstall`, `make upgrade`, `make clean`.
- `make check` must not modify source files; it runs fmt-check, lint-check,
  type, test, and man.
- `make ci` runs a locked sync, `make check`, and `make secrets`. `secrets`
  needs `gitleaks` on `PATH`.
- Run CLI: `uv run dotfig`
- Tests: `uv run pytest` (single test: `uv run pytest tests/test_core.py -k
  store`)
- Lint / format: `uv run ruff check` / `uv run ruff format`
- Typecheck: `uv run ty check`

## Layout
- `src/dotfig/cli.py` -- click + rich commands and global options; `core.py` --
  store/restore/list state machine and path mapping; `config.py` -- platform
  config path and TOML load/save; `completions.py` -- static bash completion
  generation and installation; `diffview.py` -- shells out to the configured
  `diff_tool`, falling back to `diff -u`, and runs diffuse `--ask` for `sync`.
  Entry point `dotfig:main` in `src/dotfig/__init__.py`.
- README is the behavior spec for `core.py` (`init` / `list` / `diff` / `sync` /
  `store` / `restore`) and the installation/development guide.
- Running `dotfig` with no subcommand invokes `list` (the group uses
  `invoke_without_command` and `no_args_is_help=False`). This is intentional;
  do not switch to `no_args_is_help=True` without asking.
- `list` assigns ephemeral IDs from the sorted `list_managed` order (`a`..`z`,
  then `aa`, `ab`, ...). `restore ID` resolves that ID only and does not accept
  stored paths.
- The config is TOML at the platform config path (`config.toml`, resolved with
  `platformdirs`) and is read with stdlib `tomllib` in binary mode. `config.py`
  writes it with a hand-rolled escaper (no TOML writer dependency) and mode
  `0600`. Unknown keys warn on stderr and are ignored. `dotfig --config` prints
  the path and exits without creating anything.
- `--completions` writes a static script to
  `$BASH_COMPLETION_USER_DIR` (first non-empty entry), `$XDG_DATA_HOME`, or
  `~/.local/share`, under `bash-completion/completions/dotfig.bash`. Only the
  path goes to stdout; the `source` hint and warnings go to stderr. It is a
  base-command flag, not a subcommand. Regenerate after changing the command
  tree; the script must not run Python at tab-press time.
- The man page is built by Sphinx from `docs/cli.rst` (sphinx-click + MyST for
  the ADR Markdown); `docs/_build/` is generated. `make install` runs
  `dotfig --completions` and installs `docs/_build/man/dotfig.1`.
- `.githooks/pre-commit` blocks staged secrets with gitleaks 8.19+; install it
  with `make hooks`. CI also runs `make secrets` against full history.
- `.github/workflows/ci.yml` and `codeql.yml` mirror the local checks. Do not
  add Codespaces/Pages settings; the project publishes the man page only.

## Output and color
- Consoles are created per invocation in the root callback after global
  options are parsed and stored on `ctx.obj` (`Output`); do not add a
  module-level console.
- `--color=auto` uses Rich's terminal detection and respects `NO_COLOR`,
  `FORCE_COLOR`, and `TERM=dumb`; `always` forces color; `never` disables ANSI.
  Set `ctx.color` to match so Click's own messages agree.
- Use `rich.markup.escape()` on every dynamic value inserted into markup.
- Errors and warnings go to stderr with an `error:` / `warning:` label; normal
  output goes to stdout. `--version`, `--config`, `--completions`, and piped
  `list` output must stay plain.
- Do not add rich-click. Help output is plain Click text.

## Gotchas
- `core.absolute()` uses `os.path.abspath` on purpose: never use
  `Path.resolve()` on user paths, it follows symlinks and would break
  managed/symlink detection. The one exception is `diffview.show_diff`, which
  resolves symlinks for display so the viewer diffs the target contents.
- Diffs use the optional `diff_tool` from the config and fall back to `diff -u`
  when it is unset or missing from `PATH`; do not add an in-process
  diff-viewer dependency.
- Stored paths mirror `$HOME` under the root; `list_managed` skips `.git` so the
  root tree can itself be a git repo.
- Provide `-h` through `AppCommand` / `AppGroup` (pass `cls=AppCommand`) for
  every command instead of relying on Click inheritance. Do not use `-h` for
  another option.
- The static completion generator uses bash 4.4 arrays and `compopt`; tests
  execute the generated script in a real bash and must not write to the real
  home directory.
