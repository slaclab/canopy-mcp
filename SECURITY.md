# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately. Don't open a public issue,
pull request or discussion for them.

Use GitHub's private vulnerability reporting: open the repository's
[Security tab](https://github.com/slaclab/canopy-mcp/security) and choose
**Report a vulnerability**. Only the maintainers can see the report.

A useful report says:

- which commit you ran;
- which settings were on (`CANOPY_ACCESS_TOKEN_FILE`, `CANOPY_PUT_RELAY`,
  `CANOPY_WORKSPACE`, `CANOPY_AUTHORING`, the proxy settings);
- the steps to reproduce it and what you expected to happen;
- the impact as you understand it.

The maintainers will acknowledge the report, work with you on a fix and agree a
disclosure date with you. Tell us if you want to be credited.

## Supported versions

canopy-mcp is pre-1.0 and under active development. Security fixes are made on
`main`; they are not backported to older commits. Run a current commit.

## Notes for operators

- No MCP tool writes a PV. The viewer the server hosts can write one only with
  `CANOPY_PUT_RELAY=1`, which relays the single write route to the canopy
  backend and refuses to start without both an access token
  (`CANOPY_ACCESS_TOKEN_FILE`) and a write-scope key file
  (`CANOPY_WRITE_API_KEY_FILE`).
- Without an access token nothing is authenticated. `/mcp` only refuses
  requests that came through the embedding host's proxy, so any process that
  can reach the port can call every tool, and the saved views, collections and
  workspace routes guard their writes only by `Sec-Fetch-Site`. Run such a
  server on a single-user host, bound to loopback (the default). On a host
  other users can reach, set `CANOPY_ACCESS_TOKEN_FILE`.
- The `convert_legacy` tool reads any file the server's user can read: it posts
  the file to the converter at `CANOPY_BASE_URL` and copies image files found
  beside it into the drafts store. Run the server as a user whose readable
  files may be shown to the agent, or set `CANOPY_AUTHORING=0`, which takes
  `convert_legacy` and the other authoring tools off the server.
- Give the server a read-scope key for the backend, and prefer the `_FILE`
  settings to passing keys in the environment.
- `CANOPY_WORKSPACE=1` lets an agent change what is on the operator's screen.
  Use it only for one server process serving one operator.
- The screenshot Chromium renders agent-written pages. It runs without its own
  sandbox unless `CANOPY_BROWSER_SANDBOX=1`, because the sandbox needs user
  namespaces a container usually lacks; set it where the host allows. Either
  way each page is locked to this server's origin: a request to any other
  origin is aborted, only GET, HEAD and OPTIONS requests go through, and
  same-origin WebSockets are relayed through the server.
- Report a vulnerability in a dependency, canopy included, to that project.
  Tell us too if canopy-mcp's usage of it makes the impact worse.
