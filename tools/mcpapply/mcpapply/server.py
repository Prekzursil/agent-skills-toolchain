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
* **A per-run bearer token on EVERY API route**, mutating or not. The inventory is
  sensitive (it names credential-bearing servers), so a read is gated too.
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

from mcpctl.matrix import Row
from mcpctl.safety import safe

from mcpapply.apply import ApplyResult
from mcpapply.impact import Impact
from mcpapply.plan import Plan

__all__ = [
    "LOOPBACK_HOSTS",
    "STATIC_DIR",
    "GuiPorts",
    "make_handler",
    "render_page",
    "require_loopback",
    "serve",
]

#: The only host this GUI may bind to or accept a ``Host`` header for.
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})

STATIC_DIR = Path(__file__).parent / "static"

#: The largest request body this API will accept. A plan request is a few hundred
#: bytes; anything past this is a mistake or an attempt to exhaust memory.
_MAX_BODY = 64_000

#: The largest body it will DRAIN before refusing. Between the two limits the body is
#: read and discarded so the 400 actually reaches the client (see ``_body``).
_MAX_DRAIN = 1_048_576

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


def _esc(text: str) -> str:
    """The mandated order: safe() (strip controls, then redact) THEN html.escape."""
    return html.escape(safe(text), quote=True)


def render_page(rows: Sequence[Row], token: str) -> str:
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
            '<select name="intent"><option>disable</option><option>enable</option>'
            "<option>reconnect</option></select></label> "
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
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Mapping[str, object]) -> None:
            self._send(code, _json_bytes(payload), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            host = self.headers.get("Host", "")
            return host.rsplit(":", 1)[0] in LOOPBACK_HOSTS

        def _authorised(self) -> bool:
            offered = self.headers.get("X-MCPApply-Token", "")
            return secrets.compare_digest(offered, ports.token)

        def _body(self) -> Mapping[str, object] | None:
            """Read and validate a JSON object body, or ``None`` to reject it.

            An over-large-but-drainable body is READ AND DISCARDED before the refusal
            is sent. Answering without draining leaves the client mid-write, and the
            socket is torn down before the 400 is delivered -- so the caller sees a
            connection reset instead of the reason it was rejected.
            """
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if length <= 0 or length > _MAX_DRAIN:
                return None
            raw = self.rfile.read(length)
            if length > _MAX_BODY:
                return None
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            return parsed if isinstance(parsed, dict) else None

        def _static(self, name: str) -> None:
            target = STATIC_DIR / name
            media = _MEDIA_TYPES.get(target.suffix)
            if media is None or "/" in name or ".." in name or not target.is_file():
                self._json(404, {"error": "not found"})
                return
            self._send(200, target.read_bytes(), media)

        # -- routes --------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's contract.
            if not self._host_ok():
                self._json(403, {"error": "non-loopback Host header refused"})
                return
            if self.path == "/":
                page = render_page(ports.rows(), ports.token).encode("utf-8")
                self._send(200, page, "text/html; charset=utf-8")
                return
            if self.path.startswith("/static/"):
                self._static(self.path[len("/static/") :])
                return
            if self.path == "/api/matrix":
                if not self._authorised():
                    self._json(401, {"error": "bad or missing token"})
                    return
                self._json(200, {"rows": [r.to_dict() for r in ports.rows()]})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 -- BaseHTTPRequestHandler's contract.
            if not self._host_ok():
                self._json(403, {"error": "non-loopback Host header refused"})
                return
            if self.path not in ("/api/plan", "/api/apply"):
                self._json(404, {"error": "not found"})
                return
            if not self._authorised():
                self._json(401, {"error": "bad or missing token"})
                return
            body = self._body()
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
            if self.path == "/api/plan":
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
