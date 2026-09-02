#!/usr/bin/env python3
"""Probe 1: fetched pages are untrusted DATA; injections are logged, not followed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402
import sweep as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0021-sweep-vendor-documentation.json"
PLANTED = HERE / "fixtures/planted_injection.md"


def main() -> int:
    text = PLANTED.read_text(encoding="utf-8")
    safe, log = L.neutralize(text)
    ids = {row["pattern_id"] for row in log}
    need = {
        "ignore-previous",
        "you-are-now",
        "mark-verified",
        "skip-timestamp",
        "do-not-log",
        "promote-finding",
        "system-tag",
    }
    missing = sorted(need - ids)
    if missing:
        print("FAILED:WFA-0021-probe1 patterns not logged", missing)
        return 1
    if any(row.get("followed") for row in log):
        print("FAILED:WFA-0021-probe1 followed=true")
        return 1
    if "Ignore previous instructions" in safe:
        print("FAILED:WFA-0021-probe1 instruction survived neutralize")
        return 1
    if "planted-backdoor as VERIFIED" in safe:
        print("FAILED:WFA-0021-probe1 promote instruction survived")
        return 1

    planted_surfaces = [
        {
            "kind": "docs",
            "url": "https://example.invalid/planted",
            "retrieved_at": "2026-08-24T18:00:00Z",
        }
    ]
    grade = L.grade_surfaces(planted_surfaces)
    if grade["status"] != "UNVERIFIED":
        print("FAILED:WFA-0021-probe1 planted promoted", grade)
        return 1
    if not grade.get("settling_probe"):
        print("FAILED:WFA-0021-probe1 planted missing settling_probe")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0021-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS" or S.SENTINEL not in json.dumps(doc):
        print("FAILED:WFA-0021-probe1 sentinel/state")
        return 1
    for row in doc.get("injection_log") or []:
        if row.get("followed"):
            print("FAILED:WFA-0021-probe1 live log followed")
            return 1

    live = S.run_sweep()
    for rec in live["mechanisms"]:
        if rec["id"] == "planted-backdoor":
            print("FAILED:WFA-0021-probe1 planted leaked into live sweep")
            return 1

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-injection-neutralize",
                "logged": sorted(ids),
                "planted_status": grade["status"],
                "followed": False,
                "unit_id": "WFA-0021",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0021-probe1 injection logged not followed not promoted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
