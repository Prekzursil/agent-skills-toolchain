#!/usr/bin/env python3
"""Detector controls for CNF-0012.

1. Mutate one input byte: exactly one CONFIRMED receipt flips to STALE.
2. Leave inputs untouched: zero receipts flip.
3. No recorded input hashes: STALE by default, never CONFIRMED by omission.
4. TTL expiry and advisory-class missing TTL: STALE even when hashes match.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from corpus import is_confirmation_receipt, load_receipt, scan_corpus
from freshness import (
    ADVISORY_TTL_SECONDS,
    DEFAULT_TTL_SECONDS,
    digest_bytes,
    evaluate_receipt,
    mutate_one_byte,
    reader_from_files,
)

NOW = datetime(2026, 8, 24, 18, 33, tzinfo=timezone.utc)
STABLE = b"stable-input-payload-v1\n"
MUTABLE = b"mutable-input-payload-v1\n"
CODE = b"scanner-wrapper-source-v1\n"


def _receipt(
    *,
    receipt_id: str,
    claim_id: str,
    path: str,
    blob: bytes,
    confirmed_at: datetime,
    ttl_seconds: int | None = DEFAULT_TTL_SECONDS,
    advisory_class: bool = False,
    include_hashes: bool = True,
    extra_hashes: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    hashes: list[dict[str, str]] = []
    if include_hashes:
        hashes.append({"path": path, "sha256": digest_bytes(blob)})
        if extra_hashes:
            hashes.extend(extra_hashes)
    rec: dict[str, Any] = {
        "receipt_id": receipt_id,
        "claim_id": claim_id,
        "confirmer": "CNF-0012-fixture-confirmer",
        "source_probe": {
            "tool": "sha256",
            "shell": "python3",
            "field": "input-bytes",
            "kind": "digest",
        },
        "verifier_probe": {
            "tool": "ttl-clock",
            "shell": "python3",
            "field": "confirmed_at",
            "kind": "age",
        },
        "probe_output": "fixture-control",
        "verdict": "CONFIRMED",
        "residual": "none",
        "confirmed_at": confirmed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "advisory_class": advisory_class,
        "input_hashes": hashes,
    }
    if ttl_seconds is not None:
        rec["ttl_seconds"] = ttl_seconds
    return rec


def mutate_one_byte_control() -> dict[str, Any]:
    files = {"input-a.txt": MUTABLE, "input-b.txt": STABLE}
    r_mut = _receipt(
        receipt_id="R-MUTATE",
        claim_id="CNF-0012-mutate",
        path="input-a.txt",
        blob=MUTABLE,
        confirmed_at=NOW,
    )
    r_ok = _receipt(
        receipt_id="R-UNTOUCHED",
        claim_id="CNF-0012-untouched",
        path="input-b.txt",
        blob=STABLE,
        confirmed_at=NOW,
    )
    before_reader = reader_from_files(files)
    before = [
        evaluate_receipt(r_mut, now=NOW, read_bytes=before_reader),
        evaluate_receipt(r_ok, now=NOW, read_bytes=before_reader),
    ]
    files["input-a.txt"] = mutate_one_byte(MUTABLE)
    after_reader = reader_from_files(files)
    after = [
        evaluate_receipt(r_mut, now=NOW, read_bytes=after_reader),
        evaluate_receipt(r_ok, now=NOW, read_bytes=after_reader),
    ]
    flipped = [
        a["receipt_id"]
        for b, a in zip(before, after)
        if b["live_verdict"] != a["live_verdict"]
    ]
    ok = (
        all(row["live_verdict"] == "CONFIRMED" for row in before)
        and len(flipped) == 1
        and flipped == ["R-MUTATE"]
        and after[0]["live_verdict"] == "STALE"
        and after[1]["live_verdict"] == "CONFIRMED"
        and "input-hash-mismatch:input-a.txt" in after[0]["reasons"]
    )
    return {
        "name": "mutate-one-byte",
        "before": before,
        "after": after,
        "flipped_count": len(flipped),
        "flipped_ids": flipped,
        "untouched_stayed_confirmed": after[1]["live_verdict"] == "CONFIRMED",
        "pass": ok,
    }


def untouched_control() -> dict[str, Any]:
    files = {"input-a.txt": MUTABLE, "input-b.txt": STABLE}
    receipts = [
        _receipt(
            receipt_id="R-MUTATE",
            claim_id="CNF-0012-mutate",
            path="input-a.txt",
            blob=MUTABLE,
            confirmed_at=NOW,
        ),
        _receipt(
            receipt_id="R-UNTOUCHED",
            claim_id="CNF-0012-untouched",
            path="input-b.txt",
            blob=STABLE,
            confirmed_at=NOW,
        ),
    ]
    reader = reader_from_files(files)
    first = [evaluate_receipt(r, now=NOW, read_bytes=reader) for r in receipts]
    second = [evaluate_receipt(r, now=NOW, read_bytes=reader) for r in receipts]
    flipped = [
        a["receipt_id"]
        for b, a in zip(first, second)
        if b["live_verdict"] != a["live_verdict"]
    ]
    ok = (
        all(row["live_verdict"] == "CONFIRMED" for row in first)
        and len(flipped) == 0
        and all(row["live_verdict"] == "CONFIRMED" for row in second)
    )
    return {
        "name": "untouched-inputs",
        "first": first,
        "second": second,
        "flipped_count": len(flipped),
        "flipped_ids": flipped,
        "pass": ok,
    }


def omission_control() -> dict[str, Any]:
    files = {"input-a.txt": MUTABLE}
    rec = _receipt(
        receipt_id="R-OMISSION",
        claim_id="CNF-0012-omission",
        path="input-a.txt",
        blob=MUTABLE,
        confirmed_at=NOW,
        include_hashes=False,
    )
    row = evaluate_receipt(rec, now=NOW, read_bytes=reader_from_files(files))
    ok = row["live_verdict"] == "STALE" and "missing-input-hashes" in row["reasons"]
    return {
        "name": "missing-input-hashes-default-stale",
        "row": row,
        "stored_verdict": rec["verdict"],
        "live_verdict": row["live_verdict"],
        "pass": ok,
    }


def ttl_and_advisory_control() -> dict[str, Any]:
    files = {"scanner.py": CODE}
    fresh = _receipt(
        receipt_id="R-TTL-FRESH",
        claim_id="ADV-0016",
        path="scanner.py",
        blob=CODE,
        confirmed_at=NOW,
        ttl_seconds=DEFAULT_TTL_SECONDS,
        advisory_class=True,
    )
    expired = _receipt(
        receipt_id="R-TTL-EXPIRED",
        claim_id="ADV-0016",
        path="scanner.py",
        blob=CODE,
        confirmed_at=NOW - timedelta(days=8),
        ttl_seconds=DEFAULT_TTL_SECONDS,
        advisory_class=True,
    )
    no_ttl = _receipt(
        receipt_id="R-ADVISORY-NO-TTL",
        claim_id="ADV-0016",
        path="scanner.py",
        blob=CODE,
        confirmed_at=NOW,
        ttl_seconds=None,
        advisory_class=True,
    )
    reader = reader_from_files(files)
    rows = {
        "fresh": evaluate_receipt(fresh, now=NOW, read_bytes=reader),
        "expired": evaluate_receipt(expired, now=NOW, read_bytes=reader),
        "no_ttl": evaluate_receipt(no_ttl, now=NOW, read_bytes=reader),
    }
    hashes_match = all(
        all(c["match"] for c in rows[k]["input_hash_set"]) for k in rows
    )
    ok = (
        hashes_match
        and rows["fresh"]["live_verdict"] == "CONFIRMED"
        and rows["expired"]["live_verdict"] == "STALE"
        and rows["no_ttl"]["live_verdict"] == "STALE"
        and any(r.startswith("ttl-expired") for r in rows["expired"]["reasons"])
        and "advisory-ttl-missing" in rows["no_ttl"]["reasons"]
        and rows["fresh"]["live_verdict"] != rows["expired"]["live_verdict"]
    )
    return {
        "name": "ttl-and-advisory",
        "advisory_ttl_seconds": ADVISORY_TTL_SECONDS,
        "rows": rows,
        "hashes_matched_on_all_three": hashes_match,
        "pass": ok,
    }


def write_disk_fixtures(root: Path) -> None:
    """On-disk control blobs plus a planted labelled/unlabelled pair."""
    inp = root / "inputs"
    inp.mkdir(parents=True, exist_ok=True)
    (inp / "mutable.txt").write_bytes(MUTABLE)
    (inp / "stable.txt").write_bytes(STABLE)
    (inp / "scanner.py").write_bytes(CODE)
    planted = root / "planted"
    planted.mkdir(parents=True, exist_ok=True)
    labelled = _receipt(
        receipt_id="R-PLANTED-LABELLED",
        claim_id="CNF-0012-planted-visible",
        path="command-center/p2-wave/probes/CNF-0012/fixtures/inputs/stable.txt",
        blob=STABLE,
        confirmed_at=NOW,
    )
    (planted / "labelled-confirmed.json").write_text(
        json.dumps(labelled, indent=1) + "\n", encoding="utf-8"
    )
    unlabelled = {
        "note": "json present but not a confirmation receipt: no claim_id",
        "verdict": "CONFIRMED",
        "confirmer": "imposter",
    }
    (planted / "unlabelled-no-claim.json").write_text(
        json.dumps(unlabelled, indent=1) + "\n", encoding="utf-8"
    )
    no_hashes = _receipt(
        receipt_id="R-PLANTED-NO-HASHES",
        claim_id="CNF-0012-planted-omission",
        path="command-center/p2-wave/probes/CNF-0012/fixtures/inputs/stable.txt",
        blob=STABLE,
        confirmed_at=NOW,
        include_hashes=False,
    )
    (planted / "confirmed-no-hashes.json").write_text(
        json.dumps(no_hashes, indent=1) + "\n", encoding="utf-8"
    )


def planted_visibility_control(repo: Path, fixture_root: Path) -> dict[str, Any]:
    write_disk_fixtures(fixture_root)
    planted = fixture_root / "planted"
    unlabelled = json.loads(
        (planted / "unlabelled-no-claim.json").read_text(encoding="utf-8")
    )
    live = scan_corpus(repo, now=NOW, roots=(str(planted),))
    found_ids = set()
    for path in sorted(planted.glob("*.json")):
        rec = load_receipt(path)
        if rec is not None:
            found_ids.add(rec.get("receipt_id"))
    labelled_seen = "R-PLANTED-LABELLED" in found_ids
    no_hash_seen = "R-PLANTED-NO-HASHES" in found_ids
    unlabelled_rejected = not is_confirmation_receipt(unlabelled)
    ok = (
        labelled_seen
        and no_hash_seen
        and unlabelled_rejected
        and live["corpus_size"] == 2
        and live["stale_count"] == 1
        and live["confirmed_count"] == 1
    )
    return {
        "name": "planted-visibility",
        "labelled_seen": labelled_seen,
        "no_hash_seen": no_hash_seen,
        "unlabelled_rejected": unlabelled_rejected,
        "planted_corpus_size": live["corpus_size"],
        "planted_stale_count": live["stale_count"],
        "planted_confirmed_count": live["confirmed_count"],
        "pass": ok,
    }


def run_all(repo: Path | None = None, fixture_root: Path | None = None) -> dict[str, Any]:
    mutate = mutate_one_byte_control()
    untouched = untouched_control()
    omission = omission_control()
    ttl = ttl_and_advisory_control()
    planted = None
    if repo is not None and fixture_root is not None:
        planted = planted_visibility_control(repo, fixture_root)
    parts = [mutate, untouched, omission, ttl]
    if planted is not None:
        parts.append(planted)
    ok = all(x["pass"] for x in parts)
    out = {
        "pass": ok,
        "mutate_one_byte": mutate,
        "untouched": untouched,
        "omission": omission,
        "ttl_and_advisory": ttl,
    }
    if planted is not None:
        out["planted_visibility"] = planted
    return out
