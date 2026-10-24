# dotfig

[github.com/8cylinder/dotfig](https://github.com/8cylinder/dotfig)

Manage individual config files with a git-friendly tree. `dotfig` stores files
under a root directory that mirrors their path in `$HOME`, then replaces each
source file with a symlink to the stored copy. Commit the root to git and check
it out on other machines to sync your configs.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended)
- `make` for the development commands
- [gdiff](https://github.com/8cylinder/gdiff) on `PATH` for the interactive
  diff viewer. Without it, dotfig falls back to the standard `diff -u`
  command.

## Download and build

Clone the repository and install the CLI as an editable uv tool:

```sh
git clone https://github.com/8cylinder/dotfig.git
cd dotfig
make sync
make check
make install
dotfig --help
```

`make install` runs `uv tool install --editable --force .`, so the `dotfig`
command stays pointed at the checkout.

To work from the checkout without installing the tool:

```sh
make sync
uv run dotfig --help
```

## Global options

Every command supports `-h` and `--help`.

| Option | Description |
| --- | --- |
| `-h`, `--help` | Show help. |
| `--version` | Print the version from `pyproject.toml`. |
| `--config` | Print the config file path and exit. |
| `--completions` | Write the bash completion script and exit. |

## Shell completion

```sh
dotfig --completions
```

This writes a bash completion script to
`$XDG_DATA_HOME/bash-completion/completions/dotfig`, or
`~/.local/share/bash-completion/completions/dotfig` when `XDG_DATA_HOME` is not
set. It then prints the script path and the `source` command that enables
completion in the current shell.

Bash completion requires **bash 4.4 or newer** and bash-completion 2.x. On
macOS, `/bin/bash` is 3.2, so install a newer bash (for example with Homebrew),
use it as your shell, and source `bash-completion`. macOS defaults to zsh, which
is not covered because dotfig only writes bash completions. The
`dotfig --completions` command prints a warning when the `bash` on `PATH` is
older than 4.4.

## Usage

### init

```sh
dotfig init PATH
```

Create `PATH` (the dotfig root) if it doesn't exist and write the platform
config file. Use `--force` to overwrite an existing config.

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
shared trailing path components appear in cyan in both columns. The `.git`
directory is skipped so the root can itself be a git repo.

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
  (`Continue? [y/N/(d)iff]`) and `d` opens the diff viewer before asking again.
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
  nothing. Pass `--diff` to show the difference with
  [gdiff](https://github.com/8cylinder/gdiff), falling back to `diff -u` when
  gdiff is not installed. Pass `--force` to back the file up to `<name>.BAK`
  and replace it with a link to the stored copy. `--force` asks for confirmation
  (`Continue? [y/N/(d)iff]`) before overwriting; answer `d` to show the diff and
  be asked again. The gdiff viewer starts in side-by-side mode; `space` toggles
  split/unified, `A` toggles annotations, and `q` quits. Showing a diff needs an
  interactive terminal; otherwise dotfig reports an error.
- If the destination is a foreign symlink: error. Pass `--force` to back the
  link up to `<name>.BAK` and replace it with a link to the stored copy (with
  the same confirmation prompt). If it already points at the root: no-op.
- If there is no stored copy: error (`nothing to restore`).

`--diff` and `--force` combine with `--dry-run` to show what would happen
without touching the filesystem.

## Config file

The config is TOML in the platform's user config directory:

- Linux: `$XDG_CONFIG_HOME/dotfig/config.toml` (default
  `~/.config/dotfig/config.toml`)
- macOS: `~/Library/Application Support/dotfig/config.toml`
- Windows: `%APPDATA%\dotfig\config.toml`

Run `dotfig --config` to print the resolved path. The file stores the root
location:

```toml
# -*- mode: toml -*-
root = "/home/you/dotfiles"
```

`~` and environment variables are expanded when the config is loaded. Older
versions stored the config at `$HOME/.dotfig`; that path is no longer read, so
run `dotfig init PATH` again after upgrading.

## Development

Use the `Makefile` as the command runner:

```sh
make sync    # create .venv and install dependencies
make fmt     # format with ruff
make lint    # lint with ruff --fix
make type    # typecheck with ty
make test    # run pytest
make check   # format check, lint, typecheck, and tests
make install # install the CLI as an editable uv tool
```

Run a single test directly:

```sh
uv run pytest tests/test_core.py -k store
```

Layout:

- `src/dotfig/cli.py` -- click + rich commands and global options
- `src/dotfig/core.py` -- store/restore/list state machine and path mapping
- `src/dotfig/config.py` -- platform config path and TOML load/save
- `src/dotfig/diffview.py` -- diff viewer backed by gdiff, with `diff -u` fallback
- `tests/` -- pytest suite
