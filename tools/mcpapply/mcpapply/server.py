"""A localhost-only web GUI: stdlib ``http.server`` + hand-written static assets.

No framework, no CDN, no npm, no network fetch of any kind, and **zero resident cost
when closed** -- there is no daemon, no service and no scheduled task: the process
exists only while the operator is looking at it.

Security posture, all enforced here and all covered by tests:

* **Bound to 127.0.0.1 only.** :func:`serve` refuses any other host outright rather
  than trusting the caller.
* **Host-header allowlist.** A browser can be lured to ``http://<attacker-dns>/``
  that resolves to 127.0.0.1 (DNS rebinding); the loopback bind alone does not stop
  that. Requests whose ``Host`` is not loopback are rejected.
* **A per-run bearer token on every ``/api/`` route**, mutating or not. The inventory
  is sensitive (it names credential-bearing servers), so a read is gated too. Two
  routes are deliberately NOT gated and the distinction matters: ``GET /`` must serve
  the token (it is how the operator's browser obtains it) and therefore also serves
  the rendered matrix, and ``/static/`` serves two fixed assets. Neither is readable
  cross-origin -- no ``Access-Control-Allow-Origin`` header is ever sent -- so the
  token cannot be stolen by a page the operator merely visits.
* **Static assets are served by CONTAINMENT, not by a blocklist.** ``_static``
  resolves the candidate and requires it to be inside :data:`STATIC_DIR`. A
  character blocklist is the wrong shape on this platform: an earlier version rejected
  ``/`` and ``..`` but not the native backslash and not a drive letter, so a request
  naming an absolute path read an arbitrary file, unauthenticated.
* **An explicit confirm on every mutating route.** ``POST /api/apply`` requires both
  the token and a literal ``{"confirm": "APPLY"}`` body; anything else previews.
* **Escaped output.** Every server name reaches the HTML through
  :func:`mcpctl.safety.safe` (strip controls, THEN redact -- that order is a proven
  leak bypass if reversed) and then ``html.escape`` with ``quote=True``. The static JS
  builds DOM nodes with ``textContent`` and never assigns ``innerHTML``; a test asserts
  that mechanically over the shipped asset.
* **No credential VALUE can reach a response.** Not by filtering, but structurally:
  the only env representation in the model is ``mcpctl.safety.EnvField`` -- a name
  plus present/absent/reference -- so a value was never parsed in the first place.
"""

from __future__ import annotations

import html
import json
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from mcpctl.matrix import Row
from mcpctl.safety import safe

from mcpapply.apply import ApplyResult
from mcpapply.impact import Impact
from mcpapply.plan import Plan

__all__ = [
    "GUI_INTENTS",
    "LOOPBACK_HOSTS",
    "STATIC_DIR",
    "GuiPorts",
    "host_allowed",
    "make_handler",
    "render_page",
    "require_loopback",
    "serve",
]

#: The only host this GUI may bind to or accept a ``Host`` header for.
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})

#: The intents the GUI offers. Deliberately a SUBSET of the CLI's verbs, and the ONE
#: source for both the rendered dropdown and the API allowlist -- previously the
#: dropdown offered three and the API accepted all six, so ``edit``/``remove`` were
#: reachable over HTTP from a UI that never showed them. What is excluded, and why:
#:
#: * ``add`` / ``edit`` take a definition spec the GUI has no field for. Reachable
#:   without one, ``edit`` replaced a live definition with ``{}`` -- command, args and
#:   the whole env block gone.
#: * ``remove`` deletes a definition outright and the GUI has no undo affordance.
#: * ``reconnect`` is live-channel-only: the GUI owns no control session, and the
#:   recorded affordance for BOTH config scopes is disproven/unproven
#:   (:data:`mcpapply.live.AFFORDANCES`). Offering it would advertise a control the
#:   evidence says does not work. It lives on the CLI's ``--live`` path instead.
GUI_INTENTS: tuple[str, ...] = ("disable", "enable")

STATIC_DIR = Path(__file__).parent / "static"

#: The largest request body this API will accept. A plan request is a few hundred
#: bytes; anything past this is a mistake or an attempt to exhaust memory.
_MAX_BODY = 64_000

#: The largest body it will DRAIN before refusing. Between the two limits the body is
#: read and discarded so the 400 actually reaches the client (see ``_consume_body``).
_MAX_DRAIN = 1_048_576

#: How long the best-effort drain waits when ``Content-Length`` is unparseable and the
#: body's size therefore cannot be known. Loopback only, so this is generous.
_DRAIN_SECONDS = 0.25

_MEDIA_TYPES: Mapping[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


@dataclass(frozen=True)
class GuiPorts:
    """Everything the GUI needs from the rest of the package, injected.

    The handler owns no business logic: it authenticates, routes, serialises and
    escapes. That is what keeps it a thin shell over the pure core.
    """

    rows: Callable[[], tuple[Row, ...]]
    plan_for: Callable[[str, str], Plan]
    impact_for: Callable[[Plan], Impact]
    apply_plan: Callable[[Plan, bool], ApplyResult]
    token: str
    #: Scopes that could not be read on THIS request. Rendered on the page: a config
    #: file that became unparseable while the window was open otherwise just vanishes
    #: from the matrix, which reads as "that server is gone" rather than "I cannot see".
    problems: Callable[[], tuple[str, ...]] = tuple


def _esc(text: str) -> str:
    """The mandated order: safe() (strip controls, then redact) THEN html.escape."""
    return html.escape(safe(text), quote=True)


def host_allowed(host: str) -> bool:
    """Whether a ``Host`` header names loopback. PURE, so it is asserted on directly.

    Splitting on the last colon and accepting whatever precedes it is not enough:
    ``127.0.0.1:8000.evil.example`` passes that test, because everything after the
    port is simply discarded. The port is therefore required to be numeric. Host names
    are compared case-insensitively, per RFC 9110.
    """
    if not host:
        return False
    name = host
    if ":" in host and not host.endswith("]"):
        name, _, port = host.rpartition(":")
        if not port.isdigit():
            return False
    return name.lower() in LOOPBACK_HOSTS


def render_page(rows: Sequence[Row], token: str, problems: Sequence[str] = ()) -> str:
    """Server-render the health matrix. Works with JavaScript disabled."""
    body = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>mcpapply</title>",
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<link rel="stylesheet" href="/static/app.css">',
        "</head><body>",
        "<h1>MCP control</h1>",
        '<p class="sub">localhost only &middot; dry-run by default &middot; '
        "every apply needs an explicit confirm</p>",
        f'<div id="token" data-token="{_esc(token)}"></div>',
        *(
            [
                '<ul class="problems">'
                + "".join(f"<li>UNREADABLE {_esc(p)}</li>" for p in problems)
                + "</ul>"
            ]
            if problems
            else []
        ),
        "<table><thead><tr><th>server</th><th>state</th><th>transport</th>"
        "<th>tools</th><th>basis</th><th>credentials</th></tr></thead><tbody>",
    ]
    for row in rows:
        tools = "-" if row.tool_count is None else str(row.tool_count)
        creds = ", ".join(f"{f.name}={f.kind}" for f in row.env_fields) or "-"
        body.append(
            "<tr>"
            f"<td>{_esc(row.name)}</td>"
            f'<td class="s-{_esc(row.state)}">{_esc(row.state)}'
            f"{'~' if row.inferred else ''}</td>"
            f"<td>{_esc(row.transport)}</td>"
            f"<td>{_esc(tools)}</td>"
            f"<td>{_esc(', '.join(row.basis))}</td>"
            f"<td>{_esc(creds)}</td>"
            "</tr>"
        )
    body.extend(
        [
            "</tbody></table>",
            '<section id="preview"><h2>plan preview</h2>'
            '<form id="planner"><label>intent '
            '<select name="intent">'
            + "".join(f"<option>{_esc(i)}</option>" for i in GUI_INTENTS)
            + "</select></label> "
            '<label>server <input name="server" required></label> '
            '<button type="submit">preview</button></form>'
            '<pre id="out">no plan yet</pre>'
            '<button id="apply" disabled>apply (requires confirm)</button>'
            "</section>",
            '<script src="/static/app.js"></script>',
            "</body></html>",
        ]
    )
    return "".join(body)


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def make_handler(ports: GuiPorts) -> type[BaseHTTPRequestHandler]:
    """Build the request handler class bound to ``ports``."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "mcpapply"
        sys_version = ""

        def log_message(self, format: str, *args: object) -> None:
            """Silence the default stderr access log -- it echoes the raw request line."""

        # -- helpers -------------------------------------------------------
        def _send(self, code: int, body: bytes, media: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            # `frame-ancestors` has NO fallback to `default-src`, so the bare
            # default-src this used to send left the control surface freely
            # embeddable. X-Frame-Options repeats it for anything that predates CSP2.
            self.send_header(
                "Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'"
            )
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Mapping[str, object]) -> None:
            self._send(code, _json_bytes(payload), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            return host_allowed(self.headers.get("Host", ""))

        def _authorised(self) -> bool:
            """Constant-time token check that cannot be crashed by the caller.

            The comparison is over BYTES. ``http.server`` decodes headers as latin-1,
            so any byte above 0x7F yields a non-ASCII ``str`` and the ``str`` form of
            ``compare_digest`` raises ``TypeError`` -- an unauthenticated caller could
            force an unhandled exception on the auth path and get no response at all.
            """
            offered = self.headers.get("X-MCPApply-Token", "")
            return secrets.compare_digest(
                offered.encode("utf-8", "replace"), ports.token.encode("utf-8")
            )

        def _consume_body(self) -> bytes | None:
            """Read the request body NOW -- before any gate can refuse the request.

            Returns the bytes, or ``None`` when the body is unusable (absent, an
            unparseable length, or over :data:`_MAX_BODY`).

            **The ordering is the whole point.** Answering a POST without consuming
            its body leaves data in the receive buffer; the connection is then torn
            down, which on Windows sends RST and DISCARDS the response already queued.
            The caller sees a connection reset instead of the 401/400 explaining the
            refusal -- measured, and the cause of two intermittently-failing tests.
            Draining only on the parse path fixed one gate out of four.
            """
            declared = self.headers.get("Content-Length", "0").strip()
            if declared.isdigit():
                length = int(declared)
                if length <= 0 or length > _MAX_DRAIN:
                    return None
                raw = self.rfile.read(length)
                return raw if length <= _MAX_BODY else None
            # A malformed length: the body's size is unknowable, so take whatever has
            # already arrived without blocking, purely so the 400 is not lost too.
            self.connection.settimeout(_DRAIN_SECONDS)
            try:
                self.rfile.read1(_MAX_DRAIN)
            except OSError:
                pass
            finally:
                self.connection.settimeout(None)
            return None

        def _parse_body(self, raw: bytes | None) -> Mapping[str, object] | None:
            """Decode a consumed body into a JSON object, or ``None`` to reject it."""
            if raw is None:
                return None
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            return parsed if isinstance(parsed, dict) else None

        def _static(self, name: str) -> None:
            """Serve one asset from :data:`STATIC_DIR`, by CONTAINMENT.

            The candidate is resolved and then required to sit inside the resolved
            static root. This is what makes ``C:\\...``, ``\\...``, ``sub\\..\\..\\x``
            and any future separator spelling all fail at once -- the previous
            blocklist (reject ``/`` and ``..``) let every backslash and drive-letter
            form through and served an arbitrary file to an unauthenticated caller.
            ``resolve()`` can raise on a malformed name, which is also a 404.
            """
            root = STATIC_DIR.resolve()
            try:
                target = (root / name).resolve()
            except (OSError, ValueError):
                self._json(404, {"error": "not found"})
                return
            media = _MEDIA_TYPES.get(target.suffix)
            if media is None or not target.is_relative_to(root) or not target.is_file():
                self._json(404, {"error": "not found"})
                return
            self._send(200, target.read_bytes(), media)

        def _route(self) -> str:
            """The path with any query string removed.

            ``Path("app.js?v=1").suffix`` is ``".js?v=1"``, so leaving the query on
            made every cache-busted asset URL a 404 -- the GUI's own JS and CSS
            included, the moment anything appended ``?v=``.
            """
            return urlsplit(self.path).path

        # -- routes --------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's contract.
            if not self._host_ok():
                self._json(403, {"error": "non-loopback Host header refused"})
                return
            route = self._route()
            if route == "/":
                page = render_page(ports.rows(), ports.token, ports.problems()).encode(
                    "utf-8"
                )
                self._send(200, page, "text/html; charset=utf-8")
                return
            if route.startswith("/static/"):
                self._static(route[len("/static/") :])
                return
            if route == "/api/matrix":
                if not self._authorised():
                    self._json(401, {"error": "bad or missing token"})
                    return
                self._json(
                    200,
                    {
                        "rows": [r.to_dict() for r in ports.rows()],
                        "problems": [safe(p) for p in ports.problems()],
                    },
                )
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's contract.
            # Consumed FIRST, so every refusal below actually reaches the caller.
            raw = self._consume_body()
            if not self._host_ok():
                self._json(403, {"error": "non-loopback Host header refused"})
                return
            if self._route() not in ("/api/plan", "/api/apply"):
                self._json(404, {"error": "not found"})
                return
            if not self._authorised():
                self._json(401, {"error": "bad or missing token"})
                return
            body = self._parse_body(raw)
            if body is None:
                self._json(400, {"error": "a JSON object body is required"})
                return
            intent = str(body.get("intent", ""))
            server = str(body.get("server", ""))
            if not intent or not server:
                self._json(400, {"error": "intent and server are required"})
                return
            try:
                plan = ports.plan_for(intent, server)
            except ValueError as exc:
                self._json(400, {"error": safe(str(exc))})
                return
            payload: dict[str, object] = {
                "plan": plan.to_dict(),
                "impact": ports.impact_for(plan).to_dict(),
            }
            if self._route() == "/api/plan":
                self._json(200, payload)
                return
            confirmed = body.get("confirm") == "APPLY"
            result = ports.apply_plan(plan, confirmed)
            payload["result"] = result.to_dict()
            payload["confirmed"] = confirmed
            if not confirmed:
                payload["error"] = (
                    'apply refused: send {"confirm": "APPLY"} to authorise the write. '
                    "The preview above is what would have happened."
                )
            self._json(200, payload)

    return Handler


def require_loopback(host: str) -> None:
    """Raise unless ``host`` is loopback. PURE, so it can be asserted on without
    binding a socket -- a test that had to call :func:`serve` to see the refusal would,
    when the check is broken, really expose this control surface to the network for the
    duration of the test."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            f"refusing to bind {host!r}: this GUI is loopback-only. Exposing an MCP "
            "control surface on a routable interface would hand config-write access to "
            "the network."
        )


def serve(
    ports: GuiPorts, *, host: str = "127.0.0.1", port: int = 0
) -> ThreadingHTTPServer:
    """Create (but do not run) the loopback GUI server on an ephemeral port by default."""
    require_loopback(host)
    return ThreadingHTTPServer((host, port), make_handler(ports))


def new_token() -> str:
    """A fresh per-run bearer token. Never persisted."""
    return secrets.token_urlsafe(32)
