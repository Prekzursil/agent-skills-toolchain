"""Locks on defects found by adversarial review. Each test FAILS on the pre-fix code.

Every test here names the exact defect it prevents and how it presented, because a
regression test whose reason has been forgotten is the first one deleted when it becomes
inconvenient. Grouped by the review lens that found them.

Nothing here touches the operator's real configuration: every document is synthesised
under ``tmp_path`` and every seam (clock, store, process listing, control channel) is
injected.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from mcpctl.matrix import Row
from mcpctl.scopes import ScopeId
from mcpctl.sources import SourcePaths

from mcpapply import server as gui
from mcpapply.apply import ApplyResult, MemoryFileStore
from mcpapply.cli import main
from mcpapply.impact import Cost, Impact, Regime, TokenBasis, preview, render_impact
from mcpapply.live import LiveOp, Proof, run_live
from mcpapply.plan import build_plan, plan_disable
from conftest import FIXED_NOW, PROJECT_KEY, topology_from, write_home

QUIET = '"explorer.exe","4","Console","1","1 K"\n'


def _quiet(argv: Sequence[str]) -> str:
    assert argv
    return QUIET


class Sink:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _gui_ports(home: Path, **kwargs: object) -> gui.GuiPorts:
    """Launch the GUI wiring and hand back the ports, without serving."""
    captured: list[gui.GuiPorts] = []
    main(
        ["gui", "--home", str(home), "--project", PROJECT_KEY],
        runner=_quiet,
        write=Sink(),
        serve_fn=lambda p, _n: (captured.append(p), 0)[1],
        **kwargs,  # type: ignore[arg-type]
    )
    return captured[0]


# --------------------------------------------------------------------------
# LENS: destructive safety -- the shell around the writer
# --------------------------------------------------------------------------


def test_a_long_lived_gui_takes_a_DISTINCT_backup_for_every_apply(
    home: Path, paths: SourcePaths
):
    """Two applies in ONE process must leave TWO recoverable sidecars.

    Regression: ``main`` captured one ``datetime`` and handed that same instant to
    every apply, so ``backup_path`` derived ONE filename for the whole GUI session.
    After two applies exactly one .bak existed and it held POST-apply-#1 state, so
    apply #1 restore command silently restored the wrong content and the operator
    could only ever roll back one step.
    """
    ports = _gui_ports(home)

    first = ports.apply_plan(ports.plan_for("disable", "cloud-hub"), True)
    pristine = Path(first.backups[0].backup).read_text("utf-8")
    second = ports.apply_plan(ports.plan_for("disable", "basic-memory"), True)

    assert first.backups[0].backup != second.backups[0].backup, (
        "both applies derived the SAME sidecar name; the second clobbered the first"
    )
    assert len(sorted(home.glob(".claude.json.mcpapply-*.bak"))) == 2
    # The file apply #1 told the operator to restore from still holds pre-#1 content.
    assert Path(first.backups[0].backup).read_text("utf-8") == pristine
    row = json.loads(pristine)["projects"][PROJECT_KEY]["disabledMcpServers"]
    assert "cloud-hub" not in row


def test_the_gui_re_reads_the_config_so_it_can_undo_its_own_change(home: Path):
    """The GUI must plan against DISK, not a snapshot captured at launch.

    Regression: after the GUI disabled a server it could not re-enable it. It planned
    against a world where the disable had never happened, emitted "no scope suppresses
    this server; nothing to write", and went on rendering the server as enabled.
    """
    ports = _gui_ports(home)
    assert {r.name: r.state for r in ports.rows()}["cloud-hub"] != "disabled"

    ports.apply_plan(ports.plan_for("disable", "cloud-hub"), True)
    assert {r.name: r.state for r in ports.rows()}["cloud-hub"] == "disabled"

    undo = ports.apply_plan(ports.plan_for("enable", "cloud-hub"), True)
    assert undo.written, "planned against stale docs and wrote nothing"
    assert {r.name: r.state for r in ports.rows()}["cloud-hub"] != "disabled"


def test_the_gui_surfaces_a_scope_that_became_unreadable_while_it_was_open(home: Path):
    ports = _gui_ports(home)
    assert ports.problems() == ()
    (home / ".mcp.json").write_text("{ not json", encoding="utf-8")
    assert any("mcp_json" in problem for problem in ports.problems())


def test_a_windows_shaped_project_path_lands_in_the_row_the_host_reads(tmp_path: Path):
    """A native path and a forward-slash path must target the SAME row.

    Regression: the raw ``--project`` value was passed straight through, ``_navigate``
    minted a brand-new ``projects[]`` row nobody reads, the requested disable did not
    land, and the terminal line still said SUCCESS. The junk row accumulated on every
    repeat.
    """
    forward = PROJECT_KEY
    native = forward.replace("/", "\\")
    write_home(tmp_path)
    code = main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(tmp_path),
            "--project",
            native,
            "--apply",
        ],
        now=FIXED_NOW,
        runner=_quiet,
        write=Sink(),
    )
    doc = json.loads((tmp_path / ".claude.json").read_text("utf-8"))
    assert code == 0
    assert native not in doc["projects"], "a phantom projects[] row was created"
    assert "cloud-hub" in doc["projects"][forward]["disabledMcpServers"]
    assert doc["projects"][forward]["history"] == [{"display": "keep this too"}]


def test_a_refusal_that_wrote_NOTHING_is_reported_as_FAILED_not_SUCCESS(
    home: Path, paths: SourcePaths
):
    """A shell one-liner chained on success must not treat a refusal as a landing.

    Regression: ``_classify`` mapped any problem to a warning and a warning renders as
    ``SUCCESS:`` with exit 0 -- including the stale-write refusal, which is the entire
    justification for the deliberate no-lock design.
    """

    class StaleStore(MemoryFileStore):
        """Moves the target between the preview read and the pre-write re-read."""

        def __init__(self, files: dict[str, str]) -> None:
            super().__init__(files)
            self.reads = 0

        def read_text(self, path: Path) -> str:
            text = super().read_text(path)
            if str(path) != str(paths.claude_json):
                return text
            self.reads += 1
            if self.reads != 2:
                return text
            doc = json.loads(text)
            doc["disabledMcpServers"] = ["someone-else"]
            moved = json.dumps(doc, indent=2) + "\n"
            self.files[str(path)] = moved
            return moved

    store = StaleStore({str(p): p.read_text("utf-8") for _, p in paths.as_tuple()})
    sink = Sink()
    code = main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--project",
            PROJECT_KEY,
            "--apply",
        ],
        now=FIXED_NOW,
        store=store,
        runner=_quiet,
        write=sink,
    )
    assert "changed on disk between the preview and the write" in sink.text
    assert code == 1
    assert "FAILED:mcpapply-disable" in sink.text
    assert "SUCCESS" not in sink.text
    assert "NOTHING was written" in sink.text


def test_a_partial_write_is_still_a_warning_not_a_failure(home: Path):
    """A problem on one scope while ANOTHER scope did land stays a SUCCESS/warning.

    ``markitdown`` is suppressed in BOTH settings-denied and the root list, so an
    enable targets two files; the settings write is refused as unparseable while the
    claude_json write lands. Nothing-written is a failure, but something-written with
    a caveat is exactly what a warning is for.
    """
    claude = json.loads((home / ".claude.json").read_text("utf-8"))
    claude["disabledMcpServers"] = ["ghidra-mcp", "markitdown"]
    paths = write_home(home, claude_json=claude)
    store = MemoryFileStore({str(p): p.read_text("utf-8") for _, p in paths.as_tuple()})
    store.files[str(paths.settings)] = "{ not json"
    sink = Sink()
    code = main(
        [
            "enable",
            "markitdown",
            "--home",
            str(home),
            "--project",
            PROJECT_KEY,
            "--apply",
        ],
        now=FIXED_NOW,
        store=store,
        runner=_quiet,
        write=sink,
    )
    assert "unparseable JSON" in sink.text
    assert store.writes == [str(paths.claude_json)]
    assert code == 0
    assert "SUCCESS:mcpapply-enable" in sink.text


def test_a_non_finite_number_is_REFUSED_not_written_as_the_token_Infinity(
    home: Path, paths: SourcePaths
):
    """``json.dumps`` would emit bare ``Infinity``, which ``JSON.parse`` rejects.

    The host reads these files with a real JSON parser, so writing a token Python
    accepts and JavaScript does not would turn a merely-odd config into one the host
    cannot load at all.
    """
    doc = json.loads(paths.claude_json.read_text("utf-8"))
    doc["someOverflowingNumber"] = 1e400  # round-trips to the token `Infinity`
    raw = json.dumps(doc, indent=2) + "\n"
    store = MemoryFileStore({str(p): p.read_text("utf-8") for _, p in paths.as_tuple()})
    store.files[str(paths.claude_json)] = raw

    sink = Sink()
    code = main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--project",
            PROJECT_KEY,
            "--apply",
        ],
        now=FIXED_NOW,
        store=store,
        runner=_quiet,
        write=sink,
    )
    assert "non-finite number" in sink.text
    # The refusal is total: the target is left byte-for-byte as it was found.
    assert store.writes == []
    assert store.files[str(paths.claude_json)] == raw
    assert code == 1
    # Detector control: the same run WITHOUT the overflow does write.
    clean = MemoryFileStore({str(p): p.read_text("utf-8") for _, p in paths.as_tuple()})
    main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--project",
            PROJECT_KEY,
            "--apply",
        ],
        now=FIXED_NOW,
        store=clean,
        runner=_quiet,
        write=Sink(),
    )
    assert clean.writes == [str(paths.claude_json)]


# --------------------------------------------------------------------------
# LENS: destructive safety -- the live channel is WIRED, not decorative
# --------------------------------------------------------------------------


class _FakeClient:
    """Stands in for a real control session. Records every frame."""

    def __init__(self, servers: tuple[str, ...] = ("cloud-hub",)) -> None:
        self.sent: list[str] = ["kick"]
        self.calls: list[tuple[str, object]] = []
        self._servers = servers

    def reconnect(self, name: str) -> None:
        self.calls.append(("reconnect", name))
        self.sent.append(f"reconnect:{name}")

    def toggle(self, name: str, *, enabled: bool) -> None:
        self.calls.append(("toggle", enabled))
        self.sent.append(f"toggle:{name}:{enabled}")

    def status(self) -> tuple[dict[str, object], ...]:
        self.sent.append("status")
        return tuple({"name": n} for n in self._servers)


def test_reconnect_without_live_refuses_instead_of_reporting_a_hollow_success(
    home: Path, paths: SourcePaths
):
    """Regression: an inert verb that printed SUCCESS while doing nothing at all.

    ``plan_reconnect`` emits a LIVE_ONLY edit which the writer filters out, and no
    production path ever built a control client -- so the command wrote no config
    (correct: it has none) and sent no frame either, then exited 0 with
    ``SUCCESS:mcpapply-reconnect 0 file(s) written``.
    """
    before = paths.claude_json.read_bytes()
    sink = Sink()
    code = main(
        ["reconnect", "cloud-hub", "--home", str(home), "--apply"],
        now=FIXED_NOW,
        runner=_quiet,
        write=sink,
    )
    assert code == 1
    assert paths.claude_json.read_bytes() == before
    assert "FAILED:mcpapply-reconnect" in sink.text
    assert "needs --live" in sink.text


def test_the_live_path_is_reachable_from_the_cli_and_actually_sends_frames(home: Path):
    """``mcpapply disable X --live --apply`` drives the control channel for real."""
    client = _FakeClient()
    sink = Sink()
    code = main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--live",
            "--apply",
            "--live-cwd",
            str(home),
        ],
        now=FIXED_NOW,
        runner=_quiet,
        client_for=lambda _cwd: client,  # type: ignore[arg-type]
        write=sink,
    )
    assert code == 0
    assert client.calls == [("toggle", False)]
    assert client.sent == ["kick", "toggle:cloud-hub:False", "status"]
    assert "control frame(s) sent" in sink.text
    assert "observed after the change: cloud-hub" in sink.text
    assert "SUCCESS:mcpapply-disable" in sink.text


def test_a_live_dry_run_never_even_builds_a_session(home: Path):
    built: list[str] = []

    def factory(cwd: str) -> object:
        built.append(cwd)
        return _FakeClient()

    sink = Sink()
    code = main(
        ["disable", "cloud-hub", "--home", str(home), "--live"],
        now=FIXED_NOW,
        runner=_quiet,
        client_for=factory,  # type: ignore[arg-type]
        write=sink,
    )
    assert code == 0
    assert built == [], "a dry run started a control session"
    assert "ZERO frames were sent" in sink.text


def test_a_disproven_affordance_is_refused_rather_than_attempted():
    """The recorded evidence table gates the UI mechanically, not aspirationally."""
    outcome = run_live(
        intent="reconnect",
        server="cloud-hub",
        scope=ScopeId.CLAUDE_USER,
        apply=True,
        client_for=lambda: pytest.fail("a disproven affordance was attempted"),
    )
    assert outcome.proof is Proof.DISPROVEN
    assert outcome.op is LiveOp.RECONNECT
    assert outcome.sent == ()
    assert "Server not found" in outcome.refusal


def test_the_gui_offers_only_the_intents_its_form_can_actually_carry():
    """Regression: the dropdown showed 3 intents while the API accepted all 6.

    ``edit`` was therefore reachable over HTTP from a form with no spec field -- and an
    ``edit`` with no spec replaced a live definition with an empty object.
    """
    assert set(gui.GUI_INTENTS) == {"disable", "enable"}
    page = gui.render_page((), "tok")
    for absent in ("add", "edit", "remove", "reconnect"):
        assert f"<option>{absent}</option>" not in page
    for offered in gui.GUI_INTENTS:
        assert f"<option>{offered}</option>" in page


# --------------------------------------------------------------------------
# LENS: honesty -- a proxy number can never pass as a measurement
# --------------------------------------------------------------------------


def _one_server_impact(basis: TokenBasis, tokens: int | None = 77_198) -> Impact:
    top = topology_from(
        {
            "claude_json": {
                "mcpServers": {"cloud-hub": {"command": "x"}},
                "projects": {PROJECT_KEY: {"disabledMcpServers": []}},
            }
        },
        project_key=PROJECT_KEY,
    )
    plan = build_plan([plan_disable(top, "cloud-hub")], project_key=PROJECT_KEY)
    cost = Cost(token_cost=tokens, token_basis=basis, commit_bytes=17_400_000)
    return preview(plan, {"cloud-hub": cost}, regime=Regime.EAGER)


def test_a_proxy_token_figure_renders_DIFFERENTLY_from_a_measured_one():
    """Regression: the basis was parsed, then dropped on aggregation.

    The A/B that exposed it: same server, same number, only the declared basis
    differing, produced byte-identical operator output. Tokens-per-tool spans 12.5x,
    so an unlabelled integer is a guess presented as a budget.
    """
    exact = render_impact(_one_server_impact(TokenBasis.EXACT))
    proxy = render_impact(_one_server_impact(TokenBasis.TOOL_COUNT))
    assert exact != proxy
    assert "[exact-count-tokens]" in exact
    assert "[tool-count-proxy]" in proxy
    assert "PROXY and not a measurement" in proxy
    assert "PROXY" not in exact
    # ...and the label survives serialisation, for the GUI and for --json.
    assert _one_server_impact(TokenBasis.EXACT).to_dict()["token_basis"] == (
        "exact-count-tokens"
    )
    assert "proxy" in json.dumps(_one_server_impact(TokenBasis.TOOL_COUNT).to_dict())


def test_an_aggregate_carries_the_WEAKEST_contributing_basis():
    """A sum of one exact and one guessed number is a guess."""
    top = topology_from(
        {
            "claude_json": {
                "mcpServers": {"a": {"command": "x"}, "b": {"command": "y"}},
                "projects": {PROJECT_KEY: {"disabledMcpServers": []}},
            }
        },
        project_key=PROJECT_KEY,
    )
    plan = build_plan(
        [plan_disable(top, "a"), plan_disable(top, "b")], project_key=PROJECT_KEY
    )
    impact = preview(
        plan,
        {
            "a": Cost(token_cost=10, token_basis=TokenBasis.EXACT, remote=True),
            "b": Cost(token_cost=90, token_basis=TokenBasis.SCHEMA_BYTES, remote=True),
        },
        regime=Regime.EAGER,
    )
    assert impact.token_delta == 100
    assert impact.token_basis is TokenBasis.SCHEMA_BYTES


def test_a_number_with_NO_declared_basis_is_not_summed_into_a_firm_total():
    """Regression: ``load_costs`` defaults an absent basis to NOT_MEASURED, and the
    aggregate summed it anyway -- so a hand-written costs file rendered a guessed
    figure as ``partial: false``, a confident total.
    """
    impact = _one_server_impact(TokenBasis.NOT_MEASURED)
    assert impact.token_delta is None
    assert impact.partial is True
    assert "cloud-hub" in impact.unmeasured
    assert any("NO token_basis" in note for note in impact.notes)
    assert "tokens saved:  -" in render_impact(impact)


# --------------------------------------------------------------------------
# LENS: web GUI security
# --------------------------------------------------------------------------


@pytest.fixture
def secure_base(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """A real loopback server, plus a canary file OUTSIDE the static tree."""
    leak = tmp_path / "LEAKME.js"
    leak.write_text("SECRET_OUTSIDE_STATIC_DIR", encoding="utf-8")
    ports = gui.GuiPorts(
        rows=lambda: (),
        plan_for=lambda _i, _s: build_plan([], project_key=None),
        impact_for=lambda _p: Impact(regime=Regime.EAGER),
        apply_plan=lambda _p, _c: ApplyResult(dry_run=True),
        token="tok-not-a-secret",
    )
    httpd = gui.serve(ports, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", leak
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _raw(port: int, request: str) -> bytes:
    """Send a request the WHATWG URL parser would rewrite, so a browser cannot."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        sock.sendall(request.encode("latin-1"))
        chunks: list[bytes] = []
        while True:
            block = sock.recv(65536)
            if not block:
                break
            chunks.append(block)
        return b"".join(chunks)
    finally:
        sock.close()


def _get_raw(base: str, path: str, extra: str = "") -> bytes:
    port = int(base.rsplit(":", 1)[1])
    return _raw(
        port,
        f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"{extra}Connection: close\r\n\r\n",
    )


def test_the_static_handler_cannot_be_walked_out_of_its_own_directory(
    secure_base: tuple[str, Path],
):
    """Regression: the containment check blocked ``/`` and ``..`` but not the NATIVE
    separator and not an absolute path, so ``GET /static/C:\\...\\x.js`` read an
    arbitrary file -- unauthenticated, before any token check.

    The pre-fix test vector list was four POSIX-shaped names on a Windows-first repo,
    so 100% coverage was satisfied while the control it named did not hold.
    """
    base, leak = secure_base
    vectors = (
        str(leak),
        str(leak).replace("\\", "/"),
        str(leak).replace("C:", ""),
        "..\\pyproject.toml",
        "../pyproject.toml",
        "sub\\..\\..\\pyproject.toml",
        "sub/../../pyproject.toml",
        "%2e%2e%5cpyproject.toml",
        "nope.js",
        "app.py",
    )
    for name in vectors:
        response = _get_raw(base, f"/static/{name}")
        assert b" 404 " in response.split(b"\r\n", 1)[0], name
        assert b"SECRET_OUTSIDE_STATIC_DIR" not in response, name
        assert b"[project]" not in response, name

    # Detector control: the probe DOES see a leak when the bytes really are served.
    canary = gui.STATIC_DIR / "regression-canary.js"
    canary.write_text("SECRET_OUTSIDE_STATIC_DIR", encoding="utf-8")
    try:
        served = _get_raw(base, "/static/regression-canary.js")
        assert b" 200 " in served.split(b"\r\n", 1)[0]
        assert b"SECRET_OUTSIDE_STATIC_DIR" in served
    finally:
        canary.unlink()


def test_a_cache_busted_asset_url_still_resolves(secure_base: tuple[str, Path]):
    """Regression: the query string was never stripped, so ``Path('app.js?v=1').suffix``
    missed the media-type table and the GUI own JS 404-ed."""
    base, _ = secure_base
    assert b" 200 " in _get_raw(base, "/static/app.js?v=1").split(b"\r\n", 1)[0]
    assert b" 200 " in _get_raw(base, "/static/app.css?v=2").split(b"\r\n", 1)[0]


def test_a_non_ascii_token_header_is_answered_not_crashed(
    secure_base: tuple[str, Path],
):
    """Regression: ``http.server`` decodes headers as latin-1, so a byte above 0x7F
    made the str form of ``compare_digest`` raise -- an unauthenticated caller could
    force an unhandled exception on the auth path and receive NO response at all."""
    base, _ = secure_base
    response = _get_raw(base, "/api/matrix", extra="X-MCPApply-Token: \xc3\xa9vil\r\n")
    assert response, "the server closed the connection without answering"
    assert b" 401 " in response.split(b"\r\n", 1)[0]
    control = _get_raw(base, "/api/matrix", extra="X-MCPApply-Token: asciiwrong\r\n")
    assert b" 401 " in control.split(b"\r\n", 1)[0]


def test_the_control_surface_refuses_to_be_framed(secure_base: tuple[str, Path]):
    """``frame-ancestors`` has NO fallback to ``default-src``, so the bare
    ``default-src 'self'`` left an MCP control surface freely embeddable."""
    base, _ = secure_base
    headers = _get_raw(base, "/").split(b"\r\n\r\n", 1)[0].decode("latin-1").lower()
    assert "frame-ancestors 'none'" in headers
    assert "x-frame-options: deny" in headers


@pytest.mark.parametrize(
    ("header", "allowed"),
    [
        ("127.0.0.1:8000", True),
        ("localhost:8000", True),
        ("LOCALHOST:8000", True),
        ("127.0.0.1", True),
        ("[::1]:8000", True),
        # Regression: splitting on the LAST colon discarded everything after the port.
        ("127.0.0.1:8000.evil.example", False),
        ("127.0.0.1:evil", False),
        ("evil.example:8000", False),
        ("127.0.0.1.evil.example:8000", False),
        ("0.0.0.0:8000", False),
        ("2130706433", False),
        ("", False),
    ],
)
def test_the_host_allowlist_requires_a_NUMERIC_port(header: str, allowed: bool):
    assert gui.host_allowed(header) is allowed


def test_a_refused_post_still_delivers_its_reason_rather_than_resetting(
    secure_base: tuple[str, Path],
):
    """Regression: the body was consumed only AFTER the token gate, so a 401/400 was
    written and the connection then torn down with data still unread -- which on
    Windows sends RST and DISCARDS the queued response. Measured as two
    intermittently-failing tests; the caller saw a connection reset, not the reason."""
    base, _ = secure_base
    port = int(base.rsplit(":", 1)[1])
    body = json.dumps({"intent": "disable", "server": "x"})

    unauthorised = _raw(
        port,
        f"POST /api/plan HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n{body}",
    )
    assert b" 401 " in unauthorised.split(b"\r\n", 1)[0]
    assert b"bad or missing token" in unauthorised

    unknown_route = _raw(
        port,
        f"POST /api/nope HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}",
    )
    assert b" 404 " in unknown_route.split(b"\r\n", 1)[0]

    bad_host = _raw(
        port,
        f"POST /api/plan HTTP/1.1\r\nHost: evil.example\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}",
    )
    assert b" 403 " in bad_host.split(b"\r\n", 1)[0]


def test_an_unparseable_content_length_with_no_body_is_answered_not_hung(
    secure_base: tuple[str, Path],
):
    """The best-effort drain must give up rather than block forever."""
    base, _ = secure_base
    port = int(base.rsplit(":", 1)[1])
    response = _raw(
        port,
        f"POST /api/plan HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"X-MCPApply-Token: tok-not-a-secret\r\n"
        f"Content-Length: not-a-number\r\nConnection: close\r\n\r\n",
    )
    assert b" 400 " in response.split(b"\r\n", 1)[0]
    assert b"JSON object body" in response


def test_the_matrix_api_reports_a_scope_it_could_not_read(
    secure_base: tuple[str, Path],
):
    base, _ = secure_base
    response = _get_raw(
        base, "/api/matrix", extra="X-MCPApply-Token: tok-not-a-secret\r\n"
    )
    payload = json.loads(response.split(b"\r\n\r\n", 1)[1])
    assert payload["problems"] == []


def test_a_read_problem_is_rendered_on_the_page(tmp_path: Path):
    rows: tuple[Row, ...] = ()
    page = gui.render_page(rows, "tok", ("mcp_json (x): unparseable",))
    assert "UNREADABLE mcp_json (x): unparseable" in page
    assert "UNREADABLE" not in gui.render_page(rows, "tok")


def test_a_missing_costs_file_is_a_typed_failure_not_a_bare_traceback(home: Path):
    """Every CLI path honours the terminal-state contract, including this one.

    Regression: ``--costs <missing>`` escaped as an uncaught ``FileNotFoundError`` --
    exit 1, a bare traceback, and NOT ONE envelope line, so a caller parsing for
    ``SUCCESS:``/``FAILED:`` saw nothing at all.
    """
    sink = Sink()
    code = main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--costs",
            str(home / "nope.json"),
        ],
        now=FIXED_NOW,
        runner=_quiet,
        write=sink,
    )
    assert code == 1
    assert "FAILED:mcpapply-disable" in sink.text
    assert "--costs could not be read" in sink.text
    assert sum(ln.startswith(("SUCCESS:", "FAILED:")) for ln in sink.lines) == 1


def test_a_malformed_costs_file_is_also_a_typed_failure(home: Path):
    bad = home / "costs.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    sink = Sink()
    code = main(
        ["disable", "cloud-hub", "--home", str(home), "--costs", str(bad)],
        now=FIXED_NOW,
        runner=_quiet,
        write=sink,
    )
    assert code == 1
    assert "FAILED:mcpapply-disable" in sink.text


def test_the_tool_block_credit_is_reachable_from_the_command_line(home: Path):
    """``--fleet-size`` wires the 496-token credit that no caller could reach.

    Regression: ``preview`` was called from two places and NEITHER passed
    ``fleet_size``, so the documented one-off credit never fired in the shipped
    product. The error direction was conservative, but the docs claimed otherwise.
    """
    costs = home / "costs.json"
    costs.write_text(
        json.dumps(
            {"cloud-hub": {"token_cost": 1000, "token_basis": "exact-count-tokens"}}
        ),
        encoding="utf-8",
    )
    sink = Sink()
    main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--project",
            PROJECT_KEY,
            "--costs",
            str(costs),
            "--fleet-size",
            "1",
        ],
        now=FIXED_NOW,
        runner=_quiet,
        write=sink,
    )
    assert "tokens saved:  1496" in sink.text
    assert "removes the last tool-bearing server" in sink.text


def test_a_document_verb_cannot_be_forced_down_the_control_channel(home: Path):
    sink = Sink()
    code = main(
        ["add", "newsrv", "--home", str(home), "--live", "--spec", '{"command": "x"}'],
        now=FIXED_NOW,
        runner=_quiet,
        write=sink,
    )
    assert code == 1
    assert "FAILED:mcpapply-add" in sink.text
    assert "no control-channel form" in sink.text


def test_a_refused_live_op_is_a_FAILED_envelope_with_the_recorded_reason(home: Path):
    sink = Sink()
    code = main(
        ["reconnect", "cloud-hub", "--home", str(home), "--live", "--apply"],
        now=FIXED_NOW,
        runner=_quiet,
        client_for=lambda _cwd: pytest.fail("a disproven affordance was attempted"),
        write=sink,
    )
    assert code == 1
    assert "REFUSED:" in sink.text
    assert "Server not found" in sink.text
    assert "root cause:" in sink.text
    assert "FAILED:mcpapply-reconnect" in sink.text


def test_the_live_path_emits_machine_readable_json_on_request(home: Path):
    sink = Sink()
    code = main(
        [
            "disable",
            "cloud-hub",
            "--home",
            str(home),
            "--live",
            "--apply",
            "--json",
        ],
        now=FIXED_NOW,
        runner=_quiet,
        client_for=lambda _cwd: _FakeClient(),  # type: ignore[arg-type]
        write=sink,
    )
    assert code == 0
    payload = json.loads(sink.text)
    assert payload["live"]["op"] == "mcp_toggle"
    assert payload["live"]["dry_run"] is False
    assert payload["live"]["frames_sent"] == 3
    assert payload["terminal"].startswith("SUCCESS:mcpapply-disable")


def test_a_refused_live_op_reports_its_refusal_in_json_too(home: Path):
    sink = Sink()
    code = main(
        ["reconnect", "cloud-hub", "--home", str(home), "--live", "--apply", "--json"],
        now=FIXED_NOW,
        runner=_quiet,
        write=sink,
    )
    assert code == 1
    payload = json.loads(sink.text)
    assert payload["live"]["refusal"]
    assert payload["terminal"].startswith("FAILED:mcpapply-reconnect")


def test_an_undefined_server_falls_back_to_the_declared_scope(home: Path):
    """A server with no definition still needs a scope to look its affordance up in."""
    client = _FakeClient()
    sink = Sink()
    code = main(
        [
            "disable",
            "never-heard-of-it",
            "--home",
            str(home),
            "--live",
            "--apply",
            "--scope",
            "mcp-json",
        ],
        now=FIXED_NOW,
        runner=_quiet,
        client_for=lambda _cwd: client,  # type: ignore[arg-type]
        write=sink,
    )
    assert code == 1
    assert client.calls == []
    assert "CLEAN NEGATIVE" in sink.text


def test_a_path_the_os_cannot_resolve_is_a_404_not_a_traceback(
    secure_base: tuple[str, Path], monkeypatch: pytest.MonkeyPatch
):
    """An unauthenticated route must never answer with a 500 and a stack trace."""
    base, _ = secure_base
    real = Path.resolve

    def exploding(self: Path, *args: object, **kwargs: object) -> Path:
        if "boom" in self.name:
            raise OSError("the OS refused to resolve this name")
        return real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", exploding)
    assert b" 404 " in _get_raw(base, "/static/boom.js").split(b"\r\n", 1)[0]
