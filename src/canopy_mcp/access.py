"""The access credentials in front of every route, and the files secrets come from.

A deployment that runs this server behind a proxy hands it a credential in a
file (``CANOPY_ACCESS_TOKEN_FILE``). :class:`AccessGate` then requires that
value in the ``X-Canopy-Access`` header of every HTTP request and WebSocket
handshake, whatever the path or method -- the viewer, ``/views``, the drafts,
the forwards and ``/mcp`` alike. The one exception is ``GET /health``, which a
supervisor has to be able to probe before it holds anything.

A second file (``CANOPY_MCP_TOKEN_FILE``) splits the agent's endpoint off:
requests under :data:`MCP_PATH` then need that credential instead, the access
credential no longer opens them, and the MCP credential opens nothing else. An
agent handed only the MCP credential reaches the tools, but not the PV-write
relay or any other route the browser uses.

The gate sits outside routing, so a path that matches no route is refused like
any other rather than reported as missing, and a WebSocket is refused before
it is accepted. The header is the only carrier: a browser cannot set one on a
WebSocket handshake, so the credential is added by the proxy in front, never
by a page.

:func:`read_secret_file` is the strict reader behind every ``CANOPY_*_FILE``
variable. A deployment that names a file must never run on a secret other than
the one in it, so a file that cannot supply one stops the start.
"""

import hmac
from pathlib import Path

from starlette.types import Send, Scope, ASGIApp, Receive
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket

ACCESS_HEADER = "X-Canopy-Access"
OPEN_ROUTE = ("GET", "/health")
#: FastMCP's streamable-HTTP route, the agent's endpoint.
MCP_PATH = "/mcp"

REFUSAL_CODE = "invalid_access_credential"
REFUSAL_DETAIL = f"A valid {ACCESS_HEADER} credential is required"
WS_POLICY_VIOLATION = 1008

_HEADER_NAME = ACCESS_HEADER.lower().encode("latin-1")


class CredentialFileError(RuntimeError):
    """A configured secret file cannot supply a usable secret. Never carries file content."""


def read_secret_file(variable: str, path: str | Path) -> str:
    """The secret held by ``path``, the file named by the environment variable ``variable``.

    The file holds the secret alone; surrounding whitespace (the usual
    trailing line break) is dropped. A file that is missing, unreadable, not
    text, empty, or that holds anything but one printable ASCII token raises
    :class:`CredentialFileError`, which names the variable and the path.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else type(exc).__name__
        raise CredentialFileError(f"{variable} {path}: cannot be read ({reason})") from None
    secret = raw.strip()
    if not secret:
        raise CredentialFileError(f"{variable} {path}: holds no secret")
    # It travels as an HTTP header value, so it has to be one that can.
    if not secret.isascii() or not secret.isprintable() or any(char.isspace() for char in secret):
        raise CredentialFileError(f"{variable} {path}: is not a single printable ASCII token")
    return secret


def under_mcp_path(path: str) -> bool:
    """Whether ``path`` is :data:`MCP_PATH` or lies below it (``/mcp/...``, not ``/mcpx``)."""
    return path == MCP_PATH or path.startswith(MCP_PATH + "/")


class AccessGate:
    """Refuse every request that does not carry its route's credential, except ``GET /health``.

    ``token`` is the access credential. Without ``mcp_token`` it opens every
    route, :data:`MCP_PATH` included. With ``mcp_token``, a request under
    :data:`MCP_PATH` needs ``mcp_token`` and every other request needs
    ``token``: neither credential opens the other's routes.
    """

    def __init__(self, app: ASGIApp, token: str, mcp_token: str | None = None) -> None:
        if not token:
            raise ValueError("the access gate needs a credential to compare against")
        if mcp_token is not None and (not mcp_token or mcp_token == token):
            raise ValueError("the MCP credential must be set and differ from the access credential")
        self.app = app
        self._token = token.encode("latin-1")
        self._mcp_token = self._token if mcp_token is None else mcp_token.encode("latin-1")

    def _admits(self, scope: Scope) -> bool:
        expected = self._mcp_token if under_mcp_path(scope["path"]) else self._token
        supplied = [value for name, value in scope.get("headers", ()) if name.lower() == _HEADER_NAME]
        # Exactly one value: a second one would mean the proxy in front passed
        # a caller's own header along beside the one it adds.
        return len(supplied) == 1 and hmac.compare_digest(supplied[0], expected)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        is_open = scope["type"] == "http" and (scope["method"], scope["path"]) == OPEN_ROUTE
        if is_open or self._admits(scope):
            await self.app(scope, receive, send)
            return

        refusal = JSONResponse({"code": REFUSAL_CODE, "detail": REFUSAL_DETAIL}, status_code=401)
        if scope["type"] == "http":
            await refusal(scope, receive, send)
            return
        websocket = WebSocket(scope, receive, send)
        if "websocket.http.response" in scope.get("extensions", {}):
            await websocket.send_denial_response(refusal)
        else:
            # A server that cannot answer a handshake with an HTTP response.
            await websocket.close(code=WS_POLICY_VIOLATION, reason=f"{REFUSAL_CODE}: {REFUSAL_DETAIL}")
