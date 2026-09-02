#!/usr/bin/env python3
"""Decay-aware vulnerability gate.

A scan result is a query against a live advisory database. Last week's green
says nothing about today's advisory set.

Three properties:
  1. Re-run the scanner against the exact artifact hash at promotion.
  2. Record advisory-database snapshot id and timestamp in the receipt.
  3. Refuse to consume any stored result older than the declared window.
     The refusal is a log row, not silence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from scanner import (
    SCANNER_BACKEND,
    SCANNER_NAME,
    SCANNER_PIN,
    ScanResult,
    lf_bytes,
    scan_artifact,
    sha256_bytes,
)

WINDOW_SECONDS_DEFAULT = 24 * 60 * 60


def format_ts(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def snapshot_id_for(content_bytes: bytes, pulled_at: str) -> str:
    """Unique per pull. Reusing a cached pull reuses the id and fails freshness."""
    h = hashlib.sha256()
    h.update(lf_bytes(content_bytes))
    h.update(b"|")
    h.update(pulled_at.encode("utf-8"))
    return h.hexdigest()


@dataclass
class AdvisorySnapshot:
    advisories: list[dict[str, Any]]
    pulled_at: str
    source: str
    content_bytes: bytes
    content_sha256: str
    snapshot_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "pulled_at": self.pulled_at,
            "source": self.source,
            "content_sha256": self.content_sha256,
            "advisory_count": len(self.advisories),
        }


def pull_advisory_db(
    advisories: list[dict[str, Any]],
    *,
    pulled_at: datetime,
    source: str = "fixture-advisory-mirror",
) -> AdvisorySnapshot:
    """Re-pull assigns a new snapshot id even when advisory bytes are unchanged."""
    payload = {
        "source": source,
        "advisories": advisories,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    pulled = format_ts(pulled_at)
    return AdvisorySnapshot(
        advisories=list(advisories),
        pulled_at=pulled,
        source=source,
        content_bytes=raw,
        content_sha256=sha256_bytes(raw),
        snapshot_id=snapshot_id_for(raw, pulled),
    )


def evaluate_stored(
    stored: dict[str, Any] | None,
    *,
    artifact_sha256: str,
    now: datetime,
    window_seconds: int,
) -> dict[str, Any]:
    """Refuse stale or mismatched stored results. Refusal is appended to the log."""
    log: list[dict[str, Any]] = []
    now_s = format_ts(now)
    if not stored:
        log.append(
            {
                "event": "no-stored-result",
                "reason": "first-scan",
                "now": now_s,
                "artifact_sha256": artifact_sha256,
            }
        )
        return {
            "action": "scan",
            "reason": "no-stored-result",
            "refused": False,
            "log": log,
        }

    stored_ts = str(stored.get("scan_timestamp") or "")
    stored_hash = str(stored.get("artifact_sha256") or "")
    log.append(
        {
            "event": "stored-result-presented",
            "stored_timestamp": stored_ts,
            "now": now_s,
            "artifact_sha256": stored_hash,
            "window_length_seconds": window_seconds,
        }
    )
    if stored_hash != artifact_sha256:
        log.append(
            {
                "event": "REFUSED",
                "reason": "artifact-hash-mismatch",
                "got": stored_hash,
                "expected": artifact_sha256,
                "now": now_s,
            }
        )
        log.append(
            {
                "event": "forced-rescan",
                "reason": "artifact-hash-mismatch",
                "artifact_sha256": artifact_sha256,
            }
        )
        return {
            "action": "scan",
            "reason": "artifact-hash-mismatch",
            "refused": True,
            "log": log,
        }

    age = int((now - parse_ts(stored_ts)).total_seconds())
    if age > window_seconds:
        log.append(
            {
                "event": "REFUSED",
                "reason": "stale-green",
                "classification": "stale-green",
                "age_seconds": age,
                "window_length_seconds": window_seconds,
                "stored_timestamp": stored_ts,
                "now": now_s,
                "artifact_sha256": artifact_sha256,
            }
        )
        log.append(
            {
                "event": "forced-rescan",
                "reason": "stale-green",
                "artifact_sha256": artifact_sha256,
            }
        )
        return {
            "action": "scan",
            "reason": "stale-green",
            "refused": True,
            "age_seconds": age,
            "log": log,
        }

    log.append(
        {
            "event": "stored-inside-window-not-consumed",
            "reason": "promotion-requires-live-rescan",
            "age_seconds": age,
            "window_length_seconds": window_seconds,
            "artifact_sha256": artifact_sha256,
        }
    )
    return {
        "action": "scan",
        "reason": "promotion-requires-live-rescan",
        "refused": False,
        "age_seconds": age,
        "log": log,
    }


def check_snapshot_freshness(
    this_snapshot_id: str, previous_snapshot_id: str | None
) -> dict[str, Any]:
    if previous_snapshot_id is None:
        return {"ok": True, "reason": "first-pull"}
    if this_snapshot_id == previous_snapshot_id:
        return {
            "ok": False,
            "reason": "reused-snapshot-id",
            "classification": "stale-green",
        }
    return {"ok": True, "reason": "distinct-snapshot-id"}


def promote(
    *,
    artifact_bytes: bytes,
    artifact_sha256: str,
    db: AdvisorySnapshot,
    now: datetime,
    stored: dict[str, Any] | None = None,
    window_seconds: int = WINDOW_SECONDS_DEFAULT,
    previous_snapshot_id: str | None = None,
    missing_tool: bool = False,
) -> dict[str, Any]:
    """Promotion-time re-scan. Never consumes a stale stored green."""
    actual = sha256_bytes(artifact_bytes)
    log: list[dict[str, Any]] = []
    now_s = format_ts(now)

    if actual != artifact_sha256:
        log.append(
            {
                "event": "REFUSED",
                "reason": "artifact-hash-mismatch",
                "got": actual,
                "expected": artifact_sha256,
                "now": now_s,
            }
        )
        return {
            "verdict": "REFUSED",
            "classification": "artifact-hash-mismatch",
            "consumed_stored": False,
            "rescanned": False,
            "freshness_ok": False,
            "artifact_sha256": actual,
            "expected_sha256": artifact_sha256,
            "snapshot_id": db.snapshot_id,
            "scan_timestamp": now_s,
            "window_length_seconds": window_seconds,
            "exit_code": 2,
            "findings": [],
            "promotion_log": log,
            "scanner": {
                "name": SCANNER_NAME,
                "pin": SCANNER_PIN,
                "backend": SCANNER_BACKEND,
            },
            "advisory_database": db.as_dict(),
        }

    stored_eval = evaluate_stored(
        stored,
        artifact_sha256=artifact_sha256,
        now=now,
        window_seconds=window_seconds,
    )
    log.extend(stored_eval["log"])

    freshness = check_snapshot_freshness(db.snapshot_id, previous_snapshot_id)
    if not freshness["ok"]:
        log.append(
            {
                "event": "REFUSED",
                "reason": "reused-snapshot-id",
                "classification": "stale-green",
                "snapshot_id": db.snapshot_id,
                "previous_snapshot_id": previous_snapshot_id,
                "now": now_s,
            }
        )
        return {
            "verdict": "REFUSED",
            "classification": "stale-green",
            "consumed_stored": False,
            "rescanned": False,
            "freshness_ok": False,
            "freshness_reason": freshness["reason"],
            "artifact_sha256": artifact_sha256,
            "snapshot_id": db.snapshot_id,
            "scan_timestamp": now_s,
            "window_length_seconds": window_seconds,
            "exit_code": 2,
            "findings": [],
            "promotion_log": log,
            "scanner": {
                "name": SCANNER_NAME,
                "pin": SCANNER_PIN,
                "backend": SCANNER_BACKEND,
            },
            "advisory_database": db.as_dict(),
        }

    scan: ScanResult = scan_artifact(
        artifact_bytes,
        artifact_sha256,
        db.advisories,
        missing_tool=missing_tool,
    )
    log.append(
        {
            "event": "scan-complete",
            "exit_code": scan.exit_code,
            "snapshot_id": db.snapshot_id,
            "timestamp": now_s,
            "artifact_sha256": artifact_sha256,
            "findings_count": len(scan.findings),
        }
    )
    return {
        "verdict": scan.classification,
        "classification": scan.classification,
        "error": scan.error,
        "consumed_stored": False,
        "rescanned": True,
        "stored_action": stored_eval["reason"],
        "stored_refused": bool(stored_eval.get("refused")),
        "freshness_ok": True,
        "freshness_reason": freshness["reason"],
        "artifact_sha256": artifact_sha256,
        "snapshot_id": db.snapshot_id,
        "scan_timestamp": now_s,
        "window_length_seconds": window_seconds,
        "exit_code": scan.exit_code,
        "findings": scan.findings,
        "promotion_log": log,
        "scanner": {
            "name": SCANNER_NAME,
            "pin": SCANNER_PIN,
            "backend": SCANNER_BACKEND,
        },
        "advisory_database": db.as_dict(),
    }


def log_has_refusal(log: list[dict[str, Any]], reason: str) -> bool:
    return any(
        row.get("event") == "REFUSED" and row.get("reason") == reason for row in log
    )
