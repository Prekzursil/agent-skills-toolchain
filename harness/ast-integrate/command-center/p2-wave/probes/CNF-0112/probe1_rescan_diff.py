#!/usr/bin/env python3
"""Probe 1: re-run lockfile advisory scan and diff against the stored result.

Instrument: osv.dev /v1/querybatch over product lockfiles, set-diff of
(id, package, version) versus the stored finding set. Distinct from probe 2
(single-package known-advisory + exit-127 classifier).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scanner as S  # noqa: E402

UNIT = "CNF-0112"
ART = REPO / "command-center/confirmation/CNF-0112-advisory-rescan.json"
SCHEMA = REPO / "command-center/schema/security-report.schema.json"
STORED = HERE / "fixtures/stored-scan.json"
PRODUCT_LOCKS = [
    "command-center/p2-wave/probes/CNF-0153/inputs/current/package-lock.json",
    "command-center/p2-wave/probes/CNF-0153/inputs/current/tools/mcp/hacktricks-mcp-server/package-lock.json",
]
SENTINEL = (
    "SUCCESS:CNF-0112 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the known-advisory "
    "control was reported by the scanner, proving the database is live. "
    "Any other terminal state is FAILED:CNF-0112 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0112-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0112-probe1 sentinel-absent")
        return 1
    if doc.get("unit_id") != UNIT:
        print("FAILED:CNF-0112-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0112-probe1 self-declared", doc.get("state"))
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:CNF-0112-probe1 schema", errs[0].message)
        return 1

    scanner = doc.get("scanner") or {}
    snap = scanner.get("database_snapshot_date") or scanner.get("query_timestamp")
    if not snap:
        print("FAILED:CNF-0112-probe1 scan without database snapshot date")
        return 1

    pkgs: list[dict[str, str]] = []
    for rel in PRODUCT_LOCKS:
        path = REPO / rel
        if not path.is_file():
            print("FAILED:CNF-0112-probe1 lockfile missing", rel)
            return 1
        pkgs.extend(S.packages_from_npm_lock(path))
    try:
        batch = S.query_batch(pkgs)
    except RuntimeError as exc:
        print("FAILED:CNF-0112-probe1 database-not-live", exc)
        return 1
    fresh = S.flatten_findings(batch)
    stored = S.load_stored(STORED)
    live_diff = S.diff_findings(stored.get("findings") or [], fresh)
    recorded = doc.get("diff") or {}
    if "added_count" not in recorded or "removed_count" not in recorded:
        print("FAILED:CNF-0112-probe1 artifact missing diff")
        return 1
    if not stored.get("comparable") and recorded.get("comparable") is True:
        print("FAILED:CNF-0112-probe1 unstamped stored marked comparable")
        return 1

    out = {
        "probe": "probe1-rescan-diff",
        "unit_id": UNIT,
        "package_count": len(pkgs),
        "fresh_finding_count": len(fresh),
        "stored_comparable": bool(stored.get("comparable")),
        "stored_live_or_cached": stored.get("live_or_cached"),
        "diff_added": live_diff["added_count"],
        "diff_removed": live_diff["removed_count"],
        "database_snapshot_date": snap,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"rescan packages={len(pkgs)} findings={len(fresh)} "
        f"added={live_diff['added_count']} comparable={stored.get('comparable')} "
        f"snap={snap}"
    )
    print("SUCCESS:CNF-0112-probe1 rescan-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
