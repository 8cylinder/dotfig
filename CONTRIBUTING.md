# Contributing

Report bugs and request features in the
[issue tracker](https://github.com/8cylinder/dotfig/issues).

## Development setup

```sh
git clone https://github.com/8cylinder/dotfig.git
cd dotfig
make sync
make hooks
```

`make hooks` installs the pre-commit hook that blocks secrets. Run it once per
clone. The hook needs gitleaks 8.19 or newer; `git commit --no-verify` bypasses
it, but CI runs the same scan.

## Checks

```sh
make fmt
make lint
make check
```

`make check` runs the format check, lint, type check, tests with branch
coverage, and the man-page build. It must pass before a pull request. Do not add
rich-click or a module-level console; follow the patterns in `AGENTS.md`.

## Tests

Add tests for new behavior and keep branch coverage at or above 90%. Use
`tmp_path` and `monkeypatch` for filesystem tests; never write to the real home
directory or user config directory.

```sh
uv run pytest tests/test_core.py -k store
```
