#!/usr/bin/env python3
"""Probe 2: surviving-mutant enumeration is mandatory; percentage-only reports fail."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0109.json"


def key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("schema_id") or ""),
        str(row.get("axis") or ""),
        str(row.get("path") or ""),
        str(row.get("mutation_applied") or ""),
    )


def main() -> int:
    fake = E.percentage_only_report()
    fake_ok, fake_why = E.enumeration_ok(fake)
    if fake_ok:
        print("FAILED:ARC-0109-probe2 percentage-only control was accepted")
        return 1
    if "percentage-only" not in fake_why:
        print(f"FAILED:ARC-0109-probe2 control reason unexpected: {fake_why}")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0109-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0109-probe2 self-declared {doc.get('state')}")
        return 1
    ok, why = E.enumeration_ok(doc)
    if not ok:
        print(f"FAILED:ARC-0109-probe2 artifact enumeration {why}")
        return 1
    campaign = E.run_campaign()
    live_rows = campaign["surviving_mutants"]
    art_rows = doc.get("surviving_mutants") or []
    live_keys = {key(r) for r in live_rows}
    art_keys = {key(r) for r in art_rows}
    missing = sorted(live_keys - art_keys)
    if missing:
        print(f"FAILED:ARC-0109-probe2 live survivors missing from artifact: {missing[:8]}")
        return 1
    extra = sorted(art_keys - live_keys)
    if extra:
        print(f"FAILED:ARC-0109-probe2 artifact lists stale survivors: {extra[:8]}")
        return 1
    applied = int(campaign["mutations"]["applied"])
    art_applied = int((doc.get("mutations") or {}).get("applied") or -1)
    if applied != art_applied:
        print(f"FAILED:ARC-0109-probe2 applied count live={applied} artifact={art_applied}")
        return 1
    if applied < 14 * 5:
        print(f"FAILED:ARC-0109-probe2 too few mutations applied: {applied}")
        return 1
    if "SUCCESS:ARC-0109" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0109-probe2 sentinel absent")
        return 1
    print(
        json.dumps(
            {
                "percentage_only_rejected": True,
                "percentage_only_reason": fake_why,
                "enumeration": why,
                "surviving_mutants": len(art_rows),
                "mutations_applied": applied,
                "live_matches_artifact": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0109-probe2 surviving-mutant enumeration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
