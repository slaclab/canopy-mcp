# Contributing

## Local Setup

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and a
POSIX system (Linux or macOS): the draft store locks files with `fcntl`.

```bash
git clone https://github.com/slaclab/canopy-mcp
cd canopy-mcp
./scripts/setup_dev.sh
uv run playwright install chromium
```

`setup_dev.sh` installs the dev dependencies and sets up the pre-commit hooks.
The last command installs the Chromium the `screenshot` tool and the browser
tests use; on Linux, add `--with-deps` for its system libraries.

## Running Tests

```bash
uv run pytest tests/ -v -m "not perf"
uv run lint-imports
```

The `perf` tests assert timing bounds for operator-class hardware and are left
out on shared runners. The `live` tests need a running canopy stack and run
only with `CANOPY_LIVE=1`. `lint-imports` checks the import contracts in
`pyproject.toml`.

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting, import
ordering and formatting. The pre-commit hooks run it on every commit. To run
the hooks on everything by hand:

```bash
uv run pre-commit run --all-files
```

## Building Docs

```bash
uv run zensical serve
```

## Submitting Changes

1. Create a branch off `main` using the format `<username>/<description>` or `<username>/#<issue-number>-<description>`:
   ```
   zdomke/my-changes
   yektay/#10-bug-fix
   ```
2. Make your changes and ensure tests pass
3. Open a pull request using the provided template

### From a fork

If you don't have write access to this repository, fork it, clone your fork and
follow the setup above. Branch off `main` in your fork; the branch name format
above is only a convention for people who push here, so any descriptive name
works. Open the pull request against `slaclab/canopy-mcp:main`.

- For anything larger than a small fix, open an issue first so we can agree on
  the approach before you spend time on it.
- A maintainer has to approve the GitHub Actions run on a pull request from a
  fork before it starts.
- Pull requests need an approving review before they can be merged.

## Reporting Security Issues

Don't report vulnerabilities in public issues or pull requests. See
[SECURITY.md](SECURITY.md).

## License

canopy-mcp is distributed under the terms in [LICENSE.md](LICENSE.md). By
contributing, you accept that the last paragraph of that file, which licenses
enhancements that you make available, applies to your contribution.
