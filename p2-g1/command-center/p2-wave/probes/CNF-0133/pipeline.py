"""CNF-0133 pipeline: the count/status test-rerun confirmer.

The registered suite observes ONLY file_count and status of a materialized
snapshot; it does NOT check sha256 or names. CONFIRMED iff the suite passes
on the claim's expected values; REFUTED iff it fails; never launders an infra
fault into a verdict. Rebuilt 2026-10-26 (wave-3 shard 7) after the original
probe tree was lost; the contract is pinned by the published pipeline block
in command-center/receipts/CNF-0133.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SUITE_ID = "cnf0133-count-status-suite"
SUITE_FIELDS = ["file_count", "status"]
DOES_NOT_CHECK = ["sha256", "names"]


def scan(snapshot_dir):
    """Full observation report over a materialized snapshot dir."""
    root = Path(snapshot_dir)
    names = []
    total_bytes = 0
    ok = True
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            names.append(rel)
            try:
                total_bytes += p.stat().st_size
            except OSError:
                ok = False
    status = "ok" if ok and names else "empty"
    listing = ";".join(names)
    return {
        "file_count": len(names),
        "status": status,
        "names": names,
        "sha256": hashlib.sha256(listing.encode("utf-8")).hexdigest(),
    }


def run_suite(snapshot_dir, claim):
    """The registered suite: rerun and compare ONLY the checked fields."""
    report = scan(snapshot_dir)
    exp = claim.get("expected") or {}
    checked = {}
    for f in SUITE_FIELDS:
        checked[f] = report.get(f)
    passed = all(checked.get(f) == exp.get(f) for f in SUITE_FIELDS)
    return {
        "suite_id": SUITE_ID,
        "checked_fields": list(SUITE_FIELDS),
        "observed": checked,
        "expected": {f: exp.get(f) for f in SUITE_FIELDS},
        "pass": passed,
        "full_report_ignored": {k: report[k] for k in DOES_NOT_CHECK},
    }
