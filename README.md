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

List every stored file with three columns: `source` (the stored path in the
root), `destination` (the mirrored path under `$HOME`), and the link status:
`linked`, `not linked`, `missing`, or `wrong link -> <target>`. Paths under
`$HOME` are shown with a leading `~`; paths outside it are shown absolute. The
`.git` directory is skipped so the root can itself be a git repo.

### store

```sh
dotfig store FILE
```

Move `FILE` into the root, mirroring its `$HOME` path, and symlink `FILE` back
to the stored copy.

- If `FILE` is already a correct symlink into the root: report it and do nothing.
- If a stored copy exists with the same contents: replace `FILE` with a symlink.
- If a stored copy exists with different contents: error and change nothing.
  Pass `--force` to back the stored copy up to `<name>.BAK` and store `FILE`
  instead. Like `restore --force`, it asks for confirmation
  (`Continue? [y/N/(d)iff]`) and `d` prints the diff before asking again.
- `FILE` must be under `$HOME` and is never resolved through symlinks. A path
  inside the dotfig root is an error: it names a stored copy, and the message
  points at the matching config file under `$HOME`.

### restore

```sh
dotfig restore FILE
```

Recreate a stored file's symlink in `$HOME`. `FILE` names a file inside the
dotfig root, either relative to the root or as an absolute path under it. The
mirrored path under `$HOME` is the destination, and its parent directories are
created if needed.

```sh
dotfig restore .config/path/to/config.json
```

Pass `-d` / `--dry-run` to inspect without touching the filesystem. It prints
the destination path, whether it exists, whether it matches the stored copy,
and whether a symlink would be created (or why not).

- If the destination is missing: create parent dirs and symlink it to the
  stored copy.
- If the destination is a regular file with identical contents: rename it to
  `<name>.BAK`, then symlink it to the stored copy.
- If the destination is a regular file with different contents: warn and change
  nothing. Pass `--diff` to print a unified diff of the difference, or
  `--side-by-side` to print the two files as aligned columns (`destination` and
  `stored`). Pass `--force` to back the file up to `<name>.BAK` and replace it
  with a link to the stored copy. `--force` asks for confirmation
  (`Continue? [y/N/(d)iff]`) before overwriting; answer `d` to print the diff
  (side by side when `--side-by-side` is given) and be asked again.
- If the destination is a foreign symlink: error. If it already points at the
  root: no-op.
- If there is no stored copy: error (`nothing to restore`).

`--diff`, `--side-by-side`, and `--force` combine with `--dry-run` to show what
would happen without touching the filesystem.

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
