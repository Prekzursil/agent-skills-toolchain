"""SYN-0019-style blocking manifest gate used by the SYN-0041 writer.

The gate is existence + non-empty + minimum size + JSON parse + content hash,
with a freshness window. A stale or missing receipt must not authorise a write
unless the gate is re-run against live bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

WINDOW_SECONDS = 600
MIN_BYTES = 1
GATE_NAME = "SYN-0019-manifest-gate"
GATE_PATHS = [
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/schema/final-report.schema.json",
]
GATE_RECEIPT_REL = "command-center/p2-wave/probes/SYN-0041/_gate-receipt.json"


class GateBlocked(Exception):
    def __init__(self, reason: str, receipt: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.receipt = receipt or {}


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def verify_entries(root: Path, relpaths: list[str] | None = None, *, min_bytes: int = MIN_BYTES) -> dict[str, Any]:
    rels = list(relpaths or GATE_PATHS)
    rows: list[dict[str, Any]] = []
    blocked: list[str] = []
    for rel in rels:
        path = root / rel
        row: dict[str, Any] = {
            "path": rel,
            "present": path.is_file(),
            "bytes": 0,
            "sha256": "",
            "parse_verdict": "ABSENT",
        }
        if not path.is_file():
            blocked.append(f"missing:{rel}")
            rows.append(row)
            continue
        sha, n = digest_file(path)
        row["bytes"] = n
        row["sha256"] = sha
        if n < min_bytes:
            row["parse_verdict"] = "TOO-SMALL"
            blocked.append(f"truncated:{rel}")
            rows.append(row)
            continue
        if rel.endswith(".json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
                row["parse_verdict"] = "PARSE-OK"
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                row["parse_verdict"] = "PARSE-FAIL"
                blocked.append(f"unparseable:{rel}")
        else:
            row["parse_verdict"] = "NON-JSON-OK"
        rows.append(row)
    status = "BLOCKED" if blocked else "PERMITTED"
    return {
        "gate": GATE_NAME,
        "status": status,
        "blocked_reasons": blocked,
        "entries": rows,
        "freshness_window_seconds": WINDOW_SECONDS,
        "unit_id": "SYN-0041",
    }


def is_fresh(
    prior: dict[str, Any] | None,
    now: float,
    live: dict[str, Any] | None = None,
    *,
    window: int = WINDOW_SECONDS,
) -> tuple[bool, str]:
    if not isinstance(prior, dict):
        return False, "manifest-gate-absent"
    if str(prior.get("status") or "") != "PERMITTED":
        return False, "manifest-gate-not-permitted"
    ts = prior.get("verified_at_unix")
    if not isinstance(ts, (int, float)):
        return False, "manifest-gate-untimestamped"
    if now - float(ts) > window:
        return False, "manifest-gate-stale"
    if live is not None:
        prior_map = {
            str(e.get("path")): str(e.get("sha256") or "")
            for e in (prior.get("entries") or [])
            if isinstance(e, dict)
        }
        for e in live.get("entries") or []:
            if not isinstance(e, dict):
                continue
            rel = str(e.get("path") or "")
            if prior_map.get(rel) != str(e.get("sha256") or ""):
                return False, f"manifest-gate-hash-mismatch:{rel}"
    return True, "ok"


def load_receipt(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        val = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return val if isinstance(val, dict) else None


def authorize_write(
    root: Path,
    now: float,
    *,
    rerun: bool,
    receipt_path: Path | None = None,
    relpaths: list[str] | None = None,
) -> dict[str, Any]:
    """Permit a report write.

    rerun=True: re-verify live bytes (production path). Stale cache is ignored.
    rerun=False: a cached receipt must be PERMITTED, within the window, and
    hash-match live bytes. This is the control the staleness test exercises.
    """
    receipt_path = receipt_path or (root / GATE_RECEIPT_REL)
    live = verify_entries(root, relpaths)
    if rerun:
        if live["status"] != "PERMITTED":
            reasons = ",".join(live.get("blocked_reasons") or ["unknown"])
            raise GateBlocked(f"manifest-gate-blocked:{reasons}", live)
        stamped = dict(live)
        stamped["verified_at_unix"] = now
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(stamped, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return stamped
    prior = load_receipt(receipt_path)
    ok, why = is_fresh(prior, now, live)
    if not ok:
        raise GateBlocked(why, prior or live)
    assert prior is not None
    return prior


def projection(receipt: dict[str, Any]) -> dict[str, Any]:
    """Deterministic gate table attached to the report (no wall-clock)."""
    entries = []
    for e in receipt.get("entries") or []:
        if not isinstance(e, dict):
            continue
        entries.append(
            {
                "path": e.get("path"),
                "bytes": e.get("bytes"),
                "sha256": e.get("sha256"),
                "parse_verdict": e.get("parse_verdict"),
            }
        )
    return {
        "gate": GATE_NAME,
        "status": receipt.get("status"),
        "receipt_attached": True,
        "freshness_window_seconds": WINDOW_SECONDS,
        "entries": entries,
    }
