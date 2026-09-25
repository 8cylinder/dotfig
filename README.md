# dotfig

Manage individual config files with a git-friendly tree. `dotfig` stores files
under a root directory that mirrors their path in `$HOME`, then replaces each
source file with a symlink to the stored copy. Commit the root to git and check
it out on other machines to sync your configs.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended)

## Install

Install the CLI as a standalone tool:

```sh
uv tool install .
dotfig --help
```

Or work from a checkout:

```sh
git clone <repo-url> dotfig
cd dotfig
uv sync
uv run dotfig --help
```

## Usage

Every command supports `-h` / `--help`.

### init

```sh
dotfig init PATH
```

Create `PATH` (the dotfig root) if it doesn't exist and write the config file
`$HOME/.dotfig`. Use `--force` to overwrite an existing config.

```sh
dotfig init ~/dotfiles
```

### list

```sh
dotfig list
```

List every stored file with its source path and link status: `linked`,
`not linked`, `missing`, or `wrong link -> <target>`. The `.git` directory is
skipped so the root can itself be a git repo.

### store

```sh
dotfig store FILE
```

Move `FILE` into the root, mirroring its `$HOME` path, and symlink `FILE` back
to the stored copy.

- If `FILE` is already a correct symlink into the root: report it and do nothing.
- If a stored copy exists with the same contents: replace `FILE` with a symlink.
- If a stored copy exists with different contents: error and change nothing.
- `FILE` must be under `$HOME` and is never resolved through symlinks.

### restore

```sh
dotfig restore FILE
```

Recreate the symlink for `FILE` from the stored copy.

- If `FILE` is missing: create parent dirs and symlink it to the stored copy.
- If `FILE` is a regular file with identical contents: replace it with a symlink.
- If `FILE` is a regular file with different contents: error and change nothing.
- If `FILE` is a foreign symlink: error. If it already points at the root: no-op.
- If there is no stored copy: error (`nothing to restore`).

## Config file

`$HOME/.dotfig` stores the root location in TOML, without the `.toml`
extension. `~` and environment variables are expanded when it is loaded.

```toml
# -*- mode: toml -*-
root = "/home/you/dotfiles"
```

## Development

```sh
uv sync                      # create .venv and install dependencies
uv run dotfig                # run the CLI from the checkout

uv run pytest                # tests
uv run pytest tests/test_core.py -k store   # a single test

uv run ruff check            # lint (strict: all rules)
uv run ruff format           # format
uv run ty check              # typecheck
```

Layout:

- `src/dotfig/cli.py` -- click + rich commands
- `src/dotfig/core.py` -- store/restore/list state machine and path mapping
- `src/dotfig/config.py` -- `$HOME/.dotfig` load/save
- `tests/` -- pytest suite
