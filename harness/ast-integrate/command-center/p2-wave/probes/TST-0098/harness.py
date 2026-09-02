#!/usr/bin/env python3
"""TST-0098 live network fault-injection matrix.

Six injectable faults x fail-closed adapters for the catalog-named external
boundaries. Product HTTP clients are inventoried on this worktree; they are
absent, so the adapters under test are the fail-closed library this unit
owns (TST-0122 delegates network faults here).

Every production cell must be a typed failure. EMPTY_SUCCESS is a P1.
A planted swallower is a detector control, not a production boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import struct
import threading
import time
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

FAULTS = (
    "dns_failure",
    "connection_reset",
    "tls_error",
    "slow_loris",
    "truncated_response",
    "mid_stream_disconnect",
)

TYPED = {
    "dns_failure": "DNS_FAILURE",
    "connection_reset": "CONNECTION_RESET",
    "tls_error": "TLS_ERROR",
    "slow_loris": "READ_TIMEOUT",
    "truncated_response": "TRUNCATED_RESPONSE",
    "mid_stream_disconnect": "MID_STREAM_DISCONNECT",
}

CODE_PATH = "command-center/p2-wave/probes/TST-0098/harness.py:fetch_fail_closed"
SWALLOW_PATH = (
    "command-center/p2-wave/probes/TST-0098/harness.py:"
    "planted_empty_success_swallower"
)
DNS_HOST = "tst-0098-nxdomain.invalid"

NET_API_RE = re.compile(
    r"urllib\.request|urllib\.error|http\.client|httpx|aiohttp|"
    r"requests\.(get|post|put|request)|urlopen\(|create_connection\(|"
    r"wrap_socket\(|fetch\(|https\.request|net\.createConnection",
    re.I,
)


class TypedFault(Exception):
    def __init__(self, classification: str, detail: str, *, bytes_got: int = 0):
        super().__init__(detail)
        self.classification = classification
        self.detail = detail
        self.bytes_got = bytes_got


@dataclass
class FetchResult:
    ok: bool
    classification: str
    detail: str
    staging_bytes: int
    committed_unchanged: bool
    staging_promoted: bool
    exception_type: str = ""


@dataclass
class Boundary:
    id: str
    role: str
    method: str
    path: str
    body: bytes
    mode: str  # json | digest | stream | ack
    req_body: bytes = b""


def _pkg_body() -> bytes:
    return b"PKG-TST-0098\n" + (b"\x61" * 1800) + b"\nEND\n"


def _stream_body() -> bytes:
    return (b"chunk-" * 200)[:1600]


BOUNDARIES: tuple[Boundary, ...] = (
    Boundary(
        id="marketplace_registry_fetch",
        role="B07 marketplace registry index GET",
        method="GET",
        path="/registry/index.json",
        body=json.dumps({"ok": True, "packages": ["demo@1.0.0"]}).encode() + b"\n",
        mode="json",
    ),
    Boundary(
        id="package_download",
        role="B07 package blob GET with digest",
        method="GET",
        path="/packages/demo.bin",
        body=_pkg_body(),
        mode="digest",
    ),
    Boundary(
        id="research_fetch",
        role="research/remote notes GET",
        method="GET",
        path="/research/note.json",
        body=json.dumps({"ok": True, "notes": ["n1", "n2"]}).encode() + b"\n",
        mode="json",
    ),
    Boundary(
        id="cloud_dispatch",
        role="cloud job POST expecting ack",
        method="POST",
        path="/jobs",
        body=json.dumps({"accepted": True, "id": "job-tst-0098"}).encode() + b"\n",
        mode="ack",
        req_body=b'{"job":"tst-0098"}\n',
    ),
    Boundary(
        id="cross_vendor_mcp_stream",
        role="cross-vendor MCP-like streaming GET",
        method="GET",
        path="/mcp/stream",
        body=_stream_body(),
        mode="stream",
    ),
)


def _linger_rst(conn: socket.socket) -> None:
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    conn.close()


def _read_request(conn: socket.socket, budget: float = 0.4) -> bytes:
    conn.settimeout(budget)
    buf = b""
    end = time.monotonic() + budget
    while time.monotonic() < end and b"\r\n\r\n" not in buf:
        try:
            chunk = conn.recv(4096)
        except (TimeoutError, socket.timeout):
            break
        if not chunk:
            break
        buf += chunk
        if len(buf) > 65536:
            break
    return buf


def _http_ok(body: bytes, extra_headers: list[str] | None = None) -> bytes:
    hdrs = [
        "HTTP/1.1 200 OK",
        f"Content-Length: {len(body)}",
        "Content-Type: application/octet-stream",
        "Connection: close",
    ]
    if extra_headers:
        hdrs.extend(extra_headers)
    return ("\r\n".join(hdrs) + "\r\n\r\n").encode() + body


class FaultServer:
    def __init__(self, kind: str, body: bytes, extra_headers: list[str] | None = None):
        self.kind = kind
        self.body = body
        self.extra_headers = extra_headers or []
        self.sock: socket.socket | None = None
        self.port = 0
        self._th: threading.Thread | None = None
        self._err: str | None = None

    def start(self) -> FaultServer:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        srv.settimeout(4.0)
        self.sock = srv
        self.port = srv.getsockname()[1]
        self._th = threading.Thread(target=self._serve, daemon=True)
        self._th.start()
        return self

    def _serve(self) -> None:
        assert self.sock is not None
        try:
            conn, _ = self.sock.accept()
        except Exception as exc:  # noqa: BLE001
            self._err = f"accept:{type(exc).__name__}"
            return
        try:
            self._apply(conn)
        except Exception as exc:  # noqa: BLE001
            self._err = f"apply:{type(exc).__name__}:{exc}"
            try:
                conn.close()
            except OSError:
                pass

    def _apply(self, conn: socket.socket) -> None:
        kind = self.kind
        if kind == "connection_reset":
            _read_request(conn, 0.2)
            _linger_rst(conn)
            return
        if kind == "tls_error":
            try:
                conn.sendall(b"NOT-A-TLS-RECORD\r\n")
            finally:
                conn.close()
            return
        if kind == "slow_loris":
            try:
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n")
                time.sleep(8.0)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
            return
        if kind == "truncated_response":
            full = _http_ok(self.body, self.extra_headers)
            # Headers plus a prefix of the body, then FIN.
            cut = full.index(b"\r\n\r\n") + 4 + min(64, max(8, len(self.body) // 8))
            try:
                conn.sendall(full[:cut])
                conn.shutdown(socket.SHUT_WR)
                time.sleep(0.05)
            except OSError:
                pass
            finally:
                conn.close()
            return
        if kind == "mid_stream_disconnect":
            full = _http_ok(self.body, self.extra_headers)
            cut = full.index(b"\r\n\r\n") + 4 + min(64, max(8, len(self.body) // 8))
            try:
                conn.sendall(full[:cut])
            except OSError:
                pass
            _linger_rst(conn)
            return
        if kind == "healthy":
            _read_request(conn, 0.5)
            try:
                conn.sendall(_http_ok(self.body, self.extra_headers))
            finally:
                conn.close()
            return
        conn.close()

    def stop(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        if self._th is not None:
            self._th.join(timeout=1.5)

    def __enter__(self) -> FaultServer:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def _map_oserror(exc: OSError, bytes_got: int) -> TypedFault:
    errno = getattr(exc, "errno", None)
    name = type(exc).__name__
    if isinstance(exc, ssl.SSLError) or name in {"SSLError", "SSLCertVerificationError"}:
        return TypedFault("TLS_ERROR", f"{name}:{exc}", bytes_got=bytes_got)
    if isinstance(exc, socket.gaierror) or errno in {socket.EAI_NONAME, -2, -5}:
        return TypedFault("DNS_FAILURE", f"{name}:{exc}", bytes_got=bytes_got)
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return TypedFault("READ_TIMEOUT", f"{name}:{exc}", bytes_got=bytes_got)
    if isinstance(exc, ConnectionResetError) or errno == 104:
        if bytes_got > 0:
            return TypedFault(
                "MID_STREAM_DISCONNECT", f"{name}:{exc}", bytes_got=bytes_got
            )
        return TypedFault("CONNECTION_RESET", f"{name}:{exc}", bytes_got=bytes_got)
    if isinstance(exc, (ConnectionRefusedError, ConnectionAbortedError, BrokenPipeError)):
        if bytes_got > 0:
            return TypedFault(
                "MID_STREAM_DISCONNECT", f"{name}:{exc}", bytes_got=bytes_got
            )
        return TypedFault("CONNECTION_RESET", f"{name}:{exc}", bytes_got=bytes_got)
    return TypedFault("UNTYPED", f"{name}:{exc}", bytes_got=bytes_got)


def fetch_fail_closed(
    host: str,
    port: int,
    path: str,
    *,
    use_tls: bool,
    timeout: float,
    method: str,
    req_body: bytes,
    staging_path: Path,
    committed_path: Path,
    expect_digest: str | None,
    mode: str,
) -> FetchResult:
    """Fail-closed fetch. Never promotes staging on a short or faulted read."""
    before = (
        hashlib.sha256(committed_path.read_bytes()).hexdigest()
        if committed_path.is_file()
        else None
    )
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    if staging_path.exists():
        staging_path.unlink()
    staging_path.write_bytes(b"")
    body_got = 0
    sock: socket.socket | None = None

    def _finish_fault(tf: TypedFault) -> FetchResult:
        after = (
            hashlib.sha256(committed_path.read_bytes()).hexdigest()
            if committed_path.is_file()
            else None
        )
        promoted = after is not None and after != before and staging_path.is_file()
        # promoted if committed now equals staging of a failed body — always false
        # if we never os.replace.
        return FetchResult(
            ok=False,
            classification=tf.classification,
            detail=tf.detail,
            staging_bytes=staging_path.stat().st_size if staging_path.exists() else 0,
            committed_unchanged=(after == before),
            staging_promoted=promoted,
            exception_type="TypedFault",
        )

    try:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.settimeout(timeout)
            if use_tls:
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)
            payload = req_body or b""
            req = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                "Accept: */*\r\n"
                "Connection: close\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "\r\n"
            ).encode() + payload
            sock.sendall(req)
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise TypedFault(
                        "TRUNCATED_RESPONSE",
                        "peer closed before complete headers",
                        bytes_got=0,
                    )
                buf += chunk
            header_blob, rest = buf.split(b"\r\n\r\n", 1)
            headers = {}
            lines = header_blob.split(b"\r\n")
            if not lines or not lines[0].startswith(b"HTTP/1."):
                raise TypedFault(
                    "UNTYPED", f"bad status line {lines[:1]!r}", bytes_got=0
                )
            for line in lines[1:]:
                if b":" in line:
                    k, v = line.split(b":", 1)
                    headers[k.strip().lower()] = v.strip()
            try:
                content_len = int(headers.get(b"content-length", b"-1"))
            except ValueError:
                content_len = -1
            body = bytearray(rest)
            body_got = len(body)
            staging_path.write_bytes(bytes(body))
            if content_len >= 0:
                while len(body) < content_len:
                    chunk = sock.recv(min(4096, content_len - len(body)))
                    if not chunk:
                        staging_path.write_bytes(bytes(body))
                        raise TypedFault(
                            "TRUNCATED_RESPONSE",
                            f"FIN at {len(body)}/{content_len}",
                            bytes_got=len(body),
                        )
                    body.extend(chunk)
                    body_got = len(body)
                    staging_path.write_bytes(bytes(body))
            else:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    body.extend(chunk)
                    body_got = len(body)
                    staging_path.write_bytes(bytes(body))
            raw = bytes(body)
            if mode == "json":
                doc = json.loads(raw.decode("utf-8"))
                if not isinstance(doc, dict) or doc.get("ok") is not True:
                    raise TypedFault("UNTYPED", f"json not ok: {doc!r}", bytes_got=len(raw))
            elif mode == "ack":
                doc = json.loads(raw.decode("utf-8"))
                if not isinstance(doc, dict) or doc.get("accepted") is not True:
                    raise TypedFault("UNTYPED", f"ack missing: {doc!r}", bytes_got=len(raw))
            elif mode == "digest":
                digest = hashlib.sha256(raw).hexdigest()
                if expect_digest and digest != expect_digest:
                    raise TypedFault(
                        "UNTYPED",
                        f"digest mismatch {digest} != {expect_digest}",
                        bytes_got=len(raw),
                    )
            elif mode == "stream":
                if len(raw) < 32:
                    raise TypedFault("TRUNCATED_RESPONSE", "stream too short", bytes_got=len(raw))
            os.replace(staging_path, committed_path)
            after = hashlib.sha256(committed_path.read_bytes()).hexdigest()
            return FetchResult(
                ok=True,
                classification="SUCCESS",
                detail="promoted",
                staging_bytes=len(raw),
                committed_unchanged=(after == before),
                staging_promoted=True,
            )
        except TypedFault as tf:
            return _finish_fault(tf)
        except (OSError, socket.timeout, TimeoutError, ssl.SSLError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, (json.JSONDecodeError, ValueError)) and not isinstance(
                exc, (OSError, TimeoutError)
            ):
                tf = TypedFault("UNTYPED", f"{type(exc).__name__}:{exc}", bytes_got=body_got)
            else:
                tf = _map_oserror(exc if isinstance(exc, OSError) else OSError(exc), body_got)
            return _finish_fault(tf)
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def planted_empty_success_swallower(
    host: str,
    port: int,
    path: str,
    **kwargs,
) -> FetchResult:
    """Detector control: swallows any fault into an empty SUCCESS.

    A matrix that cannot see this is blind to empty-success P1s.
    """
    inner = fetch_fail_closed(host, port, path, **kwargs)
    if inner.ok:
        return inner
    return FetchResult(
        ok=True,
        classification="SUCCESS",
        detail="swallowed:" + inner.classification,
        staging_bytes=0,
        committed_unchanged=True,
        staging_promoted=False,
        exception_type="swallowed",
    )


def _extra_headers(boundary: Boundary) -> list[str]:
    if boundary.mode == "digest":
        return [f"X-Content-SHA256: {hashlib.sha256(boundary.body).hexdigest()}"]
    return []


def _work_paths(root: Path, boundary_id: str, fault: str) -> tuple[Path, Path]:
    d = root / boundary_id / fault
    d.mkdir(parents=True, exist_ok=True)
    return d / "staging.bin", d / "committed.bin"


def run_one(
    boundary: Boundary,
    fault: str,
    work: Path,
    *,
    client: Callable[..., FetchResult] = fetch_fail_closed,
    timeout: float | None = None,
) -> dict:
    staging, committed = _work_paths(work, boundary.id, fault)
    seed = b"SEED-PARTIAL-TST-0098:" + boundary.id.encode() + b"\n"
    committed.write_bytes(seed)
    seed_sha = hashlib.sha256(seed).hexdigest()
    to = 0.45 if fault == "slow_loris" else (timeout or 2.0)
    digest = hashlib.sha256(boundary.body).hexdigest() if boundary.mode == "digest" else None
    kwargs = dict(
        use_tls=(fault == "tls_error"),
        timeout=to,
        method=boundary.method,
        req_body=boundary.req_body,
        staging_path=staging,
        committed_path=committed,
        expect_digest=digest,
        mode=boundary.mode,
    )
    if fault == "dns_failure":
        result = client(DNS_HOST, 443, boundary.path, **kwargs)
    else:
        kind = "healthy" if fault == "healthy" else fault
        with FaultServer(kind, boundary.body, _extra_headers(boundary)) as srv:
            result = client("127.0.0.1", srv.port, boundary.path, **kwargs)
    after = (
        hashlib.sha256(committed.read_bytes()).hexdigest() if committed.is_file() else None
    )
    empty_success = bool(
        result.ok and result.classification == "SUCCESS" and fault != "healthy"
    )
    if (
        result.ok
        and result.classification == "SUCCESS"
        and result.staging_bytes == 0
        and fault != "healthy"
    ):
        empty_success = True
        result.classification = "EMPTY_SUCCESS"
    return {
        "boundary": boundary.id,
        "fault": fault,
        "classification": result.classification,
        "empty_success": empty_success,
        "code_path": CODE_PATH if client is fetch_fail_closed else SWALLOW_PATH,
        "detail": result.detail[:240],
        "staging_bytes": result.staging_bytes,
        "committed_unchanged": after == seed_sha,
        "staging_promoted": result.staging_promoted,
        "ok": result.ok,
        "exception_type": result.exception_type,
    }


def run_matrix(work: Path | None = None) -> list[dict]:
    root = work or Path("/tmp/tst-0098-matrix")
    root.mkdir(parents=True, exist_ok=True)
    cells = []
    for boundary in BOUNDARIES:
        for fault in FAULTS:
            cells.append(run_one(boundary, fault, root))
    return cells


def run_healthy(work: Path | None = None) -> list[dict]:
    root = work or Path("/tmp/tst-0098-healthy")
    root.mkdir(parents=True, exist_ok=True)
    return [run_one(b, "healthy", root) for b in BOUNDARIES]


def run_swallower_control(work: Path | None = None) -> dict:
    root = work or Path("/tmp/tst-0098-swallow")
    root.mkdir(parents=True, exist_ok=True)
    return run_one(
        BOUNDARIES[0],
        "dns_failure",
        root,
        client=planted_empty_success_swallower,
    )


_NET_IMPORT_ROOTS = frozenset(
    {"urllib", "httpx", "aiohttp", "requests", "httplib"}
)


def _python_imports_http_client(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return bool(NET_API_RE.search(text))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            root = name.split(".", 1)[0]
            if name.startswith("http.client") or root in _NET_IMPORT_ROOTS:
                return True
            if name == "http" or (root == "http" and name != "http.server"):
                # "import http.client" is ImportFrom module=http.client; skip
                # a denylist string. Only treat real http.client imports.
                continue
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "urllib" and node.attr == "request":
                return True
    return False


def inventory_live_tree() -> dict:
    hits: list[dict] = []
    skip_bits = (
        "/p2-wave/probes/",
        "/__pycache__/",
        "/.git/",
    )
    roots = [REPO / "tools", REPO / "command-center"]
    scanned = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".mjs", ".js", ".ts", ".go"}:
                continue
            rel = path.relative_to(REPO).as_posix()
            if any(b in f"/{rel}" for b in skip_bits):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if path.suffix.lower() == ".py":
                if _python_imports_http_client(text):
                    hits.append({"path": rel, "kind": "python-http-import"})
            elif NET_API_RE.search(text):
                hits.append({"path": rel, "kind": "source-net-api"})
    return {
        "files_scanned": scanned,
        "product_http_clients": hits,
        "product_http_client_count": len(hits),
        "note": (
            "String denylists (e.g. telemetry/netaudit.py FORBIDDEN_MODULES) "
            "are not clients; only import/call sites count."
        ),
    }


def matrix_ok(cells: list[dict]) -> tuple[bool, str]:
    if len(cells) != len(BOUNDARIES) * len(FAULTS):
        return False, f"cell_count={len(cells)}"
    for cell in cells:
        want = TYPED[cell["fault"]]
        if cell["empty_success"] or cell["classification"] == "EMPTY_SUCCESS":
            return False, f"empty_success {cell['boundary']} x {cell['fault']}"
        if cell["classification"] != want:
            return False, (
                f"{cell['boundary']} x {cell['fault']} got "
                f"{cell['classification']} want {want} ({cell.get('detail')})"
            )
        if cell["ok"]:
            return False, f"ok-true on fault {cell['boundary']} x {cell['fault']}"
    return True, "all-typed"


def partial_ok(cells: list[dict]) -> tuple[bool, str]:
    for cell in cells:
        if not cell["committed_unchanged"]:
            return False, f"committed mutated {cell['boundary']} x {cell['fault']}"
        if cell["staging_promoted"]:
            return False, f"staging promoted {cell['boundary']} x {cell['fault']}"
        if cell["fault"] in {"truncated_response", "mid_stream_disconnect"}:
            if cell["staging_bytes"] <= 0:
                return False, f"no staging bytes {cell['boundary']} x {cell['fault']}"
    return True, "partial-preserved"


if __name__ == "__main__":
    cells = run_matrix()
    ok, why = matrix_ok(cells)
    print(json.dumps({"ok": ok, "why": why, "n": len(cells)}, indent=2))
    if not ok:
        for c in cells:
            if c["classification"] != TYPED[c["fault"]] or c["empty_success"]:
                print(c)
        raise SystemExit(1)
