"""Local redirect-chain fixture and fetch-stage adapters for ADV-0032.

All listeners bind 127.0.0.1. The metadata hop is 169.254.169.254 (link-local),
never a third-party host.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PUBLIC_CANARY = "ADV-0032-PUBLIC-CANARY"
SINK_CANARY = "ADV-0032-SINK-HIT"
META_TARGET = "http://169.254.169.254/latest/meta-data/"


def load_module(name: str, path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.hits: list[dict[str, Any]] = []
        self.sink_hits = 0
        self.sink_delay_s = 0.45

    def record(self, row: dict[str, Any]) -> None:
        with self.lock:
            self.hits.append(row)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {"hits": list(self.hits), "sink_hits": self.sink_hits}


def _handler(state: _State, sink_port: int):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def _send(self, code: int, body: bytes, extra: dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if extra:
                for k, v in extra.items():
                    self.send_header(k, v)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            state.record(
                {
                    "path": path,
                    "host": self.headers.get("Host", ""),
                    "client": self.client_address[0],
                }
            )
            if path in ("/public", "/"):
                self._send(200, PUBLIC_CANARY.encode())
                return
            if path == "/redir-loopback":
                loc = f"http://127.0.0.1:{sink_port}/sink-loopback"
                self._send(302, b"redirect\n", {"Location": loc})
                return
            if path == "/redir-metadata":
                self._send(302, b"redirect\n", {"Location": META_TARGET})
                return
            if path.startswith("/chain/"):
                try:
                    n = int(path.rsplit("/", 1)[-1])
                except ValueError:
                    n = 0
                if n <= 0:
                    self._send(200, PUBLIC_CANARY.encode())
                    return
                loc = f"http://127.0.0.1:{self.server.server_address[1]}/chain/{n - 1}"
                self._send(302, b"chain\n", {"Location": loc})
                return
            if path == "/sink-loopback":
                with state.lock:
                    state.sink_hits += 1
                time.sleep(state.sink_delay_s)
                self._send(200, SINK_CANARY.encode())
                return
            self._send(404, b"not-found\n")

    return H


class FixturePair:
    """Public-looking fixture plus a distinct-port loopback sink."""

    def __init__(self) -> None:
        self.state = _State()
        self._sink = ThreadingHTTPServer(("127.0.0.1", 0), _handler(self.state, 0))
        self.sink_port = int(self._sink.server_address[1])
        self._fx = ThreadingHTTPServer(
            ("127.0.0.1", 0), _handler(self.state, self.sink_port)
        )
        self.fx_port = int(self._fx.server_address[1])
        self._threads: list[threading.Thread] = []

    def start(self) -> "FixturePair":
        for srv in (self._sink, self._fx):
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def stop(self) -> None:
        for srv in (self._fx, self._sink):
            srv.shutdown()
            srv.server_close()

    def __enter__(self) -> "FixturePair":
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    def url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"http://127.0.0.1:{self.fx_port}{path}"


def _redact(result: dict[str, Any]) -> dict[str, Any]:
    blob = " ".join(
        [
            str(result.get("final_url") or ""),
            str(result.get("body") or ""),
            str(result.get("error") or ""),
        ]
    )
    if "169.254.169.254" in blob or "ami-id" in blob:
        result = dict(result)
        result["body"] = "[REDACTED-LINK-LOCAL-IMDS]"
        result["imds_body_redacted"] = True
    return result


def urllib_fetch(url: str, timeout: float = 2.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url, method="GET", headers={"User-Agent": "ADV-0032-urllib"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return _redact(
                {
                    "ok": True,
                    "status": int(getattr(resp, "status", 200) or 200),
                    "final_url": str(resp.geturl()),
                    "body": body.decode("utf-8", errors="replace")[:200],
                    "error": None,
                }
            )
    except Exception as exc:  # noqa: BLE001
        return _redact(
            {
                "ok": False,
                "status": None,
                "final_url": url,
                "body": "",
                "error": f"{type(exc).__name__}:{exc}",
            }
        )


def spdx_fetch(url: str, timeout: float = 2.0) -> dict[str, Any]:
    mod = load_module("adv0032_spdx", REPO / "tools" / "marketplace" / "spdx.py")
    orig = urllib.request.urlopen

    def _wrapped(*args, **kwargs):
        kwargs["timeout"] = min(float(kwargs.get("timeout") or timeout), timeout)
        return orig(*args, **kwargs)

    urllib.request.urlopen = _wrapped  # type: ignore[assignment]
    try:
        raw = mod._default_fetch(url)
        text = (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, (bytes, bytearray))
            else str(raw)
        )
        return _redact(
            {
                "ok": True,
                "status": 200,
                "final_url": url,
                "body": text[:200],
                "error": None,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _redact(
            {
                "ok": False,
                "status": None,
                "final_url": url,
                "body": "",
                "error": f"{type(exc).__name__}:{exc}",
            }
        )
    finally:
        urllib.request.urlopen = orig  # type: ignore[assignment]


def research_capture_fetch(url: str, timeout: float = 2.0) -> dict[str, Any]:
    """Same urllib+SSL pattern as RES-0008/RES-0125 research capture stages."""
    import ssl

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ADV-0032-research-capture", "Accept": "*/*"},
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read()
            return _redact(
                {
                    "ok": True,
                    "status": int(getattr(resp, "status", 200) or 200),
                    "final_url": str(resp.geturl()),
                    "body": body.decode("utf-8", errors="replace")[:200],
                    "error": None,
                }
            )
    except Exception as exc:  # noqa: BLE001
        return _redact(
            {
                "ok": False,
                "status": None,
                "final_url": url,
                "body": "",
                "error": f"{type(exc).__name__}:{exc}",
            }
        )


def res0170_fetch(url: str, timeout: float = 2.0) -> dict[str, Any]:
    import sys

    d = REPO / "command-center" / "p2-wave" / "probes" / "RES-0170"
    sys.path.insert(0, str(d))
    try:
        import resolver as R  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": None,
            "final_url": url,
            "body": "",
            "error": f"import:{type(exc).__name__}:{exc}",
        }
    got = R.fetch(url, timeout=timeout)
    return _redact(
        {
            "ok": bool(got.get("ok")),
            "status": got.get("http_status"),
            "final_url": got.get("url") or url,
            "body": str(got.get("body_text") or "")[:200],
            "error": got.get("error"),
        }
    )


class SsrfBlocked(RuntimeError):
    pass


def _host_blocked(host: str) -> bool:
    if not host:
        return True
    if host.lower() in {"localhost", "metadata.google.internal"}:
        return True
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return True
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            return True
    return False


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if _host_blocked(parsed.hostname or ""):
            raise SsrfBlocked(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def guarded_fetch(url: str, timeout: float = 2.0) -> dict[str, Any]:
    """First hop allowed; redirect hops to private/loopback/link-local refused."""
    opener = urllib.request.build_opener(_GuardedRedirect)
    req = urllib.request.Request(
        url, method="GET", headers={"User-Agent": "ADV-0032-guard"}
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
            return {
                "ok": True,
                "status": int(getattr(resp, "status", 200) or 200),
                "final_url": str(resp.geturl()),
                "body": body.decode("utf-8", errors="replace")[:200],
                "error": None,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": None,
            "final_url": url,
            "body": "",
            "error": f"{type(exc).__name__}:{exc}",
        }


STAGES: list[dict[str, Any]] = [
    {
        "id": "stage:stdlib-urllib-urlopen",
        "path": "urllib.request.urlopen",
        "fetch": urllib_fetch,
    },
    {
        "id": "stage:tools-marketplace-spdx-_default_fetch",
        "path": "tools/marketplace/spdx.py",
        "fetch": spdx_fetch,
    },
    {
        "id": "stage:research-capture-urllib-ssl",
        "path": "command-center/p2-wave/probes/RES-0008/capture.py",
        "fetch": research_capture_fetch,
    },
    {
        "id": "stage:research-resolver-RES-0170",
        "path": "command-center/p2-wave/probes/RES-0170/resolver.py",
        "fetch": res0170_fetch,
    },
]


def ipv4_proc_key(ip: str, port: int) -> str:
    parts = [int(x) for x in ip.split(".")]
    addr = "".join(f"{b:02X}" for b in reversed(parts))
    return f"{addr}:{port:04X}".upper()


def proc_tcp_keys() -> set[str]:
    keys: set[str] = set()
    for rel in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(rel).read_text(encoding="utf-8", errors="replace").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            cols = line.split()
            if len(cols) < 3:
                continue
            keys.add(cols[2].upper())
            keys.add(cols[1].upper())
    return keys


def ss_lines(ip: str, port: int) -> str:
    import shutil
    import subprocess

    if not shutil.which("ss"):
        return ""
    try:
        p = subprocess.run(
            ["ss", "-tnH", "dst", f"{ip}:{port}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (p.stdout or "") + (p.stderr or "")


def inspect_spdx_controls() -> dict[str, Any]:
    text = (REPO / "tools" / "marketplace" / "spdx.py").read_text(encoding="utf-8")
    low = text.lower()
    return {
        "path": "tools/marketplace/spdx.py",
        "uses_urlopen": "urlopen" in text,
        "has_host_allowlist": any(
            t in low for t in ("allowlist", "allowed_hosts", "host_allow")
        ),
        "has_private_range_block": any(
            t in text for t in ("is_private", "169.254", "link-local", "RFC1918")
        ),
        "mentions_redirect": "redirect" in low,
        "bytes": len(text.encode("utf-8")),
    }


def census_urlopen(root: Path) -> list[str]:
    hits: list[str] = []
    skip = {".git", "node_modules", "__pycache__", "p2-wave"}
    for p in root.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        try:
            blob = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "urlopen" in blob or "urllib.request" in blob:
            rel = str(p.relative_to(REPO)).replace("\\", "/")
            hits.append(rel)
    return sorted(hits)


def first_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


FetchFn = Callable[[str], dict[str, Any]]


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "fetch":
        timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
        result = urllib_fetch(sys.argv[2], timeout=timeout)
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result.get("ok") else 1)
    print("usage: ssrf_lib.py fetch URL [timeout]", file=sys.stderr)
    raise SystemExit(2)
