"""``CANOPY_MCP_TOKEN_FILE``: ``/mcp`` on a credential of its own, which opens nothing else.

With the access token alone, ``X-Canopy-Access`` opens every route, ``/mcp`` and
the PV-write relay alike, so an agent handed it could drive writes. The MCP
token splits them: requests under ``/mcp`` need the MCP credential and refuse
the access one, and every other route the reverse. The relay needs the split.

==============  ===========  ======================  ======================
access token    MCP token    ``/mcp`` opens with     other routes open with
==============  ===========  ======================  ======================
unset           unset        anything (proxy guard)  anything
set             unset        the access token        the access token
set             set          the MCP token           the access token
unset           set          the server does not start
==============  ===========  ======================  ======================
"""

from pathlib import Path
from collections.abc import Iterator

import httpx
import pytest
from starlette.testclient import TestClient, WebSocketDenialResponse

from canopy_mcp.app import HostGuard, ProxiedMcpGuard, create_app
from canopy_mcp.access import ACCESS_HEADER, AccessGate, CredentialFileError, under_mcp_path
from canopy_mcp.client import make_client
from canopy_mcp.config import Settings, get_settings
from tests.canopy_mcp.test_access_credential import (
    OPEN,
    REFUSAL,
    SOCKETS,
    INITIALIZE,
    ALL_METHODS,
    MCP_HEADERS,
    _run,
    _walk,
    _upstream,
)

TOKEN = "access-credential-7f3a"
MCP = "mcp-credential-91c2"
WRITE_KEY = "server-write-key"
BASE = "http://canopy-api:8000"
ACCESS = {ACCESS_HEADER: TOKEN}
AGENT = {ACCESS_HEADER: MCP}
PV_PUT = "/hare/v1/pvs/SIM:X"
SAME_ORIGIN = {"Sec-Fetch-Site": "same-origin", "content-type": "application/json"}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in (
        "CANOPY_ACCESS_TOKEN_FILE",
        "CANOPY_MCP_TOKEN_FILE",
        "CANOPY_PUT_RELAY",
        "CANOPY_WRITE_API_KEY_FILE",
        "CANOPY_API_KEY_FILE",
        "CANOPY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _secret(tmp_path: Path, name: str, value: str) -> Path:
    path = tmp_path / name
    path.write_text(value + "\n")
    return path


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    """A relay-on server behind both credentials; ``overrides`` take parts of it away."""
    drafts = tmp_path / "drafts"
    drafts.mkdir(exist_ok=True)
    fields: dict[str, object] = {
        "base_url": BASE,
        "api_key": "server-read-key",
        "drafts_dir": drafts,
        # The test client names its server "testserver" in Host, which the relays must accept.
        "self_url": "http://testserver",
        "access_token_file": _secret(tmp_path, "front.access", TOKEN),
        "mcp_token_file": _secret(tmp_path, "agent.mcp", MCP),
        "put_relay": True,
        "write_api_key_file": _secret(tmp_path, "front.write", WRITE_KEY),
    }
    fields.update(overrides)
    return Settings(**fields)


@pytest.fixture
def split_app(tmp_path: Path):
    return create_app(_settings(tmp_path), startup_hooks=[])


@pytest.fixture
def client(split_app) -> Iterator[TestClient]:
    with TestClient(split_app) as c:
        yield c


@pytest.fixture
def relayed(split_app) -> Iterator[tuple[TestClient, list[httpx.Request]]]:
    """The split app with its backend client swapped for one that records every upstream request."""
    upstream: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        upstream.append(request)
        return httpx.Response(200, json={"pv": "SIM:X", "outcome": "confirmed"})

    with TestClient(split_app) as c:
        split_app.state.http = make_client(split_app.state.settings, transport=httpx.MockTransport(answer))
        yield c, upstream


def _initialize(client: TestClient, headers: dict[str, str]) -> httpx.Response:
    return client.post("/mcp", json=INITIALIZE, headers={**MCP_HEADERS, **headers}, follow_redirects=False)


# --- The four states ---------------------------------------------------------------

STATES = {
    "neither": {"access_token_file": None, "mcp_token_file": None, "put_relay": False},
    "access only": {"mcp_token_file": None, "put_relay": False},
    "both": {"put_relay": False},
}
# For each state: which header opens /mcp and which opens a viewer route (None: no header).
OPENS = {
    "neither": ({None, "access", "mcp"}, {None, "access", "mcp"}),
    "access only": ({"access"}, {"access"}),
    "both": ({"mcp"}, {"access"}),
}
HEADERS = {None: {}, "access": ACCESS, "mcp": AGENT}


@pytest.mark.parametrize("state", list(STATES))
def test_each_state_opens_mcp_and_the_viewer_with_its_own_credential(tmp_path, state):
    app = create_app(_settings(tmp_path, **STATES[state]), startup_hooks=[])
    mcp_opens, viewer_opens = OPENS[state]
    with TestClient(app) as client:
        for name, headers in HEADERS.items():
            mcp = _initialize(client, headers)
            assert (mcp.status_code == 200) is (name in mcp_opens), (state, name, mcp.status_code)
            viewer = client.get("/config.json", headers=headers)
            assert (viewer.status_code == 200) is (name in viewer_opens), (state, name, viewer.status_code)


@pytest.mark.parametrize("state", list(STATES))
def test_each_state_keeps_its_guard(tmp_path, state):
    app = create_app(_settings(tmp_path, **STATES[state]), startup_hooks=[])
    guard = ProxiedMcpGuard if state == "neither" else AccessGate
    assert [m.cls for m in app.user_middleware][:2] == [HostGuard, guard]


def test_an_mcp_token_without_an_access_token_stops_the_server(tmp_path):
    with pytest.raises(ValueError, match="CANOPY_MCP_TOKEN_FILE is set but CANOPY_ACCESS_TOKEN_FILE is not"):
        _settings(tmp_path, access_token_file=None, put_relay=False)


# --- The setting -------------------------------------------------------------------


def test_no_mcp_token_is_asked_for_by_default():
    assert Settings().mcp_token_file is None


def test_the_mcp_token_file_is_read_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CANOPY_ACCESS_TOKEN_FILE", str(tmp_path / "front.access"))
    monkeypatch.setenv("CANOPY_MCP_TOKEN_FILE", str(tmp_path / "agent.mcp"))
    assert Settings().mcp_token_file == tmp_path / "agent.mcp"


def test_the_mcp_token_is_a_documented_setting():
    readme = (Path(__file__).resolve().parents[2] / "src" / "canopy_mcp" / "README.md").read_text(encoding="utf-8")
    assert "| `CANOPY_MCP_TOKEN_FILE` |" in readme


def test_an_empty_mcp_token_variable_counts_as_unset(monkeypatch):
    monkeypatch.setenv("CANOPY_MCP_TOKEN_FILE", "")
    assert Settings().mcp_token_file is None


def test_an_mcp_token_equal_to_the_access_token_stops_the_start(tmp_path):
    settings = _settings(tmp_path, mcp_token_file=_secret(tmp_path, "agent.same", TOKEN))
    with pytest.raises(CredentialFileError, match="CANOPY_MCP_TOKEN_FILE") as excinfo:
        create_app(settings, startup_hooks=[])
    assert "CANOPY_ACCESS_TOKEN_FILE" in str(excinfo.value)
    assert TOKEN not in str(excinfo.value)


def test_one_file_named_for_both_tokens_stops_the_start(tmp_path):
    shared = _secret(tmp_path, "shared", TOKEN)
    with pytest.raises(CredentialFileError, match="must differ"):
        create_app(_settings(tmp_path, access_token_file=shared, mcp_token_file=shared), startup_hooks=[])


def test_an_unreadable_mcp_token_file_stops_the_start(tmp_path):
    with pytest.raises(CredentialFileError, match="CANOPY_MCP_TOKEN_FILE"):
        create_app(_settings(tmp_path, mcp_token_file=tmp_path / "absent"), startup_hooks=[])


@pytest.mark.parametrize("problem", ["missing", "same as the access token"])
def test_the_launch_exits_non_zero_before_binding(tmp_path, problem):
    access = _secret(tmp_path, "front.access", TOKEN)
    mcp = tmp_path / "absent" if problem == "missing" else _secret(tmp_path, "agent.mcp", TOKEN)
    proc = _run(
        ["-m", "canopy_mcp", "--http", "--port", "0"],
        tmp_path,
        CANOPY_ACCESS_TOKEN_FILE=str(access),
        CANOPY_MCP_TOKEN_FILE=str(mcp),
    )
    assert proc.returncode != 0
    assert "CANOPY_MCP_TOKEN_FILE" in proc.stderr and str(mcp) in proc.stderr
    assert "Traceback" not in proc.stderr
    assert TOKEN not in proc.stderr + proc.stdout
    assert "Uvicorn running" not in proc.stderr + proc.stdout


def test_the_gate_cannot_be_built_with_one_credential_for_both():
    with pytest.raises(ValueError):
        AccessGate(lambda *a: None, token=TOKEN, mcp_token=TOKEN)
    with pytest.raises(ValueError):
        AccessGate(lambda *a: None, token=TOKEN, mcp_token="")


# --- Both tokens: /mcp ---------------------------------------------------------------


def test_mcp_answers_the_mcp_credential(client):
    r = _initialize(client, AGENT)
    assert r.status_code == 200
    assert "serverInfo" in r.text


@pytest.mark.parametrize("path", ["/mcp", "/mcp/", "/mcp/x"])
def test_the_access_credential_opens_nothing_under_mcp(client, path):
    for method in ALL_METHODS:
        r = client.request(method, path, json=INITIALIZE, headers={**MCP_HEADERS, **ACCESS}, follow_redirects=False)
        assert r.status_code == 401, (method, path)
        if method != "HEAD":
            assert r.json() == REFUSAL


def test_the_browser_through_the_proxy_cannot_reach_mcp(client):
    """The proxy adds the access credential to the browser's requests, which /mcp now refuses."""
    assert _initialize(client, {**ACCESS, "x-forwarded-prefix": "/panel/canopy"}).status_code == 401


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
def test_mcp_with_a_trailing_slash_is_still_never_the_transport(client, method):
    r = client.request(method, "/mcp/", json=INITIALIZE, headers={**MCP_HEADERS, **AGENT}, follow_redirects=False)
    assert r.status_code in (307, 308, 404)
    assert "serverInfo" not in r.text


def test_two_credential_headers_on_mcp_are_refused_even_when_one_is_right(client):
    headers = [*MCP_HEADERS.items(), (ACCESS_HEADER, MCP), (ACCESS_HEADER, TOKEN)]
    assert client.post("/mcp", json=INITIALIZE, headers=headers).status_code == 401


def test_a_path_that_only_starts_like_mcp_is_another_route(client):
    assert not under_mcp_path("/mcpx") and under_mcp_path("/mcp") and under_mcp_path("/mcp/x")
    assert client.get("/mcpx", headers=ACCESS).status_code == 404
    assert client.get("/mcpx", headers=AGENT).status_code == 401


# --- Both tokens: every other route --------------------------------------------------


def test_the_mcp_credential_opens_no_route_but_mcp(client, split_app):
    paths = {path for _, _, path in _walk(split_app)}
    assert {"/mcp", "/config.json", "/views", "/drafts/manifest.json"} <= paths
    answered = {}
    for path in sorted(paths):
        for method in ALL_METHODS:
            if under_mcp_path(path) or (method, path) == OPEN:
                continue
            r = client.request(method, path, headers=AGENT, follow_redirects=False)
            if r.status_code != 401 or (method != "HEAD" and r.json() != REFUSAL):
                answered[f"{method} {path}"] = r.status_code
    assert answered == {}


def test_the_access_credential_still_opens_every_other_route(client, split_app):
    refused = [
        f"{method} {path}"
        for kind, method, path in _walk(split_app)
        if kind == "http" and not under_mcp_path(path)
        if client.request(method, path, headers=ACCESS, follow_redirects=False).status_code == 401
    ]
    assert refused == []


def test_the_relay_refuses_the_mcp_credential_and_sends_nothing_upstream(relayed):
    client, upstream = relayed
    r = client.put(PV_PUT, content=b'{"value": 1}', headers={**SAME_ORIGIN, **AGENT})
    assert r.status_code == 401 and r.json() == REFUSAL
    assert upstream == []


def test_the_relay_still_takes_the_access_credential(relayed):
    client, upstream = relayed
    r = client.put(PV_PUT, content=b'{"value": 1}', headers={**SAME_ORIGIN, **ACCESS})
    assert r.status_code == 200
    [sent] = upstream
    assert sent.headers["x-api-key"] == WRITE_KEY
    assert ACCESS_HEADER.lower() not in sent.headers


@pytest.mark.parametrize("path", sorted(SOCKETS))
def test_a_websocket_refuses_the_mcp_credential(client, path):
    with pytest.raises(WebSocketDenialResponse) as excinfo:
        with client.websocket_connect(path, headers=AGENT):
            pass
    assert excinfo.value.status_code == 401


def test_a_websocket_still_takes_the_access_credential(tmp_path):
    with _upstream() as (base_url, _):
        app = create_app(_settings(tmp_path, base_url=base_url), startup_hooks=[])
        with TestClient(app) as c, c.websocket_connect("/hare/v1/ws/pvs", headers=ACCESS) as ws:
            assert ws.receive_text() == "welcome"


def test_each_request_makes_one_constant_time_comparison_against_its_routes_credential(monkeypatch, split_app):
    import canopy_mcp.access as access

    compared = []

    def spy(left, right):
        compared.append((left, right))
        return left == right

    monkeypatch.setattr(access.hmac, "compare_digest", spy)
    client = TestClient(split_app)
    assert client.get("/config.json", headers=AGENT).status_code == 401
    assert _initialize(client, ACCESS).status_code == 401
    assert compared == [(MCP.encode(), TOKEN.encode()), (TOKEN.encode(), MCP.encode())]


def test_the_screenshot_browser_carries_the_access_credential_not_the_mcp_one(tmp_path):
    from canopy_mcp.app import chromium_hook

    app = create_app(_settings(tmp_path), startup_hooks=[chromium_hook])
    with TestClient(app):
        assert app.state.browser.access_token == TOKEN
        assert not app.state.browser.running
