"""TLS-only registry index fetch. Handshake failure does not downgrade to HTTP."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from tools.lib.net_allowlist import AllowlistError, inspect_config_keys

CLASS_TLS = "tls-handshake-failed"
CLASS_PARSE = "config-parse-rejected"
CLASS_OK = "ok"


@dataclass
class FetchResult:
    ok: bool = False
    classification: str = CLASS_TLS
    exit_code: int = 1
    cache_substituted: bool = False
    connections: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    bytes_written: int = 0


def parse_config(doc: dict[str, Any]) -> dict[str, Any]:
    inspect_config_keys(doc)
    url = str(doc.get("registry_url") or "")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise AllowlistError("registry_url must be https", CLASS_PARSE)
    return dict(doc)


def fetch_index(cfg: dict[str, Any]) -> FetchResult:
    try:
        cfg = parse_config(cfg)
    except AllowlistError as exc:
        return FetchResult(ok=False, classification=getattr(exc, "classification", CLASS_PARSE), exit_code=2, error=str(exc))
    url = str(cfg.get("registry_url") or "")
    parsed = urlparse(url)
    cafile = cfg.get("cafile")
    server_hostname = cfg.get("server_hostname") or parsed.hostname
    timeout = float(cfg.get("timeout") or 4.0)
    ctx = ssl.create_default_context()
    if cafile:
        ctx.load_verify_locations(cafile=str(cafile))
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    result = FetchResult(connections=[{"host": parsed.hostname, "port": parsed.port, "scheme": parsed.scheme}])
    try:
        import http.client
        import socket

        host = parsed.hostname or "127.0.0.1"
        port = int(parsed.port or 443)
        raw = socket.create_connection((host, port), timeout=timeout)
        ssock = ctx.wrap_socket(raw, server_hostname=str(server_hostname or host))
        conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
        conn.sock = ssock
        conn.request("GET", parsed.path or "/index.json")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        dest = cfg.get("index_path")
        if dest:
            from pathlib import Path

            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(body)
            result.bytes_written = len(body)
        result.ok = True
        result.classification = CLASS_OK
        result.exit_code = 0
        return result
    except ssl.SSLError as exc:
        result.ok = False
        result.classification = CLASS_TLS
        result.exit_code = 1
        result.error = f"SSLError:{exc}"
        return result
    except Exception as exc:  # noqa: BLE001
        result.ok = False
        result.classification = CLASS_TLS
        result.exit_code = 1
        result.error = f"{type(exc).__name__}:{exc}"
        return result
