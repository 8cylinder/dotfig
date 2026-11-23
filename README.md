# dotfig

[github.com/8cylinder/dotfig](https://github.com/8cylinder/dotfig)

Manage individual config files with a git-friendly tree. `dotfig` keeps copies
of files in a root directory that mirrors their path in `$HOME`, copying files
between the store and the host. Commit the root to git and check it out on other
machines to sync your configs.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended)
- `make` for the development commands
- An optional external diff viewer on `PATH` for `dotfig diff` and the `d`
  prompt. Set `diff_tool` in the config; without it, dotfig uses `diff -u`.

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

List every stored file with four columns: `ID`, `Store` (the stored path in the
root), `Host` (the mirrored path under `$HOME`), and `Status`: `✓` when
the host path is a regular file with identical contents, `✗` when it differs,
is missing, is not a regular file, or is still a symlink. The `ID` column
assigns lowercase IDs from the current sorted list order: `a` through `z`, then
`aa`, `ab`, and so on. Use these IDs with `restore`. IDs are recomputed on each
run, so adding or removing a stored file can shift later IDs. Paths under
`$HOME` are shown with a leading `~`; paths outside it are shown absolute. The
shared trailing path components appear in cyan in both columns when the host
copy matches, and in yellow when it differs. The `.git` directory is skipped so
the root can itself be a git repo, and files whose names end in `.BAK` (backups
made by `--force`) are not listed.

Running `dotfig` with no arguments is equivalent to `dotfig list`.

When output is piped, `dotfig list` prints one row per entry with no header:
`id`, `store`, `host`, and `status` separated by tabs, without colors. This is
intended for tools such as `cut`:

```sh
dotfig list | cut -f1,3
```

An empty store prints nothing in this mode.

### diff

```sh
dotfig diff ID
```

Show the difference between the entry with `ID` and its host path under
`$HOME`. `ID` is the identifier shown by `dotfig list`; it is case-insensitive.
This is the same view that `restore --diff` opens: the host path is the
original side and the stored copy is the modified side. It uses the `diff_tool`
from the config, falling back to `diff -u` when the field is unset or the tool
is not on `PATH`, and needs an interactive terminal.

If the host path is missing or is not a file, the command fails. If the
contents match, it reports that and does not open the viewer.

### store

```sh
dotfig store FILE
dotfig store ID
```

Copy `FILE` into the root, mirroring its `$HOME` path. `FILE` stays in place as
a regular file; `dotfig` never creates symlinks. If the file is already stored,
`ID` from `dotfig list` (case-insensitive) can be passed instead of its path;
paths take precedence when the argument names an existing file.

- If `FILE` is a symlink: error and point at `dotfig break`.
- If a stored copy exists with the same contents: report it and do nothing.
- If a stored copy exists with different contents: error and change nothing.
  Pass `--force` to back the stored copy up to `<name>.BAK` and copy `FILE`
  instead. Like `restore --force`, it asks for confirmation
  (`Continue? [y/N/(d)iff]`) and `d` opens the diff viewer before asking again.
- `FILE` must be under `$HOME` and is never resolved through symlinks. A path
  inside the dotfig root is an error: it names a stored copy, and the message
  points at the matching config file under `$HOME`.

### restore

```sh
dotfig restore ID
```

Copy a stored file back to its host path in `$HOME`. `ID` is the identifier
shown by `dotfig list`; it is case-insensitive. Paths are no longer accepted, so
run `dotfig list` first if you don't know the ID. The mirrored path under `$HOME`
is the host path, and its parent directories are created if needed.

```sh
dotfig list
dotfig restore b
```

Pass `-d` / `--dry-run` to inspect without touching the filesystem. It prints
the host path, whether it exists, whether it matches the stored copy, and
whether a copy would be made (or why not).

- If the host path is missing: create parent dirs and copy the stored file.
- If the host path is a regular file with identical contents: report that it is
  already restored and change nothing.
- If the host path is a regular file with different contents: warn and change
  nothing. Pass `--diff` to show the difference with the configured
  `diff_tool`, falling back to `diff -u` when it is unset or not on `PATH`. Pass
  `--force` to back the file up to `<name>.BAK` and replace it with the stored
  copy. `--force` asks for confirmation (`Continue? [y/N/(d)iff]`) before
  overwriting; answer `d` to show the diff and be asked again. Showing a diff
  needs an interactive terminal; otherwise dotfig reports an error.
- If the host path is a symlink: error. Pass `--force` to ask for confirmation
  and replace the link (including a broken link or one pointing into the root)
  with a regular copy of the stored file; the link target is left untouched and
  no `.BAK` is made. `dotfig break ID` still converts a managed link.
- If the host path is a directory: error.
- If there is no stored copy: error (`nothing to restore`).

`--diff` and `--force` combine with `--dry-run` to show what would happen
without touching the filesystem.

### Migrating from symlinks

Earlier versions replaced host files with symlinks. To convert an existing
managed symlink into a regular copy, run `dotfig break ID`. The command is
hidden from `--help` and is intended only for this transition: it replaces the
link with a copy of the stored file.

## Config file

The config is TOML in the platform's user config directory:

- Linux: `$XDG_CONFIG_HOME/dotfig/config.toml` (default
  `~/.config/dotfig/config.toml`)
- macOS: `~/Library/Application Support/dotfig/config.toml`
- Windows: `%APPDATA%\dotfig\config.toml`

Run `dotfig --config` to print the resolved path. The file stores the root
location and optionally the diff viewer:

```toml
# -*- mode: toml -*-
root = "/home/you/dotfiles"
diff_tool = "diffuse"
```

`diff_tool` names an executable on `PATH`. dotfig runs it with the original and
modified file paths. When the field is absent or the executable is not on
`PATH`, dotfig falls back to `diff -u`.

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
- `src/dotfig/diffview.py` -- configured diff viewer with `diff -u` fallback
- `tests/` -- pytest suite
