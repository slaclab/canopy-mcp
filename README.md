# canopy-mcp

The panel-builder MCP server for [Canopy](https://github.com/slaclab/canopy).
It lets an agent build, check and screenshot Canopy screens, convert legacy
`.bob`, `.opi`, `.edl` and `.ui` panels into drafts, file a draft for the
shared screen library, and, when the operator turns it on, show screens on the
operator's workspace. It talks to the canopy backend over HTTP, and no tool
writes a PV.

## Install

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and
Linux or macOS.

```bash
git clone https://github.com/slaclab/canopy-mcp
cd canopy-mcp
uv sync
uv run playwright install chromium
```

Chromium is needed only for the `screenshot` tool; on Linux, add `--with-deps`
for its system libraries. canopy-mcp depends on canopy from git, pinned in
`pyproject.toml`. Until PyDMConverter 1.1.0 is on PyPI, uv takes it from git
too (see `[tool.uv]` in `pyproject.toml`), so install with uv.

## Run

```bash
CANOPY_BASE_URL=http://127.0.0.1:8000 \
CANOPY_VIEWER_DIST=/path/to/viewer/dist \
uv run python -m canopy_mcp --http --host 127.0.0.1 --port 8765
```

The MCP endpoint is `http://127.0.0.1:8765/mcp`. The same port serves the
embedded viewer, the draft screens and the saved views. Every setting, tool
and route is described in [`src/canopy_mcp/README.md`](src/canopy_mcp/README.md);
read *Single-user host or access token* there before serving it to other users.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests and code style, and
[SECURITY.md](SECURITY.md) to report a vulnerability.

The documentation is built with `uv run zensical serve`.

## License

See [LICENSE.md](LICENSE.md).
