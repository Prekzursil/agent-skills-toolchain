#!/usr/bin/env python3
"""CNF-0115 live egress measurement.

Two instruments (socket.connect vs socket.create_connection; optional strace)
capture outbound TCP during (1) a declared telemetry-event control, (2) an
undeclared well-known-service plant, and (3) a representative local run of
this worktree. Payload bytes are inspected for a user-content marker and then
discarded; they are never returned.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PHASE4 = REPO / "command-center" / "phase4" / "contracts" / "ARC-0096.json"
ART = REPO / "command-center" / "confirmation" / "CNF-0115-egress-measurement.json"
SCHEMA = REPO / "command-center" / "schema" / "privacy-report.schema.json"

DECLARED_EVENT_ID = "CNF0115_DECLARED_EVENT"
MARKER_ID = "CNF0115_USER_CONTENT_CANARY"
# Full needle lives only in this module. The confirmation artifact names MARKER_ID
# and must not contain this needle (that would be a stored payload).
USER_MARKER = "CNF0115_USER_CONTENT_CANARY|DO_NOT_TRANSMIT"
WELL_KNOWN_PLANT_HOST = "pypi.org"
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "payload",
        "raw_payload",
        "body",
        "packet",
        "wire_bytes",
        "request_body",
        "captured_payload",
        "captured_bytes",
        "hex_dump",
        "raw_bytes",
        "request_payload",
        "response_body",
    }
)
SENTINEL = (
    "SUCCESS:CNF-0115 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the declared-event "
    "control was observed in the capture and no captured payload bytes are "
    "stored in the artifact. Any other terminal state is FAILED:CNF-0115 "
    "<classification> with the diagnostic tail attached."
)
CONTRACT_UNITS = ("ARC-0096", "IMP-0057", "IMP-0479", "CNF-0115")
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0115/probe1_socket_capture.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0115/probe2_independent_capture.py"
)


def _host_port(address: Any) -> tuple[str, int] | None:
    if isinstance(address, (tuple, list)) and len(address) >= 2:
        try:
            return str(address[0]), int(address[1])
        except (TypeError, ValueError):
            return None
    return None


def _marker_in(data: Any) -> bool:
    if isinstance(data, (bytes, bytearray, memoryview)):
        return USER_MARKER.encode("ascii") in bytes(data)
    if isinstance(data, str):
        return USER_MARKER in data
    return False


class Sink:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = int(self.sock.getsockname()[1])
        self.stop = threading.Event()
        self.connections = 0
        self.bytes = 0
        self.marker_hits = 0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.connections += 1
            try:
                conn.settimeout(0.5)
                hit = False
                while True:
                    try:
                        chunk = conn.recv(1024)
                    except (TimeoutError, OSError):
                        break
                    if not chunk:
                        break
                    self.bytes += len(chunk)
                    if USER_MARKER.encode("ascii") in chunk:
                        hit = True
                if hit:
                    self.marker_hits += 1
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
        try:
            self.sock.close()
        except OSError:
            pass

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=2)


class BaseCapture:
    def __init__(self) -> None:
        self.phase = "idle"
        self.intended_host: str | None = None
        self.rows: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._orig: dict[str, Any] = {}

    def _note_connect(
        self, host: str, port: int, result: str, peer: str | None = None
    ) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "host": self.intended_host or host,
            "peer": peer or host,
            "port": port,
            "phase": self.phase,
            "result": result,
            "byte_volume": 0,
            "user_content_marker_present": False,
            "connection_count": 1,
        }
        with self._lock:
            self.rows.append(rec)
        return rec

    def install(self) -> None:
        raise NotImplementedError

    def restore(self) -> None:
        for name, orig in self._orig.items():
            setattr(socket, name, orig)
        self._orig.clear()


class SocketConnectCapture(BaseCapture):
    """Instrument 1: subclass socket.socket and intercept connect/send.

    CPython's socket.socket methods are C slots and cannot be assigned; replacing
    the constructor with a subclass is the load-bearing hook.
    """

    def install(self) -> None:
        orig_socket = socket.socket
        capture = self
        self._orig = {"socket": orig_socket}

        class Wrapped(orig_socket):  # type: ignore[valid-type,misc]
            def connect(self, address: Any) -> None:
                if self.family not in (socket.AF_INET, socket.AF_INET6):
                    return orig_socket.connect(self, address)
                hp = _host_port(address)
                if hp is None:
                    return orig_socket.connect(self, address)
                host, port = hp
                try:
                    orig_socket.connect(self, address)
                except Exception as exc:
                    capture._note_connect(host, port, type(exc).__name__)
                    raise
                peer = host
                try:
                    pn = self.getpeername()
                    if isinstance(pn, tuple) and pn:
                        peer = str(pn[0])
                except OSError:
                    pass
                rec = capture._note_connect(host, port, "connected", peer=peer)
                setattr(self, "_cnf0115_rec", rec)

            def connect_ex(self, address: Any) -> int:
                if self.family not in (socket.AF_INET, socket.AF_INET6):
                    return orig_socket.connect_ex(self, address)
                hp = _host_port(address)
                if hp is None:
                    return orig_socket.connect_ex(self, address)
                host, port = hp
                rc = orig_socket.connect_ex(self, address)
                result = "connected" if rc == 0 else f"connect_ex:{rc}"
                rec = capture._note_connect(host, port, result)
                if rc == 0:
                    setattr(self, "_cnf0115_rec", rec)
                return rc

            def send(self, data: Any, *a: Any, **k: Any) -> int:
                rec = getattr(self, "_cnf0115_rec", None)
                if isinstance(rec, dict):
                    rec["byte_volume"] += len(data) if data is not None else 0
                    if _marker_in(data):
                        rec["user_content_marker_present"] = True
                return orig_socket.send(self, data, *a, **k)

            def sendall(self, data: Any, *a: Any, **k: Any) -> None:
                rec = getattr(self, "_cnf0115_rec", None)
                if isinstance(rec, dict):
                    rec["byte_volume"] += len(data) if data is not None else 0
                    if _marker_in(data):
                        rec["user_content_marker_present"] = True
                return orig_socket.sendall(self, data, *a, **k)

        socket.socket = Wrapped  # type: ignore[misc]

    def restore(self) -> None:
        if "socket" in self._orig:
            socket.socket = self._orig["socket"]
        self._orig.clear()


class CreateConnectionCapture(BaseCapture):
    """Instrument 2: wrap socket.create_connection (urllib/http.client layer)."""

    def install(self) -> None:
        orig = socket.create_connection
        self._orig = {"create_connection": orig}
        capture = self

        def create_connection(address: Any, *a: Any, **k: Any) -> socket.socket:
            hp = _host_port(address)
            host, port = hp if hp else (str(address), 0)
            try:
                sock = orig(address, *a, **k)
            except Exception as exc:
                capture._note_connect(host, port, type(exc).__name__)
                raise
            peer = host
            try:
                pn = sock.getpeername()
                if isinstance(pn, tuple) and pn:
                    peer = str(pn[0])
            except OSError:
                pass
            rec = capture._note_connect(host, port, "connected", peer=peer)
            rec["_sock_id"] = id(sock)
            return sock

        socket.create_connection = create_connection  # type: ignore[assignment]


def emit_declared(port: int) -> None:
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        sock.sendall(DECLARED_EVENT_ID.encode("ascii"))
    finally:
        sock.close()


def emit_undeclared_plant(port: int) -> None:
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        sock.sendall(USER_MARKER.encode("ascii") + b"|plant")
    finally:
        sock.close()


def representative_workload() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = None
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == "CNF-0115":
            unit = row
            break
    tools = REPO / "tools" / "command-center"
    fields = 0
    imported = False
    if tools.is_dir():
        sys.path.insert(0, str(tools))
        import catalog as cc_catalog  # type: ignore  # noqa: E402

        fields = len(cc_catalog.WORK_UNIT_FIELDS)
        imported = True
    return {
        "unit_found": unit is not None,
        "output_path": (unit or {}).get("output_path"),
        "catalog_fields": fields,
        "catalog_imported": imported,
        "worktree_surface": "command-center+tools (plugin/platform telemetry absent)",
    }


def implementation_census() -> dict[str, Any]:
    hits: list[str] = []
    skip_bits = (
        "/probes/CNF-0115/",
        "/WORK-UNIT-CATALOG.json",
        "/CNF-0115-egress-measurement.json",
        "/privacy-report.schema.json",
    )
    for root in (REPO / "tools", REPO / "command-center"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            rel = path.as_posix()
            if any(b in rel for b in skip_bits):
                continue
            name = path.name.lower()
            if "telemetry" in name or "privacy" in name:
                hits.append(str(path.relative_to(REPO)).replace("\\", "/"))
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"\btelemetry\b", text, re.I) and "egress" in text.lower():
                hits.append(str(path.relative_to(REPO)).replace("\\", "/"))
    hits = sorted(set(hits))[:40]
    return {
        "present": bool(hits),
        "telemetry_modules_in_worktree": hits,
        "plugin_tree_present": (REPO / "plugin").is_dir(),
        "platform_tree_present": (REPO / "platform").is_dir(),
        "phase4_contract_present": PHASE4.is_file(),
    }


def _arc0096_clauses() -> dict[str, str]:
    path = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0096" / "clauses.py"
    if not path.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("cnf0115_arc0096_clauses", path)
    if spec is None or spec.loader is None:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    keys = (
        "EGRESS_RULE",
        "DISABLED_RULE",
        "LOCAL_VS_EGRESS",
        "REDACTION_RULE",
        "RETENTION_RULE",
        "OPT_IN_RULE",
        "RECORDABLE_RULE",
        "OBSERVATION_RULE",
    )
    out: dict[str, str] = {}
    for key in keys:
        val = getattr(mod, key, None)
        if isinstance(val, str) and val.strip():
            out[key.lower()] = val
    return out


def extract_contract() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    sourced: dict[str, Any] = {}
    for row in data.get("work_units") or []:
        uid = row.get("id")
        if uid in CONTRACT_UNITS:
            sourced[uid] = {
                "title": row.get("title"),
                "question_or_target": row.get("question_or_target"),
                "tests_required": row.get("tests_required"),
                "output_path": row.get("output_path"),
            }
    clauses = _arc0096_clauses()
    return {
        "source_units": list(CONTRACT_UNITS),
        "sourced_from_catalog": sourced,
        "phase4_artifact_path": "command-center/phase4/contracts/ARC-0096.json",
        "phase4_artifact_present": PHASE4.is_file(),
        "arc0096_clauses_module": (
            "command-center/p2-wave/probes/ARC-0096/clauses.py"
            if clauses
            else None
        ),
        "normative_clauses": clauses,
        "default_mode": "local-only",
        "declared_destinations": [],
        "opt_in_required": True,
        "never_transmit": [
            "user_content",
            "file_contents",
            "prompts",
            "absolute_paths",
        ],
        "owner_opt_in_recorded": False,
        "extraction_note": (
            "Phase-4 ARC-0096 JSON is absent on this worktree. Rules are taken "
            "from catalog units ARC-0096, IMP-0057, IMP-0479, CNF-0115 plus the "
            "normative clause strings in probes/ARC-0096/clauses.py when that "
            "file is present: default nothing leaves; opt-in required; user "
            "content is never transmitted. The capture-control sink is declared "
            "only for the opt-in control phase."
        ),
        "control_sink_declaration": {
            "host": "127.0.0.1",
            "role": "opt-in declared telemetry event sink used only for capture-liveness control",
        },
    }


def classify_rows(
    rows: list[dict[str, Any]], declared_port: int, undeclared_port: int
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        phase = row.get("phase")
        port = int(row.get("port") or 0)
        if phase == "control-declared" or port == declared_port:
            row["declared"] = True
            row["classification"] = "declared"
            row["well_known_service"] = False
            row["phase"] = "control-declared"
        elif phase == "control-undeclared" or port == undeclared_port:
            row["declared"] = False
            row["classification"] = "undeclared-egress"
            row["well_known_service"] = True
            row["host"] = WELL_KNOWN_PLANT_HOST
            row["phase"] = "control-undeclared"
        elif phase == "representative-run":
            row["declared"] = False
            row["classification"] = "undeclared-egress"
            row["well_known_service"] = False
        else:
            row["declared"] = False
            row["classification"] = "undeclared-egress"
        # Drop any accidental large buffers if a future hook attached them.
        row.pop("payload", None)
        row.pop("data", None)
        row.pop("bytes_sent", None)
        out.append(row)
    return out


def public_destinations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pub = []
    for row in rows:
        pub.append(
            {
                "host": row.get("host"),
                "peer": row.get("peer"),
                "port": int(row.get("port") or 0),
                "phase": row.get("phase"),
                "connection_count": int(row.get("connection_count") or 1),
                "byte_volume": int(row.get("byte_volume") or 0),
                "declared": bool(row.get("declared")),
                "classification": row.get("classification"),
                "result": row.get("result"),
                "user_content_marker_present": bool(
                    row.get("user_content_marker_present")
                ),
                "well_known_service": bool(row.get("well_known_service")),
            }
        )
    return pub


def run(instrument: str) -> dict[str, Any]:
    if instrument not in {"socket", "create_connection"}:
        raise ValueError(instrument)
    cap: BaseCapture = (
        SocketConnectCapture() if instrument == "socket" else CreateConnectionCapture()
    )
    declared = Sink()
    undeclared = Sink()
    workload: dict[str, Any] = {}
    try:
        cap.install()
        cap.phase = "control-declared"
        cap.intended_host = None
        emit_declared(declared.port)
        cap.phase = "control-undeclared"
        cap.intended_host = WELL_KNOWN_PLANT_HOST
        emit_undeclared_plant(undeclared.port)
        cap.intended_host = None
        cap.phase = "representative-run"
        workload = representative_workload()
        cap.phase = "idle"
        time.sleep(0.2)
    finally:
        cap.restore()
        declared.close()
        undeclared.close()
    rows = classify_rows(cap.rows, declared.port, undeclared.port)
    for row in rows:
        if row.get("phase") == "control-declared":
            row["byte_volume"] = max(int(row.get("byte_volume") or 0), int(declared.bytes))
            if declared.marker_hits:
                row["user_content_marker_present"] = True
        elif row.get("phase") == "control-undeclared":
            row["byte_volume"] = max(int(row.get("byte_volume") or 0), int(undeclared.bytes))
            if undeclared.marker_hits:
                row["user_content_marker_present"] = True
    dest = public_destinations(rows)
    declared_rows = [d for d in dest if d["phase"] == "control-declared"]
    plant_rows = [d for d in dest if d["phase"] == "control-undeclared"]
    live_rows = [d for d in dest if d["phase"] == "representative-run"]
    control_seen = any(
        d["result"] == "connected" and d["port"] == declared.port for d in declared_rows
    )
    plant_seen = any(d["result"] == "connected" for d in plant_rows)
    plant_marker = any(d["user_content_marker_present"] for d in plant_rows) or (
        undeclared.marker_hits > 0
    )
    declared_marker = any(d["user_content_marker_present"] for d in declared_rows) or (
        declared.marker_hits > 0
    )
    return {
        "instrument": instrument,
        "declared_port": declared.port,
        "undeclared_port": undeclared.port,
        "sink_declared_connections": declared.connections,
        "sink_undeclared_connections": undeclared.connections,
        "sink_undeclared_marker_hits": undeclared.marker_hits,
        "declared_event_observed": bool(control_seen and declared.connections >= 1),
        "undeclared_plant_observed": bool(plant_seen),
        "declared_event_contained_user_content": bool(declared_marker),
        "undeclared_plant_contained_user_content": bool(plant_marker),
        "destinations": dest,
        "representative_run": workload,
        "representative_run_undeclared": live_rows,
    }


def strace_declared_control() -> dict[str, Any]:
    sink = Sink()
    log_path = None
    try:
        fd, log_path = tempfile.mkstemp(prefix="cnf0115-strace-")
        os.close(fd)
        script = (
            "import socket\n"
            f"s = socket.create_connection(('127.0.0.1', {sink.port}), timeout=2)\n"
            "s.sendall(b'CNF0115_DECLARED_EVENT')\n"
            "s.close()\n"
        )
        proc = subprocess.run(
            [
                "strace",
                "-f",
                "-e",
                "trace=connect",
                "-o",
                log_path,
                sys.executable,
                "-c",
                script,
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=20,
        )
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
        observed = (
            f"htons({sink.port})" in text
            and "127.0.0.1" in text
            and "AF_INET" in text
        )
        return {
            "available": True,
            "rc": proc.returncode,
            "declared_event_observed": observed,
            "log_bytes": len(text),
            "ptrace_denied": "Operation not permitted" in (proc.stderr or "")
            or "PTRACE" in (proc.stderr or ""),
        }
    except FileNotFoundError:
        return {"available": False, "declared_event_observed": False}
    except subprocess.TimeoutExpired:
        return {"available": True, "declared_event_observed": False, "timeout": True}
    finally:
        sink.close()
        if log_path:
            try:
                os.unlink(log_path)
            except OSError:
                pass


def walk_forbidden(doc: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(doc, dict):
        for key, val in doc.items():
            here = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_PAYLOAD_KEYS:
                hits.append(here)
            hits.extend(walk_forbidden(val, here))
    elif isinstance(doc, list):
        for i, val in enumerate(doc):
            hits.extend(walk_forbidden(val, f"{path}[{i}]"))
    elif isinstance(doc, str):
        if USER_MARKER in doc:
            hits.append(path + ":marker-needle")
        if "|plant" in doc and "CNF0115" in doc:
            hits.append(path + ":plant-payload")
    elif isinstance(doc, (bytes, bytearray)):
        hits.append(path + ":bytes")
    return hits


def load_artifact() -> dict[str, Any]:
    return json.loads(ART.read_text(encoding="utf-8"))


def catalog_shim_ref() -> dict[str, Any]:
    """Inspect the catalog output_schema file. Never retrieve its $ref."""
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return {"present": False}
    try:
        shim = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"present": True, "parse_error": type(exc).__name__}
    ref = shim.get("$ref") if isinstance(shim, dict) else None
    host = None
    if isinstance(ref, str) and "://" in ref:
        try:
            host = ref.split("://", 1)[1].split("/", 1)[0]
        except IndexError:
            host = None
    return {
        "present": True,
        "path": "command-center/schema/privacy-report.schema.json",
        "ref": ref if isinstance(ref, str) else None,
        "ref_is_https": isinstance(ref, str) and ref.startswith("https://"),
        "ref_host": host,
        "generated_shim": True,
        "pipeline_retrieves_ref": False,
    }


def discriminating_schema() -> dict[str, Any]:
    """Local schema that discriminates this unit without a network $ref.

    Stock jsonschema 4.10 Draft7Validator against the catalog shim follows
    https://ast-integrate.invalid/... over HTTPS (undeclared egress). This
    unit's measurement pipeline must not do that. The discriminator encodes
    the two load-bearing constants named in emit_report: payload_bytes_stored
    is false, and the declared-event control was observed.
    """
    return {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "payload_bytes_stored",
            "capture_control",
            "payload_inspection",
            "destinations",
        ],
        "properties": {
            "unit_id": {"const": "CNF-0115"},
            "state": {"const": "SUCCESS"},
            "payload_bytes_stored": {"const": False},
            "capture_control": {
                "type": "object",
                "required": ["declared_event_observed"],
                "properties": {"declared_event_observed": {"const": True}},
            },
            "payload_inspection": {
                "type": "object",
                "required": ["captured_payload_stored"],
                "properties": {"captured_payload_stored": {"const": False}},
            },
            "destinations": {"type": "array", "minItems": 1},
        },
    }


def validate_schema(doc: dict[str, Any]) -> list[str]:
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return ["catalog-output-schema-absent"]
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-missing"]
    try:
        validator = jsonschema.Draft7Validator(discriminating_schema())
        errs = [
            f"{'/'.join(str(p) for p in e.path)}: {e.message}"
            for e in validator.iter_errors(doc)
        ]
        for garbage in (
            {},
            {"totally": "unrelated"},
            {"unit_id": "CNF-0115", "state": "SUCCESS"},
        ):
            if not list(validator.iter_errors(garbage)):
                errs.append("schema-accepts-garbage")
                break
        shim = catalog_shim_ref()
        if not shim.get("present"):
            errs.append("catalog-shim-absent")
        elif not shim.get("ref"):
            errs.append("catalog-shim-missing-$ref")
        return errs
    except Exception as exc:  # noqa: BLE001 - must never raise into a named probe
        return [f"schema-validate-exception:{type(exc).__name__}"]


def assert_artifact_honest(doc: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{doc.get('state')}")
    text = json.dumps(doc, sort_keys=True)
    if SENTINEL not in text:
        errs.append("sentinel-absent")
    if doc.get("payload_bytes_stored") is not False:
        errs.append("payload_bytes_stored")
    insp = doc.get("payload_inspection") or {}
    if insp.get("captured_payload_stored") is not False:
        errs.append("captured_payload_stored")
    ctrl = doc.get("capture_control") or {}
    if ctrl.get("declared_event_observed") is not True:
        errs.append("declared-event-not-observed-in-artifact")
    errs.extend(f"forbidden:{h}" for h in walk_forbidden(doc))
    return errs


def require_live(result: dict[str, Any], label: str) -> None:
    if not result.get("declared_event_observed"):
        raise SystemExit(f"FAILED:CNF-0115 capture-incomplete {label} declared-event-unseen")
    if not result.get("undeclared_plant_observed"):
        raise SystemExit(f"FAILED:CNF-0115 detector-failure {label} undeclared-plant-unseen")
    if result.get("declared_event_contained_user_content"):
        raise SystemExit(f"FAILED:CNF-0115 contract-violation {label} declared-event-carried-user-content")
    if not result.get("undeclared_plant_contained_user_content"):
        raise SystemExit(
            f"FAILED:CNF-0115 detector-failure {label} user-content-marker-silent-on-plant"
        )


def catalog_question() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for row in data.get("work_units") or []:
        if row.get("id") == "CNF-0115":
            return str(row.get("question_or_target") or "")
    raise SystemExit("FAILED:CNF-0115 catalog-missing CNF-0115")
