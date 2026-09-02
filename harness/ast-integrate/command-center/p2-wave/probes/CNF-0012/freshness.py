#!/usr/bin/env python3
"""Confirmation freshness: TTL plus input-hash invalidation.

A stored CONFIRMED verdict is not a pass once any hashed input changes, once
the TTL expires, or when input hashes were never recorded. Missing hashes are
STALE by default (never CONFIRMED by omission). Advisory-class gates, whose
result can change with no code change, cannot stay CONFIRMED without a TTL.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

CLOSED_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED", "STALE"}
)
DEFAULT_TTL_SECONDS = 7 * 24 * 3600
ADVISORY_TTL_SECONDS = 24 * 3600

ReadBytes = Callable[[str], bytes | None]


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def recorded_hashes(receipt: dict) -> list[dict[str, str]] | None:
    raw = receipt.get("input_hashes")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        path = str(item.get("path") or "").strip()
        sha = str(item.get("sha256") or "").strip().lower()
        if not path or not sha:
            return None
        out.append({"path": path, "sha256": sha})
    return out


def evaluate_receipt(
    receipt: dict,
    *,
    now: datetime | None = None,
    read_bytes: ReadBytes | None = None,
) -> dict[str, Any]:
    """Return stored vs live verdict. Never upgrades a non-CONFIRMED stored value."""
    now = now or utcnow()
    stored = str(receipt.get("verdict") or receipt.get("stored_verdict") or "").upper()
    receipt_id = str(receipt.get("receipt_id") or receipt.get("id") or "")
    claim_id = str(receipt.get("claim_id") or "")
    reasons: list[str] = []
    comparisons: list[dict[str, Any]] = []

    if stored not in CLOSED_VERDICTS:
        reasons.append("unknown-stored-verdict")
        return _row(receipt_id, claim_id, stored or "UNKNOWN", "STALE", reasons, comparisons)

    hashes = recorded_hashes(receipt)
    advisory = bool(receipt.get("advisory_class") or receipt.get("unhashable_inputs"))
    ttl_raw = receipt.get("ttl_seconds")
    ttl: int | None
    if ttl_raw is None:
        ttl = None
    else:
        try:
            ttl = int(ttl_raw)
        except (TypeError, ValueError):
            ttl = -1

    if stored != "CONFIRMED":
        return _row(receipt_id, claim_id, stored, stored, ["stored-not-confirmed"], comparisons)

    if hashes is None or len(hashes) == 0:
        reasons.append("missing-input-hashes")
        return _row(receipt_id, claim_id, stored, "STALE", reasons, comparisons)

    reader = read_bytes or (lambda p: None)
    for item in hashes:
        path = item["path"]
        recorded = item["sha256"]
        blob = reader(path)
        if blob is None:
            reasons.append(f"input-missing:{path}")
            comparisons.append(
                {
                    "path": path,
                    "recorded_sha256": recorded,
                    "today_sha256": None,
                    "match": False,
                }
            )
            continue
        today = digest_bytes(blob)
        match = today == recorded
        comparisons.append(
            {
                "path": path,
                "recorded_sha256": recorded,
                "today_sha256": today,
                "match": match,
            }
        )
        if not match:
            reasons.append(f"input-hash-mismatch:{path}")

    if any(not c["match"] for c in comparisons):
        return _row(receipt_id, claim_id, stored, "STALE", reasons, comparisons)

    if advisory and ttl is None:
        reasons.append("advisory-ttl-missing")
        return _row(receipt_id, claim_id, stored, "STALE", reasons, comparisons)

    if ttl is not None:
        if ttl < 0:
            reasons.append("ttl-unparseable")
            return _row(receipt_id, claim_id, stored, "STALE", reasons, comparisons)
        confirmed_at = parse_iso(receipt.get("confirmed_at") or receipt.get("timestamp"))
        if confirmed_at is None:
            reasons.append("confirmed-at-unparseable")
            return _row(receipt_id, claim_id, stored, "STALE", reasons, comparisons)
        age = (now - confirmed_at).total_seconds()
        if age >= ttl:
            reasons.append(f"ttl-expired:age_s={int(age)}:ttl_s={ttl}")
            return _row(receipt_id, claim_id, stored, "STALE", reasons, comparisons)

    reasons.append("hashes-match-and-ttl-ok")
    return _row(receipt_id, claim_id, stored, "CONFIRMED", reasons, comparisons)


def _row(
    receipt_id: str,
    claim_id: str,
    stored: str,
    live: str,
    reasons: list[str],
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "receipt_id": receipt_id,
        "claim_id": claim_id,
        "stored_verdict": stored,
        "live_verdict": live,
        "flipped": stored == "CONFIRMED" and live == "STALE",
        "reasons": reasons,
        "input_hash_set": comparisons,
    }


def reader_from_files(files: dict[str, bytes]) -> ReadBytes:
    def read(path: str) -> bytes | None:
        if path in files:
            return files[path]
        p = Path(path)
        if p.is_file():
            return p.read_bytes()
        return None

    return read


def evaluate_corpus(
    receipts: Iterable[dict],
    *,
    now: datetime | None = None,
    read_bytes: ReadBytes | None = None,
) -> list[dict[str, Any]]:
    return [
        evaluate_receipt(r, now=now, read_bytes=read_bytes)
        for r in receipts
        if isinstance(r, dict)
    ]


def mutate_one_byte(raw: bytes) -> bytes:
    if not raw:
        return b"\x00"
    return bytes([raw[0] ^ 0x01]) + raw[1:]
