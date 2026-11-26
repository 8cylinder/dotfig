# dotfig

[github.com/8cylinder/dotfig](https://github.com/8cylinder/dotfig)

[![CI](https://github.com/8cylinder/dotfig/actions/workflows/ci.yml/badge.svg)](https://github.com/8cylinder/dotfig/actions/workflows/ci.yml)
[![License: GPL-2.0-only](https://img.shields.io/badge/license-GPL--2.0--only-blue.svg)](LICENSE)

Manage individual config files with a git-friendly tree. dotfig keeps copies of
files in a root directory that mirrors their path in `$HOME`, copying files
between the store and the host. Commit the root to git and check it out on other
machines to sync your configs.

## Requirements

- Python 3.13 or newer.
- [uv](https://docs.astral.sh/uv/) and `make` for development and installation
  from source.
- bash 4.4 or newer for the generated completions.
- bash-completion 2.18 or newer for automatic completion loading.
- [gitleaks](https://github.com/gitleaks/gitleaks#installing) 8.19 or newer to
  commit; the pre-commit hook blocks secrets. CI runs the same scan.
- Linux or macOS. Windows is not supported because dotfig relies on POSIX
  paths and the commit hook is a bash script.
- An optional external diff viewer on `PATH` for `dotfig diff` and the `d`
  prompt. Set `diff_tool` in the config; without it, dotfig uses `diff -u`.

## Installation

dotfig is not published on PyPI. Install it from source:

```sh
git clone https://github.com/8cylinder/dotfig.git
cd dotfig
make sync
make install
dotfig --help
```

`make install` runs `uv tool install --editable --force .`, then generates bash
completions and builds and installs the man page. Because the install is
editable, the `dotfig` command stays pointed at the checkout.

To work from the checkout without installing the tool:

```sh
make sync
uv run dotfig --help
```

Installing the Python package with `uv tool install dotfig` (if it were
published) would install the command but not the man page, because `uv tool`
does not install manual pages.

## Quick start

Store your shell configuration and list it:

```console
$ dotfig init ~/dotfiles
ok initialized dotfig root at /home/you/dotfiles
ok wrote /home/you/.config/dotfig/config.toml
$ dotfig store ~/.bashrc
ok stored /home/you/.bashrc
$ dotfig list
ID   Host          Store                 Status
a    ~/.bashrc     ~/dotfiles/.bashrc    ✓
```

Restore it on another machine after cloning `~/dotfiles`:

```console
$ dotfig init ~/dotfiles
$ dotfig list
$ dotfig restore a
ok restored /home/you/.bashrc
```

## Command reference

Run `dotfig --help` or `dotfig -h` for the built-in reference, and
`man dotfig` for the man page.

### Global options

Global options are root-level, so they must appear before a subcommand.

| Option | Description |
| --- | --- |
| `-h`, `--help` | Show help. |
| `--version` | Print the version from `pyproject.toml`. |
| `--config` | Print the config file path and exit. |
| `--completions` | Write the bash completion script and exit. |
| `--color [auto\|always\|never]` | Control colored output. Defaults to `auto`. |

`--color=auto` colors output only on a terminal and respects `NO_COLOR`,
`FORCE_COLOR`, and `TERM=dumb`. `--color=always` forces color, including in a
pipe. `--color=never` disables color and ANSI styling. Machine-readable output
(`--version`, `--config`, `--completions`) never contains ANSI escapes, and
piped `list` output is plain unless color is forced with `--color=always`.

Running `dotfig` with no arguments is equivalent to `dotfig list`.

### init

```sh
dotfig init PATH
```

Create `PATH` (the dotfig root) if it does not exist and write the platform
config file. The config file is created with mode `0600`. Use `--force` to
overwrite an existing config.

```sh
dotfig init ~/dotfiles
```

### list

```sh
dotfig list
```

List every stored file with four columns by default: `ID`, `Host` (the mirrored
path under `$HOME`), `Store` (the stored path in the root), and `Status`: `✓`
when the host path is a regular file with identical contents, `✗` when it
differs, is missing, is not a regular file, or is still a symlink. When any
entry is `✗`, `list` adds a `State` column saying why: `missing`, `symlink` (a
live symlink), `broken symlink` (a symlink whose target does not exist),
`differs` (a regular file with different contents), or `not a file` (a
directory or other non-regular file). The column is omitted when every entry
matches. The `ID` column assigns lowercase IDs from the current sorted list
order: `a` through `z`, then `aa`, `ab`, and so on. Use these IDs with
`restore`. IDs are recomputed on each run, so adding or removing a stored file
can shift later IDs. Paths under `$HOME` are shown with a leading `~`; paths
outside it are shown absolute. The shared trailing path components appear in
cyan in both columns when the host copy matches, and in yellow when it
differs. The `.git` directory is skipped so the root can itself be a git repo,
and files whose names end in `.BAK` (backups made by `--force`) are not
listed.

When output is piped, `dotfig list` prints one row per entry with no header:
`id`, `store`, `host`, and `status` separated by tabs, without colors. The
`store` and `host` fields are absolute paths, unlike the `~`-shortened paths in
the terminal table. When the `State` column is present, each row gains a fifth
field with the state, or `-` for a matching entry. This is intended for tools
such as `cut`:

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
This is the same view that `restore --diff` and the `--force` prompt open: in
every diff, the host path is the original (left) side and the stored copy is
the modified (right) side. It uses the `diff_tool` from the config, falling
back to `diff -u` when the field is unset or the tool is not on `PATH`, and
needs an interactive terminal.

If the host path is missing or is not a file, the command fails. If the contents
match, it reports that and does not open the viewer.

### store

```sh
dotfig store FILE
dotfig store ID
```

Copy `FILE` into the root, mirroring its `$HOME` path. `FILE` stays in place as
a regular file; dotfig never creates symlinks. If the file is already stored,
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
shown by `dotfig list`; it is case-insensitive. Paths are not accepted, so run
`dotfig list` first if you do not know the ID. The mirrored path under `$HOME`
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

## Configuration

The config is TOML in the platform's user config directory:

- Linux: `$XDG_CONFIG_HOME/dotfig/config.toml` (default
  `~/.config/dotfig/config.toml`)
- macOS: `~/Library/Application Support/dotfig/config.toml`

Run `dotfig --config` to print the resolved path. It does not create the
directory or the file.

```toml
# -*- mode: toml -*-
root = "/home/you/dotfiles"
diff_tool = "diffuse"
```

`root` is required. A relative `root` resolves against the config file's
directory, not the current working directory. `diff_tool` names an executable
on `PATH`; dotfig runs it with the original and modified file paths. When the
field is absent or the executable is not on `PATH`, dotfig falls back to
`diff -u`.

A missing config file is an error for commands that need the root; run
`dotfig init PATH` first. Invalid TOML is an error that names the file. Unknown
keys produce a warning on stderr and are ignored so older configs keep working.

`~` and environment variables are expanded when the config is loaded. Older
versions stored the config at `$HOME/.dotfig`; that path is no longer read, so
run `dotfig init PATH` again after upgrading.

## Bash completions

```sh
dotfig --completions
```

This writes a static bash completion script and prints its path on stdout:

```console
$ dotfig --completions
/home/you/.local/share/bash-completion/completions/dotfig.bash
To use it in this shell:
  source /home/you/.local/share/bash-completion/completions/dotfig.bash
```

The `source` instruction goes to stderr, so command substitution gets only the
path. The destination is resolved in this order:

1. The first non-empty entry in `BASH_COMPLETION_USER_DIR`.
2. `$XDG_DATA_HOME`.
3. `~/.local/share`.

The file is always named `dotfig.bash` and is overwritten on each run. Regenerate
it after changing commands or options. Earlier versions wrote an unsuffixed
`dotfig` file in the same directory; delete it if it is still there.

Bash completion requires **bash 4.4 or newer** and bash-completion 2.18 or newer
for automatic loading. On macOS, `/bin/bash` is 3.2, so install a newer bash
(for example `brew install bash`) and use it as your shell. Zsh is not
supported because dotfig writes bash completions only. `dotfig --completions`
prints a warning when the `bash` on `PATH` is missing or older than 4.4.

## Man page

`make install` builds the man page with Sphinx and installs it to
`$XDG_DATA_HOME/man/man1` (or `~/.local/share/man/man1`). View it with:

```sh
man dotfig
```

If `man` cannot find the page, add that directory to `MANPATH`:

```sh
export MANPATH="${XDG_DATA_HOME:-$HOME/.local/share}/man:${MANPATH:-}"
```

Build it without installing with `make man`, then read
`docs/_build/man/dotfig.1` directly:

```sh
man -l docs/_build/man/dotfig.1
```

The man page is generated from `docs/cli.rst` with sphinx-click; it is not
committed.

## Documentation

This project publishes the man page only. There is no HTML documentation site.
The design decisions live in [`docs/adr/`](docs/adr/).

## Development

Use the `Makefile` as the command runner:

```sh
make sync     # create .venv and install all dependency groups
make hooks    # install the git hook that blocks secrets
make fmt      # format with ruff
make lint     # lint with ruff and apply safe fixes
make type     # type-check with ty
make test     # run pytest with branch coverage
make check    # format, lint, type, test, and man checks
make secrets  # scan the repository history with gitleaks
make build    # build the wheel and sdist into dist/
```

`make check` does not modify source files. Use `make fmt` and `make lint` when
you want fixes.

Run `make hooks` once per clone. It sets `core.hooksPath` to `.githooks`, so
the pre-commit hook applies to this checkout and its worktrees. The hook needs
gitleaks 8.19 or newer. `git commit --no-verify` bypasses the hook; CI runs
`make secrets` as the enforceable gate.

Run a single test directly:

```sh
uv run pytest tests/test_core.py -k store
```

Layout:

- `src/dotfig/cli.py` -- click + rich commands, global options, and consoles
- `src/dotfig/core.py` -- store/restore/list state machine and path mapping
- `src/dotfig/config.py` -- platform config path and TOML load/save
- `src/dotfig/completions.py` -- static bash completion generator and installer
- `src/dotfig/diffview.py` -- configured diff viewer with `diff -u` fallback
- `tests/` -- pytest suite
- `docs/` -- Sphinx sources for the man page and the ADRs

## Contributing

Report bugs and request features at
[github.com/8cylinder/dotfig/issues](https://github.com/8cylinder/dotfig/issues).
Read [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, and
[SECURITY.md](SECURITY.md) to report a vulnerability privately. Release notes
are in [CHANGELOG.md](CHANGELOG.md). Run `make check` before opening a pull
request.

## License

dotfig is licensed under GPL-2.0-only. See [LICENSE](LICENSE).

Copyright (C) 2026 Sheldon McGrandle
