"""Consumer call site for the ARC-0096 telemetry/privacy contract.

This module is the real caller the catalog reviewer_requirement asks for: it
loads command-center/phase4/contracts/ARC-0096.json and will not egress a
body the schema rejects. Probes observe sockets; they do not trust flags.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import jsonschema

from clauses import (
    CONTRACT_ID,
    CONTRACT_REL,
    SCHEMA_VERSION,
    UNIT_ID,
)

REPO = Path(__file__).resolve().parents[4]
CONTRACT_PATH = REPO / CONTRACT_REL
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

CANARY_PREFIX = "CANARY-ARC-0096-SECRET-"
CANARY_BODY = "00000000deadbeefcafebabe"
CANARY = CANARY_PREFIX + CANARY_BODY
HOME_UNIX = "/home/arc0096-owner/projects/secret-repo"
HOME_WIN = r"C:\Users\arc0096-owner\secret-repo"

ALLOW_LIST = frozenset(
    {
        "schema_version",
        "event_id",
        "ts",
        "unit_id",
        "contract_id",
        "event_kind",
        "outcome",
        "phase",
        "duration_ms",
        "probe_id",
        "host_os_family",
        "error_class",
    }
)
EVENT_KINDS = frozenset(
    {"probe", "lifecycle", "conformance", "heartbeat", "error"}
)
OUTCOMES = frozenset({"success", "fail", "skip"})
OS_FAMILIES = frozenset({"linux", "windows", "darwin"})

SECRET_RE = re.compile(
    r"(?:"
    + re.escape(CANARY_PREFIX)
    + r"[A-Za-z0-9_-]*"
    + r"|sk-[A-Za-z0-9]{8,}"
    + r"|ghp_[A-Za-z0-9]{8,}"
    + r"|xox[baprs]-[A-Za-z0-9-]{8,}"
    + r"|AKIA[0-9A-Z]{16}"
    + r"|(?i:(?:api[_-]?key|secret|password|token|authorization)\s*[:=]\s*\S+)"
    + r")"
)
ABS_PATH_RE = re.compile(
    r"(?:"
    r"/(?:home|Users)/[^\s\"']+"
    r"|[A-Za-z]:\\Users\\[^\s\"']+"
    r"|[A-Za-z]:/Users/[^\s\"']+"
    r")"
)
PERSONAL_RE = re.compile(
    r"(?:"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|(?i:\b(?:username|user_name|home_dir)\s*[:=]\s*\S+)"
    r")"
)
REDACT_SECRET = "[REDACTED-SECRET]"
REDACT_PATH = "[REDACTED-ABS-PATH]"
REDACT_PII = "[REDACTED-PERSONAL]"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_contract() -> dict:
    doc = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("contract is not an object")
    return doc


def validator():
    return jsonschema.Draft202012Validator(load_contract())


def load_decision_log(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("decision log is not an object")
    return doc


def opt_in_record(log: dict) -> dict | None:
    """Last telemetry-egress record wins. OPT-IN only if still in force."""
    chosen = None
    for rec in log.get("records") or []:
        if not isinstance(rec, dict):
            continue
        if rec.get("scope") != "telemetry-egress":
            continue
        if rec.get("decision") not in {"OPT-IN", "OPT-OUT", "REVOKED"}:
            continue
        chosen = rec
    if not isinstance(chosen, dict):
        return None
    if chosen.get("decision") != "OPT-IN":
        return None
    required = ("id", "ts", "owner", "destination_class")
    if any(not chosen.get(k) for k in required):
        return None
    if chosen.get("sandbox_only") is not True and chosen.get(
        "destination_class"
    ) != "sandbox-observer":
        # Production destinations still need the same fields; probes only
        # exercise sandbox-observer. Missing sandbox_only on a non-sandbox
        # class is accepted as a durable owner record shape.
        pass
    return chosen


def may_egress(policy: dict, log: dict) -> bool:
    if not policy.get("enabled"):
        return False
    return opt_in_record(log) is not None


def _scrub_string(value: str) -> str:
    value = SECRET_RE.sub(REDACT_SECRET, value)
    value = ABS_PATH_RE.sub(REDACT_PATH, value)
    value = PERSONAL_RE.sub(REDACT_PII, value)
    return value


def _walk_scrub(obj: Any) -> Any:
    if isinstance(obj, str):
        return _scrub_string(obj)
    if isinstance(obj, list):
        return [_walk_scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _walk_scrub(v) for k, v in obj.items()}
    return obj


def leak_scan(blob: str) -> list[str]:
    hits: list[str] = []
    win_json = HOME_WIN.replace("\\", "\\\\")
    if CANARY_PREFIX in blob or CANARY in blob:
        hits.append("canary-secret")
    if HOME_UNIX in blob:
        hits.append("home-unix")
    if HOME_WIN in blob or win_json in blob:
        hits.append("home-win")
    if SECRET_RE.search(blob):
        hits.append("secret-pattern")
    if ABS_PATH_RE.search(blob) or re.search(
        r"[A-Za-z]:\\\\Users\\\\", blob
    ):
        hits.append("abs-path")
    return hits


def prepare_event(raw: dict) -> dict:
    """Allow-list, scrub, then fail closed if a leak remains.

    Extra keys are dropped (scrub-by-stripping). Allow-listed string values
    are pattern-scrubbed. If the serialized event still contains a planted
    canary or absolute home path, the event is rejected.
    """
    if not isinstance(raw, dict):
        raise ValueError("event must be an object")
    cleaned = {k: raw[k] for k in ALLOW_LIST if k in raw}
    cleaned = _walk_scrub(cleaned)
    cleaned.setdefault("schema_version", SCHEMA_VERSION)
    cleaned.setdefault("contract_id", CONTRACT_ID)
    cleaned.setdefault("unit_id", UNIT_ID)
    cleaned.setdefault("event_id", str(uuid.uuid4()))
    cleaned.setdefault("ts", utc_now())
    blob = json.dumps(cleaned, ensure_ascii=True, sort_keys=True)
    leaks = leak_scan(blob)
    if leaks:
        raise PermissionError(f"rejected: leak remains after redaction {leaks}")
    errors = sorted(validator().iter_errors(cleaned), key=lambda e: list(e.path))
    if errors:
        msgs = [e.message for e in errors[:8]]
        raise PermissionError(f"rejected: schema {msgs}")
    return cleaned


def emit(
    raw: dict,
    policy: dict,
    log: dict,
    *,
    endpoint: str | None = None,
    local_dir: Path | None = None,
) -> dict:
    """Contract-faithful emit. No socket is opened unless may_egress is true."""
    if not policy.get("enabled"):
        return {
            "status": "DISABLED",
            "bytes_sent": 0,
            "local_written": False,
            "event": None,
        }
    try:
        event = prepare_event(raw)
    except PermissionError as exc:
        return {
            "status": "REJECTED",
            "bytes_sent": 0,
            "local_written": False,
            "event": None,
            "reason": str(exc),
        }
    local_written = False
    if policy.get("local_recording") and local_dir is not None:
        local_dir.mkdir(parents=True, exist_ok=True)
        path = local_dir / f"{event['event_id']}.json"
        path.write_text(
            json.dumps(event, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        local_written = True
    if not may_egress(policy, log):
        return {
            "status": "LOCAL-ONLY",
            "bytes_sent": 0,
            "local_written": local_written,
            "event": event,
        }
    if not endpoint:
        return {
            "status": "REJECTED",
            "bytes_sent": 0,
            "local_written": local_written,
            "event": event,
            "reason": "egress allowed but no endpoint",
        }
    body = json.dumps(event, ensure_ascii=True, sort_keys=True).encode("utf-8")
    req = Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    try:
        with urlopen(req, timeout=2) as resp:  # noqa: S310 - sandbox observer only
            resp.read()
    except URLError as exc:
        return {
            "status": "EGRESS-FAILED",
            "bytes_sent": 0,
            "local_written": local_written,
            "event": event,
            "reason": str(exc),
        }
    return {
        "status": "EGRESSED",
        "bytes_sent": len(body),
        "local_written": local_written,
        "event": event,
    }


class _HitHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        peer = self.client_address[0] if self.client_address else ""
        self.server.hits.append(  # type: ignore[attr-defined]
            {
                "method": "POST",
                "path": self.path,
                "bytes": len(body),
                "peer": peer,
                "body": body.decode("utf-8", errors="replace"),
            }
        )
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return


class SandboxObserver:
    """TCP/HTTP observer. Hits are real accepted connections, not config reads."""

    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _HitHandler)
        self.httpd.hits = []  # type: ignore[attr-defined]
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/telemetry"

    @property
    def hits(self) -> list[dict]:
        return list(self.httpd.hits)  # type: ignore[attr-defined]

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class ConnectCounter:
    """Counts socket.connect calls in this process (actual TCP attempts)."""

    def __init__(self) -> None:
        self.count = 0
        self._orig = socket.socket.connect
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return
        orig = self._orig
        counter = self

        def _hook(sock, address, *args, **kwargs):
            counter.count += 1
            return orig(sock, address, *args, **kwargs)

        socket.socket.connect = _hook  # type: ignore[method-assign]
        self._installed = True

    def remove(self) -> None:
        if not self._installed:
            return
        socket.socket.connect = self._orig  # type: ignore[method-assign]
        self._installed = False


def policy(*, enabled: bool, local_recording: bool = False) -> dict:
    return {
        "enabled": enabled,
        "local_recording": local_recording,
        "retention_days_local": 14,
        "egress_requires_opt_in": True,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
    }


def sample_event(**overrides: Any) -> dict:
    base = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "ts": utc_now(),
        "unit_id": UNIT_ID,
        "contract_id": CONTRACT_ID,
        "event_kind": "probe",
        "outcome": "success",
        "phase": "4",
        "duration_ms": 1,
        "probe_id": "probe1",
        "host_os_family": "linux",
        "error_class": "NONE",
    }
    base.update(overrides)
    return base
