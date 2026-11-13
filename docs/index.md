# canopy-mcp

canopy-mcp is the panel-builder MCP server for Canopy. It lets an agent build,
check and screenshot Canopy screens, convert legacy `.bob`, `.opi`, `.edl` and
`.ui` panels, and, when the operator allows it, show screens on the operator's
workspace. It talks to the canopy backend over HTTP and never writes a PV.

The same port serves the MCP endpoint (`/mcp`), the embedded viewer, the draft
screens, the saved views and, when enabled, the workspace routes.

The server's switches, tools and routes are described in the package README,
[`src/canopy_mcp/README.md`](https://github.com/slaclab/canopy-mcp/blob/main/src/canopy_mcp/README.md).
The how-to pages cover the panel-builder skill, the library report, asking for
a screen to be added to the shared library, and collections.
