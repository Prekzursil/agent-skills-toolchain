#!/usr/bin/env python3
"""Stdlib fake web origin for the search-hub ``read_url`` adapter tests.

Stands in for the public web so ``ReadUrlAdapter`` is exercised over a REAL
loopback socket with NO network. Routes model the paths the adapter must handle:

* ``/cf``        -> Cloudflare "Markdown for Agents" behaviour: when the request's
  ``Accept`` prefers ``text/markdown`` it answers ``Content-Type: text/markdown``
  with ``x-markdown-tokens`` / ``x-original-tokens`` headers and a body of YAML
  frontmatter + clean markdown (+ a fenced JSON-LD block), exactly like an
  opted-in zone; otherwise it serves the HTML page.
* ``/html``      -> an HTML page full of boilerplate (script/style/noscript/svg/
  template/nav/footer/aside/header), a ``<title>``, entities, and paragraphs.
* ``/plain``     -> ``text/plain``.
* ``/latin1``    -> HTML declared ``charset=iso-8859-1`` with a non-ASCII byte.
* ``/big``       -> a large ``text/plain`` body (size-cap / ``truncated`` path).
* ``/binary``    -> ``application/pdf`` bytes (unsupported content type).
* ``/404``       -> HTTP 404 with an HTML body.
* ``/loop``      -> 302 to itself (redirect loop).
* ``/hop/N``     -> 302 to ``/hop/N-1``; ``/hop/0`` is the ``/html`` page.
* ``/to-onion``  -> 302 to ``http://expyuzz4wqqyqhjn.onion/`` (envelope test).
* ``/to-file``   -> 302 to ``file:///etc/passwd`` (scheme re-check test).
* ``/to-private``-> 302 to ``http://intranet.test/`` (private re-check test).
* ``/nolocation``-> 302 without a Location header.

Every request is appended to ``RECEIVED`` as ``{"path", "headers"}`` (lower-cased
header keys) so tests can assert on the negotiated ``Accept``, the User-Agent, and
the ABSENCE of ``Cookie`` / ``Authorization`` headers. Call ``reset()`` first.
"""

from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

RECEIVED: list[dict] = []
_LOCK = threading.Lock()

MARKDOWN_BODY = """---
title: "Markdown for Agents"
description: "Clean markdown negotiated with Accept: text/markdown"
lang: en
---

# Markdown for Agents

Cloudflare converts the HTML to markdown at the edge when the `Accept` header
prefers `text/markdown`.

- one request header
- server-side boilerplate removal

```json
{"@context": "https://schema.org", "@type": "Article", "headline": "Markdown for Agents"}
```
"""

HTML_BODY = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Example   Page &mdash; Read Me</title>
  <style>body { color: red } /* SKIP-STYLE */</style>
  <script>console.log("SKIP-SCRIPT");</script>
  <link rel="stylesheet" href="/x.css">
</head>
<body>
  <header><h1>SKIP-HEADER site banner</h1></header>
  <nav><a href="/">SKIP-NAV home</a> <a href="/about">SKIP-NAV about</a></nav>
  <noscript>SKIP-NOSCRIPT enable javascript</noscript>
  <svg viewBox="0 0 10 10"><text>SKIP-SVG</text></svg>
  <template><p>SKIP-TEMPLATE</p></template>
  <main>
    <article>
      <h2>First heading</h2>
      <p>Tom &amp; Jerry went to the market &#8212; it was  <b>busy</b>,
         very   busy.</p>
      <p>Second paragraph with an <a href="/link">inline link</a> and
         <code>inline code</code>.</p>
      <ul><li>alpha</li><li>beta</li></ul>
      <script type="application/ld+json">{"SKIP-SCRIPT": true}</script>
    </article>
    <aside>SKIP-ASIDE related links</aside>
  </main>
  <footer>SKIP-FOOTER copyright</footer>
</body>
</html>
"""

BIG_LINE = ("lorem ipsum dolor sit amet " * 4).strip() + "\n"
BIG_BODY = (BIG_LINE * 4000).encode("utf-8")  # ~430 KB of text/plain


def reset() -> None:
    with _LOCK:
        RECEIVED.clear()


class _Handler(BaseHTTPRequestHandler):
    def _send(
        self, status: int, body: bytes, content_type: str, extra: dict | None = None
    ) -> None:
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self._send(302, b"", "text/html; charset=utf-8", {"Location": location})

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        headers = {k.lower(): v for k, v in self.headers.items()}
        with _LOCK:
            RECEIVED.append({"path": self.path, "headers": headers})
        path = self.path.split("?", 1)[0]
        if path == "/cf":
            accept = headers.get("accept", "")
            if "text/markdown" in accept:
                self._send(
                    200,
                    MARKDOWN_BODY.encode("utf-8"),
                    "text/markdown; charset=utf-8",
                    {"x-markdown-tokens": "123", "x-original-tokens": "4567"},
                )
                return
            self._send(200, HTML_BODY.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path in ("/html", "/hop/0"):
            self._send(200, HTML_BODY.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/plain":
            self._send(200, b"just  plain\n\n\n\ntext", "text/plain; charset=utf-8")
            return
        if path == "/latin1":
            body = b"<html><head><title>Caf\xe9</title></head><body><p>na\xefve</p></body></html>"
            self._send(200, body, "text/html; charset=iso-8859-1")
            return
        if path == "/big":
            self._send(200, BIG_BODY, "text/plain; charset=utf-8")
            return
        if path == "/binary":
            self._send(200, b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", "application/pdf")
            return
        if path == "/404":
            self._send(
                404, b"<html><title>Missing</title><p>nope</p></html>", "text/html"
            )
            return
        if path == "/loop":
            self._redirect("/loop")
            return
        if path.startswith("/hop/"):
            n = int(path.rsplit("/", 1)[1])
            self._redirect(f"/hop/{n - 1}")
            return
        if path == "/to-onion":
            self._redirect("http://expyuzz4wqqyqhjn.onion/")
            return
        if path == "/to-file":
            self._redirect("file:///etc/passwd")
            return
        if path == "/to-private":
            self._redirect("http://intranet.test/")
            return
        if path == "/nolocation":
            self._send(302, b"", "text/html")
            return
        self._send(404, b"not found", "text/plain")

    def log_message(self, *_args) -> None:  # keep the test output quiet
        return


def start_server() -> tuple[HTTPServer, str]:
    """Bind a loopback fake origin on a free port; returns (server, base_url)."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"fake-page listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
