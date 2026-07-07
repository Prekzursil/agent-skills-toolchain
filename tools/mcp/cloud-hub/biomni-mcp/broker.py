#!/usr/bin/env python3
"""Biomni localhost token-broker — inject the Bearer so the connector never holds it.

A stdlib reverse proxy bound to 127.0.0.1 that forwards to api.phylo.bio and
OVERWRITES the ``Authorization`` header with the real Bearer, read from a secure
source (1Password ``op``, OS keyring, or a chmod-600 file). The biomni MCP
connector points ``BIOMNI_API_BASE`` at this broker (and sets ``BIOMNI_BROKER=1``),
sends NO real token, and the broker adds it -- so the literal token lives ONLY in
the secure store + this process, never in the connector's config, the agent's
context, or any log.

This is the "access without exposure" pattern: the connector/agent handles only a
loopback handle; resolution happens HERE, in deterministic code, not in the model.

Token sources (first that resolves wins):
  1. BIOMNI_BROKER_OP_REF    -> ``op read <ref>``  (1Password secret ref op://vault/item/field)
  2. BIOMNI_BROKER_KEYRING   -> ``service[:user]``  (Windows Credential Manager / Keychain / libsecret)
  3. BIOMNI_BROKER_TOKEN_FILE (default ~/.biomni-mcp/broker_token) -> file contents
  4. BIOMNI_BROKER_TOKEN     -> env var (least preferred)

The token is cached for ``BIOMNI_BROKER_TTL`` seconds (default 60) so a rotated
token is picked up. The value is NEVER logged or returned by /__broker/health
(masked previews only). Binds to 127.0.0.1 ONLY.

Run:   python broker.py [--port 8787] [--upstream https://api.phylo.bio]
Wire:  BIOMNI_API_BASE=http://127.0.0.1:8787  BIOMNI_BROKER=1   (on the biomni connector)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_UPSTREAM = "https://api.phylo.bio"
DEFAULT_PORT = 8787
DEFAULT_TTL = 60.0
HEALTH_PATH = "/__broker/health"

# Hop-by-hop headers (RFC 7230 §6.1) + auth/host/length that the proxy rewrites.
_STRIP_HEADERS = {
    "authorization",
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


# --------------------------------------------------------------------------- #
# Token resolution (secure sources) + masking
# --------------------------------------------------------------------------- #
def _mask(token: str) -> str:
    """Non-reversible preview; never the full value."""
    if not token:
        return ""
    return f"...{token[-4:]}" if len(token) > 8 else "set"


def resolve_token_uncached(environ: dict[str, str]) -> tuple[str, str]:
    """Resolve the Bearer from the first configured secure source; (token, source).

    Pure w.r.t. ``environ`` except for the op/keyring/file side effects it is meant
    to perform; returns ("", "none") if nothing resolves. Never raises.
    """
    op_ref = environ.get("BIOMNI_BROKER_OP_REF", "").strip()
    if op_ref:
        tok = _op_read(op_ref)
        if tok:
            return tok, "op"
    kr = environ.get("BIOMNI_BROKER_KEYRING", "").strip()
    if kr:
        tok = _keyring_read(kr)
        if tok:
            return tok, "keyring"
    path = environ.get("BIOMNI_BROKER_TOKEN_FILE", "").strip() or os.path.join(
        os.path.expanduser("~"), ".biomni-mcp", "broker_token"
    )
    tok = _file_read(path)
    if tok:
        return tok, "file"
    env_tok = environ.get("BIOMNI_BROKER_TOKEN", "").strip()
    if env_tok:
        return env_tok, "env"
    return "", "none"


def _op_read(ref: str) -> str:
    """`op read <ref>` (1Password). Returns "" on any failure. Never logs output."""
    try:
        proc = subprocess.run(  # noqa: S603  (fixed argv, no shell)
            ["op", "read", ref],  # noqa: S607  (op resolved from PATH by design)
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _keyring_read(spec: str) -> str:
    """keyring service[:user] lookup (OS credential store). "" on any failure."""
    service, _, user = spec.partition(":")
    try:
        import keyring  # noqa: PLC0415  (optional dep, lazy)

        val = keyring.get_password(service, user or "biomni")
    except Exception:  # noqa: BLE001  (missing lib or backend error -> no token)
        return ""
    return (val or "").strip()


def _file_read(path: str) -> str:
    """Read a chmod-600 token file; "" if missing/unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


class TokenCache:
    """Caches the resolved token for a TTL so rotation is picked up cheaply."""

    def __init__(self, environ: dict[str, str], ttl: float, clock=time.monotonic):
        self.environ = environ
        self.ttl = ttl
        self.clock = clock
        self._token = ""
        self._source = "none"
        self._at = -1e18

    def get(self) -> tuple[str, str]:
        now = self.clock()
        if now - self._at > self.ttl or not self._token:
            self._token, self._source = resolve_token_uncached(self.environ)
            self._at = now
        return self._token, self._source


# --------------------------------------------------------------------------- #
# Header rewriting (pure — unit-tested)
# --------------------------------------------------------------------------- #
def upstream_headers(
    incoming: list[tuple[str, str]], token: str, upstream_host: str
) -> dict[str, str]:
    """Copy incoming headers minus auth/host/hop-by-hop; inject the real Bearer + Host."""
    out: dict[str, str] = {}
    for key, val in incoming:
        if key.lower() not in _STRIP_HEADERS:
            out[key] = val
    out["Authorization"] = f"Bearer {token}"
    out["Host"] = upstream_host
    return out


# --------------------------------------------------------------------------- #
# Reverse-proxy handler
# --------------------------------------------------------------------------- #
def make_handler(upstream: str, cache: TokenCache):
    upstream = upstream.rstrip("/")
    upstream_host = urllib.parse.urlsplit(upstream).netloc

    class Handler(BaseHTTPRequestHandler):
        server_version = "biomni-broker/1.0"

        def log_message(self, fmt, *args):  # noqa: A002  (silence; never log tokens/urls)
            return

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _health(self) -> None:
            token, source = cache.get()
            self._send_json(
                200,
                {
                    "ok": True,
                    "broker": "biomni",
                    "upstream": upstream,
                    "token_source": source,
                    "token_present": bool(token),
                    "token_masked": _mask(token),
                },
            )

        def _proxy(self) -> None:
            if self.path == HEALTH_PATH:
                self._health()
                return
            token, source = cache.get()
            if not token:
                self._send_json(
                    503,
                    {
                        "ok": False,
                        "error": "no Biomni token available to the broker; set one of "
                        "BIOMNI_BROKER_OP_REF / BIOMNI_BROKER_KEYRING / "
                        "BIOMNI_BROKER_TOKEN_FILE / BIOMNI_BROKER_TOKEN",
                        "token_source": source,
                    },
                )
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = upstream_headers(self.headers.items(), token, upstream_host)
            req = urllib.request.Request(
                upstream + self.path, data=body, headers=headers, method=self.command
            )
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310
                    self._relay(resp.status, resp.headers.items(), resp.read())
            except urllib.error.HTTPError as exc:
                self._relay(exc.code, exc.headers.items(), exc.read())
            except (urllib.error.URLError, OSError) as exc:
                self._send_json(502, {"ok": False, "error": f"upstream failed: {exc}"})

        def _relay(self, status: int, headers, body: bytes) -> None:
            self.send_response(status)
            for key, val in headers:
                if key.lower() not in (
                    "transfer-encoding",
                    "connection",
                    "content-length",
                ):
                    self.send_header(key, val)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = _proxy
        do_POST = _proxy
        do_PUT = _proxy
        do_PATCH = _proxy
        do_DELETE = _proxy

    return Handler


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Biomni localhost token-broker")
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BIOMNI_BROKER_PORT", DEFAULT_PORT)),
    )
    ap.add_argument(
        "--upstream", default=os.environ.get("BIOMNI_BROKER_UPSTREAM", DEFAULT_UPSTREAM)
    )
    ap.add_argument(
        "--ttl",
        type=float,
        default=float(os.environ.get("BIOMNI_BROKER_TTL", DEFAULT_TTL)),
    )
    args = ap.parse_args(argv)

    cache = TokenCache(dict(os.environ), args.ttl)
    token, source = cache.get()
    handler = make_handler(args.upstream, cache)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(
        f"[biomni-broker] 127.0.0.1:{args.port} -> {args.upstream} | "
        f"token_source={source} present={bool(token)} ({_mask(token)})",
        file=sys.stderr,
    )
    print(
        "[biomni-broker] wire the connector: "
        f"BIOMNI_API_BASE=http://127.0.0.1:{args.port} BIOMNI_BROKER=1",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
