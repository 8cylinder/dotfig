# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `dotfig list` adds a `State` column when a host file is missing, a live or
  broken symlink, not a regular file, or different from the stored copy. Piped
  output gains a fifth field at the same time.

## [0.3.0] - 2026-11-23

### Added

- Global `--color [auto|always|never]` option, with consoles created after
  option parsing.
- Static bash completion generator in `dotfig/completions.py`, written to
  `dotfig.bash` under `BASH_COMPLETION_USER_DIR`, `XDG_DATA_HOME`, or
  `~/.local/share`.
- Sphinx man page built from `docs/cli.rst`, installed by `make install`.
- Git hook that blocks secrets with gitleaks, plus CI, CodeQL, and Dependabot
  configuration.
- Branch coverage gate at 90% and tests for completions, hooks, colors, and
  configuration.

### Changed

- `-h` works on every command through `AppCommand` and `AppGroup`.
- Help and man-page output no longer include internal exception documentation.
- Unknown config keys warn and are ignored; relative `root` values resolve
  against the config file's directory.
- Config files are written with mode `0600`.
- Development dependencies moved out of the runtime dependency list.

### Fixed

- Completions print only the script path on stdout; warnings and the `source`
  hint go to stderr.

## 0.2.0

Previous work: copy-based store/restore, list IDs, diff viewer integration, and
the platform config file.

[0.3.0]: https://github.com/8cylinder/dotfig/compare/v0.2.0...v0.3.0
