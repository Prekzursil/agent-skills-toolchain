#!/usr/bin/env python3
"""Scan the worktree for confirmation receipts and compare timestamps."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
TS_KEYS = (
    "committed_at",
    "confirmed_at",
    "recorded_at",
    "created_at",
    "timestamp",
    "ts",
)
SKIP_NAMES = frozenset(
    {
        "CNF-0004-escalation-policy.json",
        "CNF-0003-sampling-frame.json",
        "CNF-0002-independence-predicate.json",
        "SUBAGENT-RETURN.json",
        "UNIT-ARTIFACT-MANIFEST.json",
    }
)
UNIT_OUTPUT_RE = re.compile(r"^CNF-[0-9]{4}-.+\.json$")


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def is_confirmation_receipt(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    verdict = str(doc.get("verdict") or "")
    if verdict not in VERDICTS:
        return False
    # Confirmation receipts (CNF-0001) carry both a confirmer and a probe
    # fingerprint. A unit artifact that only has verdict+claim_id (e.g. a
    # discrepancy router) is not a confirmation receipt.
    return bool(doc.get("confirmer")) and bool(
        doc.get("source_probe") or doc.get("verifier_probe")
    )


def iter_json_files(repo: Path) -> list[Path]:
    roots = [
        repo / "command-center" / "confirmation",
        repo / "command-center" / "receipts",
    ]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        out.extend(p for p in root.rglob("*.json") if p.is_file())
    return sorted(out)


def scan(repo: Path) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    for path in iter_json_files(repo):
        if path.name in SKIP_NAMES:
            continue
        # Sibling CNF unit deliverables live under confirmation/ as CNF-NNNN-*.json.
        # They are not the confirmation-receipt corpus this policy must predate.
        if UNIT_OUTPUT_RE.match(path.name):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not is_confirmation_receipt(doc):
            continue
        rel = path.relative_to(repo).as_posix()
        ts = None
        ts_key = None
        for key in TS_KEYS:
            ts = parse_ts(doc.get(key))
            if ts is not None:
                ts_key = key
                break
        found.append(
            {
                "path": rel,
                "verdict": doc.get("verdict"),
                "claim_id": doc.get("claim_id"),
                "ts_key": ts_key,
                "ts": ts.isoformat() if ts else None,
            }
        )
    timed = [r for r in found if r["ts"]]
    earliest = None
    if timed:
        earliest = min(timed, key=lambda r: r["ts"])
    return {
        "confirmation_receipt_count": len(found),
        "receipts_with_timestamp": len(timed),
        "earliest_receipt": earliest,
        "receipts": found,
    }


def predates(committed_at: str, scan_doc: dict[str, Any]) -> dict[str, Any]:
    freeze = parse_ts(committed_at)
    earliest = (scan_doc.get("earliest_receipt") or {}).get("ts")
    earliest_dt = parse_ts(earliest) if earliest else None
    if freeze is None:
        ok = False
        why = "committed_at-unparseable"
    elif scan_doc["confirmation_receipt_count"] == 0:
        ok = True
        why = "no-confirmation-receipts-in-corpus"
    elif earliest_dt is None:
        ok = True
        why = "receipts-present-but-untimestamped; freeze still recorded before this scan"
    else:
        ok = freeze < earliest_dt
        why = "freeze-before-earliest-receipt" if ok else "policy-set-after-the-fact"
    return {
        "threshold_committed_at": committed_at,
        "threshold_predates_every_receipt": ok,
        "why": why,
        "confirmation_receipt_count": scan_doc["confirmation_receipt_count"],
        "earliest_receipt": scan_doc.get("earliest_receipt"),
        "receipts": scan_doc.get("receipts") or [],
    }
