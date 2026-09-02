"""Dependency / supply-chain audit with advisory-DB decay.

A stored GREEN is not a control for today: the advisory database is live.
A scan older than its class TTL is STALE/DECAYED and must be re-run.
Clock is injected. Wall clock is never consulted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# advisory-live class: last week's clean scan is not a control for today.
TTL_BY_CLASS = {"advisory-live": 86400}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_advisory_db(path: Path | None = None) -> dict[str, Any]:
    target = path or (FIXTURES / "advisory_db.json")
    return json.loads(target.read_text(encoding="utf-8"))


def load_lockfile(path: Path | None = None) -> dict[str, Any]:
    target = path or (FIXTURES / "lockfile.json")
    return json.loads(target.read_text(encoding="utf-8"))


def scan_lockfile(lockfile: dict[str, Any], advisory_db: dict[str, Any], *, now_epoch: int) -> dict[str, Any]:
    """Hermetic scan: join lockfile packages to the advisory snapshot at now_epoch."""
    findings: list[dict[str, Any]] = []
    packages = lockfile.get("packages") or []
    advisories = advisory_db.get("advisories") or []
    for pkg in packages:
        name = pkg.get("name")
        version = pkg.get("version")
        for adv in advisories:
            if adv.get("package") == name and version in (adv.get("affected_versions") or []):
                findings.append(
                    {
                        "package": name,
                        "version": version,
                        "advisory_id": adv.get("id"),
                        "severity": adv.get("severity"),
                    }
                )
    verdict = "RED" if findings else "GREEN"
    snapshot = {
        "db_epoch": int(advisory_db.get("db_epoch") or now_epoch),
        "db_sha256": sha256_bytes(json.dumps(advisory_db, sort_keys=True).encode("utf-8")),
        "lockfile_sha256": sha256_bytes(json.dumps(lockfile, sort_keys=True).encode("utf-8")),
        "findings": findings,
        "finding_count": len(findings),
        "verdict": verdict,
        "scanned_at": int(now_epoch),
        "class": "advisory-live",
        "method": "hermetic-advisory-join",
    }
    return snapshot


def classify(scan: dict[str, Any], *, now_epoch: int) -> dict[str, Any]:
    ttl = TTL_BY_CLASS[str(scan.get("class") or "advisory-live")]
    scanned_at = int(scan["scanned_at"])
    age = int(now_epoch) - scanned_at
    stale = age > ttl
    stored_green = str(scan.get("verdict") or "").upper() == "GREEN"
    classification = "STALE" if stale else "FRESH"
    decayed = bool(stale and stored_green)
    return {
        "classification": classification,
        "decayed": decayed,
        "age_seconds": age,
        "ttl_seconds": ttl,
        "stored_verdict": scan.get("verdict"),
        "now_epoch": int(now_epoch),
        "scanned_at": scanned_at,
    }


def naive_reuse(scan: dict[str, Any], *, now_epoch: int) -> dict[str, Any]:
    """Negative control: trust the stored row, including last week's GREEN."""
    return {
        "action": "REUSE",
        "reused": True,
        "re_run": False,
        "classification": "TRUSTED-STORED",
        "decayed": False,
        "verdict": scan.get("verdict"),
        "now_epoch": int(now_epoch),
        "method": "naive-cache",
    }


def audit(
    scan: dict[str, Any],
    *,
    now_epoch: int,
    lockfile: dict[str, Any] | None = None,
    advisory_db: dict[str, Any] | None = None,
    rerun: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    meta = classify(scan, now_epoch=now_epoch)
    if meta["classification"] == "FRESH":
        return {
            **meta,
            "action": "ACCEPT-FRESH",
            "reused": True,
            "re_run": False,
            "verdict": scan.get("verdict"),
            "method": "ttl-fresh",
        }
    lock = lockfile if lockfile is not None else load_lockfile()
    db = advisory_db if advisory_db is not None else load_advisory_db()
    runner = rerun or (lambda: scan_lockfile(lock, db, now_epoch=now_epoch))
    fresh = runner()
    return {
        **meta,
        "action": "RE-RUN",
        "reused": False,
        "re_run": True,
        "prior_verdict": scan.get("verdict"),
        "verdict": fresh.get("verdict"),
        "fresh_scan": fresh,
        "method": "ttl-decay-rerun",
    }


def reuse_gate(result: dict[str, Any], scan: dict[str, Any], *, now_epoch: int) -> dict[str, Any]:
    """Refuse a stale stored GREEN that was reused without a re-run."""
    meta = classify(scan, now_epoch=now_epoch)
    if meta["classification"] == "STALE":
        reused = bool(result.get("reused"))
        reran = bool(result.get("re_run")) or result.get("action") == "RE-RUN"
        labelled = result.get("classification") in {"STALE", "DECAYED"} or bool(result.get("decayed"))
        if reused or not reran or not labelled:
            return {
                "ok": False,
                "fired": True,
                "reason": "stale-green-reused",
                "meta": meta,
            }
        return {"ok": True, "fired": False, "reason": "stale-rerun", "meta": meta}
    return {"ok": True, "fired": False, "reason": "fresh-ok", "meta": meta}
