"""The loopback GUI, driven against a REAL server on 127.0.0.1 with an ephemeral port.

No mock HTTP layer: the handler, the auth, the routing and the escaping are all
exercised over a real socket, because a fake would let a routing bug through.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
import pytest
from mcpctl.matrix import Liveness, Row, build_rows

from mcpapply import plan as P
from mcpapply.apply import ApplyResult, FileChange
from mcpapply.impact import Cost, Impact, Regime, TokenBasis, preview
from mcpapply.server import (
    _SAFE_ASSET,
    LOOPBACK_HOSTS,
    STATIC_DIR,
    GuiPorts,
    new_token,
    render_page,
    serve,
)
from conftest import PROJECT_KEY, topology_from

TOKEN = "test-token-not-a-secret"

#: A server name carrying markup, a quote, and a control byte -- everything a config
#: file can legally hold and a browser would happily execute.
HOSTILE = '<img src=x onerror="alert(1)">\x1b[31m&\x07'
SECRET_VALUE = "sk-" + "0" * 40


def _topology():
    return topology_from(
        {
            "claude_json": {
                "mcpServers": {
                    HOSTILE: {"command": "x", "env": {"TOKEN": SECRET_VALUE}},
                    "plain": {"command": "y"},
                },
                "projects": {PROJECT_KEY: {"disabledMcpServers": []}},
            }
        },
        project_key=PROJECT_KEY,
    )


def _rows() -> tuple[Row, ...]:
    return build_rows(
        _topology(), liveness={"plain": Liveness(tool_count=3), HOSTILE: Liveness()}
    )


def _plan_for(intent: str, server: str) -> P.Plan:
    top = _topology()
    if intent == "disable":
        return P.build_plan([P.plan_disable(top, server)], project_key=PROJECT_KEY)
    if intent == "enable":
        return P.build_plan([P.plan_enable(top, server)], project_key=PROJECT_KEY)
    raise ValueError(f"unknown intent {intent!r}")


class Recorder:
    """Records every apply call so a dry-run assertion can be made on the callee."""

    def __init__(self) -> None:
        self.calls: list[bool] = []

    def __call__(self, plan: P.Plan, confirmed: bool) -> ApplyResult:
        self.calls.append(confirmed)
        return ApplyResult(
            dry_run=not confirmed,
            file_changes=(
                FileChange(
                    label="claude_json",
                    path="~/.claude.json",
                    changed=True,
                    created=False,
                    diff="+ x",
                ),
            ),
            written=("~/.claude.json",) if confirmed else (),
        )


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def ports(recorder: Recorder) -> GuiPorts:
    costs = {
        "plain": Cost(token_cost=100, token_basis=TokenBasis.EXACT, commit_bytes=1024)
    }
    return GuiPorts(
        rows=_rows,
        plan_for=_plan_for,
        impact_for=lambda plan: preview(plan, costs, regime=Regime.DEFERRED),
        apply_plan=recorder,
        token=TOKEN,
    )


@pytest.fixture
def base(ports: GuiPorts) -> Iterator[str]:
    httpd: ThreadingHTTPServer = serve(ports)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[0], httpd.server_address[1]
    try:
        yield f"http://{host!s}:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _get(url: str, *, token: str | None = None, host: str | None = None):
    request = urllib.request.Request(url)  # noqa: S310 -- loopback literal.
    if token is not None:
        request.add_header("X-MCPApply-Token", token)
    if host is not None:
        request.add_header("Host", host)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8"), response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), exc.headers


def _post(
    url: str, body: object, *, token: str | None = TOKEN, raw: bytes | None = None
):
    payload = raw if raw is not None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")  # noqa: S310
    request.add_header("Content-Type", "application/json")
    if token is not None:
        request.add_header("X-MCPApply-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


# --------------------------------------------------------------------------
# Binding
# --------------------------------------------------------------------------


def test_it_binds_loopback_on_an_ephemeral_port(base: str):
    host, port = base.removeprefix("http://").rsplit(":", 1)
    assert host in LOOPBACK_HOSTS
    assert int(port) > 0


def test_it_refuses_to_bind_a_routable_interface(ports: GuiPorts):
    with pytest.raises(ValueError, match="loopback-only"):
        serve(ports, host="0.0.0.0")  # noqa: S104 -- the point is that it is refused.


def test_a_non_loopback_host_header_is_rejected_dns_rebinding(base: str):
    """The loopback bind alone does not stop a rebound DNS name reaching this port."""
    status, body, _ = _get(f"{base}/", host="evil.example.com")
    assert status == 403
    assert "non-loopback" in body
    assert _post(f"{base}/api/plan", {}, token=TOKEN)[0] in (400, 403)
    request = urllib.request.Request(  # noqa: S310
        f"{base}/api/plan", data=b"{}", method="POST"
    )
    request.add_header("Host", "evil.example.com")
    try:
        urllib.request.urlopen(request, timeout=10)  # noqa: S310
    except urllib.error.HTTPError as exc:
        assert exc.code == 403


# --------------------------------------------------------------------------
# Escaping and credential containment
# --------------------------------------------------------------------------


def test_a_hostile_server_name_cannot_inject_html_or_js(base: str):
    status, body, headers = _get(f"{base}/")
    assert status == 200
    assert (
        headers["Content-Security-Policy"]
        == "default-src 'self'; frame-ancestors 'none'"
    )
    # No live tag and no attribute-breaking quote survives; the escaped form does.
    assert "<img" not in body
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in body
    # Control bytes never reach the response at all.
    assert "\x1b" not in body
    assert "\x07" not in body
    # ...and the raw ampersand is entity-encoded, not passed through.
    assert "&amp;" in body


def test_no_credential_value_reaches_the_html_or_the_json(base: str):
    _, page, _ = _get(f"{base}/")
    _, payload, _ = _get(f"{base}/api/matrix", token=TOKEN)
    assert SECRET_VALUE not in page
    assert SECRET_VALUE not in payload
    # The NAME and the classification are there -- that is the whole point.
    assert "TOKEN=present" in page
    assert '"name": "TOKEN"' in payload
    assert '"kind": "present"' in payload


def test_the_page_renders_an_unmeasured_tool_count_as_a_dash_not_zero(base: str):
    _, page, _ = _get(f"{base}/")
    row = re.search(r"<tr>.*?onerror.*?</tr>", page, re.S)
    assert row is not None
    assert "<td>-</td>" in row.group(0)


_HTML_SINKS = (
    "innerHTML",
    "outerHTML",
    "insertAdjacentHTML",
    "document.write",
    "eval(",
)
_NETWORK = ("//cdn", "https:" + "//", "@import", "http:" + "//")


def _strip_comments(source: str) -> str:
    """Drop // line and /* block */ comments.

    USE-VS-MENTION: the assets DOCUMENT the very sinks the scan bans, so a raw
    substring scan fires on the prose that promises they are absent. This is a
    recorded defect class in this repo; parse the code, not the document.
    """
    without_block = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    lines = [re.sub(r"//.*$", "", line) for line in without_block.splitlines()]
    return "\n".join(lines)


def test_the_comment_stripper_can_still_see_a_real_sink():
    """Detector control: prove the probe fires before trusting its silence."""
    assert "innerHTML" in _strip_comments("var a = 1;\nx.innerHTML = y;")
    assert "innerHTML" not in _strip_comments("// never use innerHTML here")
    assert "@import" not in _strip_comments("/* no @import */\nbody { color: red }")


def test_the_static_js_never_assigns_html():
    """Mechanical assertion over the SHIPPED asset, not over a docstring."""
    code = _strip_comments((STATIC_DIR / "app.js").read_text(encoding="utf-8"))
    for sink in _HTML_SINKS:
        assert sink not in code, f"{sink} must not appear in the GUI asset"
    assert "textContent" in code


def test_the_static_assets_fetch_nothing_off_the_loopback():
    for name in ("app.js", "app.css"):
        code = _strip_comments((STATIC_DIR / name).read_text(encoding="utf-8"))
        for marker in _NETWORK:
            assert marker not in code, f"{name} must not reference {marker}"


def test_an_empty_row_set_renders_a_valid_page():
    page = render_page((), "tok")
    assert "<tbody></tbody>" in page


def test_a_row_with_no_env_renders_a_dash(base: str):
    _, page, _ = _get(f"{base}/")
    row = re.search(r"<tr><td>plain</td>.*?</tr>", page, re.S)
    assert row is not None
    assert row.group(0).endswith("<td>-</td></tr>")


def test_an_inferred_state_is_marked_so_a_judgement_is_not_read_as_a_reading():
    rows = build_rows(
        topology_from(
            {
                "claude_json": {
                    "mcpServers": {"m": {"command": "x"}},
                    "disabledMcpServers": ["m"],
                    "projects": {PROJECT_KEY: {"disabledMcpServers": ["m"]}},
                }
            },
            project_key=PROJECT_KEY,
        ),
        liveness={},
    )
    assert "disabled~" in render_page(rows, "t")


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


def test_every_api_route_needs_the_token_including_the_read(base: str):
    assert _get(f"{base}/api/matrix")[0] == 401
    assert _get(f"{base}/api/matrix", token="wrong")[0] == 401
    assert _get(f"{base}/api/matrix", token=TOKEN)[0] == 200
    assert (
        _post(f"{base}/api/plan", {"intent": "disable", "server": "plain"}, token=None)[
            0
        ]
        == 401
    )


def test_the_index_page_carries_the_token_for_the_static_js(base: str):
    _, page, _ = _get(f"{base}/")
    assert f'data-token="{TOKEN}"' in page


def test_a_fresh_token_is_unguessable_and_not_reused():
    first, second = new_token(), new_token()
    assert first != second
    assert len(first) >= 32


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


def test_unknown_routes_are_404(base: str):
    assert _get(f"{base}/nope")[0] == 404
    assert _post(f"{base}/api/nope", {}, token=TOKEN)[0] == 404


def test_static_assets_are_served_with_their_media_type(base: str):
    for name, media in (("app.js", "text/javascript"), ("app.css", "text/css")):
        status, body, headers = _get(f"{base}/static/{name}")
        assert status == 200
        assert media in headers["Content-Type"]
        assert body


def test_a_traversal_or_unknown_asset_is_404(base: str):
    for name in ("../pyproject.toml", "nope.js", "app.py", "sub/dir.js"):
        assert _get(f"{base}/static/{name}")[0] == 404


# A UNC spelling must be refused by the NAME allowlist, before the filesystem is touched.
#
# MEASURED regression: `(STATIC_DIR / "//host/share/x.js").resolve()` on Windows yields the UNC
# path \\host\share\x.js -- a UNC root DISCARDS the base -- and `resolve()` then hands it to
# the SMB redirector. Observed: a real outbound SYN to port 445 on an attacker-named host
# (RFC 5737 TEST-NET-1 used as a never-routed control) from this UNAUTHENTICATED route, plus a
# handler thread pinned for the SMB timeout (30s+). Containment checked AFTER resolving is too
# late, because `resolve()` is itself the dangerous call.
_UNC_SPELLINGS = (
    "//192.0.2.77/nope/x.js",
    "//host/share/x.js",
    "\\\\host\\share\\x.js",
    "///host/share/x.js",
)


@pytest.mark.parametrize("name", _UNC_SPELLINGS)
def test_a_unc_asset_name_is_refused_by_the_charset_before_any_filesystem_call(
    name: str,
):
    """The guard is a pure predicate, so it cannot dial anything. Pinned directly."""
    assert _SAFE_ASSET.fullmatch(name) is None


def test_the_asset_charset_still_admits_the_real_assets():
    """Control: the allowlist must not be so tight that it breaks the GUI's own files."""
    for good in ("app.js", "app.css"):
        assert _SAFE_ASSET.fullmatch(good) is not None


def test_a_unc_asset_request_is_404_and_returns_promptly(base: str):
    """End to end over the real socket: 404, and fast enough to prove no SMB dial happened.

    A dial to an unroutable host blocks for the SMB timeout (measured 13s-30s+ pre-fix), so a
    sub-second response is itself evidence the filesystem was never reached. The threshold is
    deliberately loose (5s) -- it only has to separate "guarded" from "dialled".
    """
    for name in _UNC_SPELLINGS:
        started = time.monotonic()
        assert _get(f"{base}/static/{name}")[0] == 404
        assert time.monotonic() - started < 5.0


# --------------------------------------------------------------------------
# Plan preview
# --------------------------------------------------------------------------


def test_the_plan_route_previews_and_never_applies(base: str, recorder: Recorder):
    status, body = _post(f"{base}/api/plan", {"intent": "disable", "server": "plain"})
    assert status == 200
    payload = json.loads(body)
    assert payload["plan"]["changes"][0]["intent"] == "disable"
    assert payload["impact"]["token_delta"] == 100
    assert recorder.calls == []


def test_a_bad_body_is_rejected_with_a_reason(base: str):
    assert _post(f"{base}/api/plan", None, raw=b"not json")[0] == 400
    assert _post(f"{base}/api/plan", [1, 2])[0] == 400
    assert _post(f"{base}/api/plan", {})[0] == 400
    assert _post(f"{base}/api/plan", {"intent": "disable"})[0] == 400
    assert _post(f"{base}/api/plan", None, raw=b"")[0] == 400
    assert _post(f"{base}/api/plan", None, raw=b"\xff\xfe")[0] == 400


def test_an_oversized_body_is_drained_then_rejected(base: str):
    """Drained, not just refused: an undrained body tears the socket down before the
    400 arrives, so the caller sees a reset instead of the reason."""
    assert _post(f"{base}/api/plan", None, raw=b"{}" + b" " * 70_000)[0] == 400


def test_a_body_too_large_to_drain_is_refused_without_reading_it(base: str):
    import http.client

    host, port = base.removeprefix("http://").rsplit(":", 1)
    conn = http.client.HTTPConnection(host, int(port), timeout=10)
    conn.putrequest("POST", "/api/plan", skip_accept_encoding=True)
    conn.putheader("X-MCPApply-Token", TOKEN)
    conn.putheader("Content-Length", str(2_000_000))
    conn.endheaders()
    conn.send(b"{}")
    assert conn.getresponse().status == 400
    conn.close()


def test_an_unknown_intent_is_a_400_not_a_500(base: str):
    status, body = _post(f"{base}/api/plan", {"intent": "nope", "server": "plain"})
    assert status == 400
    assert "unknown intent" in body


# --------------------------------------------------------------------------
# Apply -- the explicit confirm
# --------------------------------------------------------------------------


def test_apply_without_the_literal_confirm_previews_and_refuses(
    base: str, recorder: Recorder
):
    status, body = _post(f"{base}/api/apply", {"intent": "disable", "server": "plain"})
    payload = json.loads(body)
    assert status == 200
    assert payload["confirmed"] is False
    assert "apply refused" in payload["error"]
    assert payload["result"]["dry_run"] is True
    assert payload["result"]["written"] == []
    assert recorder.calls == [False]


def test_a_wrong_confirm_value_is_still_a_refusal(base: str, recorder: Recorder):
    _post(
        f"{base}/api/apply", {"intent": "disable", "server": "plain", "confirm": "yes"}
    )
    assert recorder.calls == [False]


def test_the_literal_confirm_authorises_the_write(base: str, recorder: Recorder):
    status, body = _post(
        f"{base}/api/apply",
        {"intent": "disable", "server": "plain", "confirm": "APPLY"},
    )
    payload = json.loads(body)
    assert status == 200
    assert payload["confirmed"] is True
    assert "error" not in payload
    assert payload["result"]["written"] == ["~/.claude.json"]
    assert recorder.calls == [True]


def test_the_access_log_is_silenced_so_a_raw_request_line_is_never_echoed(
    base: str, capsys: pytest.CaptureFixture[str]
):
    _get(f"{base}/")
    assert "GET" not in capsys.readouterr().err


def test_the_impact_payload_keeps_not_measured_as_null_over_the_wire(base: str):
    _, body = _post(f"{base}/api/plan", {"intent": "disable", "server": HOSTILE})
    payload = json.loads(body)
    assert payload["impact"]["token_delta"] is None
    assert payload["impact"]["commit_delta"] is None
    assert payload["impact"]["partial"] is True


def test_the_row_projection_reaches_the_json_unchanged(base: str):
    _, body, _ = _get(f"{base}/api/matrix", token=TOKEN)
    names = {row["name"] for row in json.loads(body)["rows"]}
    assert "plain" in names
    assert all("\x1b" not in n for n in names)


def test_ports_is_a_plain_value_object(ports: GuiPorts):
    assert ports.token == TOKEN
    assert callable(ports.rows)


def test_the_static_dir_ships_inside_the_package():
    assert STATIC_DIR.is_dir()
    assert (STATIC_DIR / "app.js").is_file()
    assert STATIC_DIR.parent.name == "mcpapply"


def test_impact_and_apply_result_shapes_are_json_serialisable():
    assert json.dumps(Impact(regime=Regime.EAGER).to_dict())
    assert json.dumps(ApplyResult(dry_run=True).to_dict())


def test_a_non_numeric_content_length_is_rejected_not_crashed(base: str):
    """urllib always sends a valid header, so this needs a raw client."""
    import http.client

    host, port = base.removeprefix("http://").rsplit(":", 1)
    conn = http.client.HTTPConnection(host, int(port), timeout=10)
    conn.putrequest("POST", "/api/plan", skip_accept_encoding=True)
    conn.putheader("X-MCPApply-Token", TOKEN)
    conn.putheader("Content-Length", "not-a-number")
    conn.endheaders()
    conn.send(b"{}")
    response = conn.getresponse()
    assert response.status == 400
    assert b"JSON object body" in response.read()
    conn.close()
