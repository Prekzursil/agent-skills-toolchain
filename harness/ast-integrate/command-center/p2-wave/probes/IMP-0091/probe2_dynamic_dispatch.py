#!/usr/bin/env python3
"""Probe 2: reviewer hide-behind-dynamic-dispatch.

Static pass must miss the computed getattr network call; dynamic (strace)
must catch it; the discrepancy must be named. The limitation is documented
inline on the receipt, not hidden.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center/receipts/IMP-0091.json"
TOOLS = REPO / "tools"
HERE = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.permission_analysis import (  # noqa: E402
    NET,
    STATIC_LIMITATION,
    analyze,
    write_fixture,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0091-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0091-p2-") as td:
        root = write_fixture(td, "dispatch-kit")
        report = analyze(root)

    if NET in report.static_used:
        return fail(f"static unexpectedly saw network: {report.static_used}")
    if NET not in report.dynamic_used:
        return fail(
            f"dynamic missed network method={report.dynamic_method} used={report.dynamic_used} detail={report.dynamic_detail}"
        )
    if NET not in report.union_used or NET not in report.undeclared:
        return fail(f"union/undeclared missing net: union={report.union_used} und={report.undeclared}")
    kinds = [d.get("kind") for d in report.discrepancies]
    if "static_misses_dynamic_dispatch" not in kinds:
        return fail(f"discrepancy not named: {report.discrepancies}")
    if report.verdict == "CLEAN":
        return fail("CLEAN despite undeclared dynamic-dispatch network")
    if STATIC_LIMITATION not in report.static_limitation:
        return fail("static limitation text missing on report")

    if not ART.is_file():
        return fail("receipt absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0091" not in blob:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    reviewer = doc.get("reviewer") or {}
    if not reviewer.get("independent"):
        return fail("reviewer.independent is not true")
    if "dynamic dispatch" not in blob.lower() and "dynamic-dispatch" not in blob.lower():
        return fail("receipt hides the dynamic-dispatch limitation")
    if "getattr" not in blob.lower() and "computed" not in blob.lower():
        return fail("receipt does not name getattr/computed dispatch")
    if STATIC_LIMITATION not in blob and "expected limitation" not in blob.lower():
        return fail("receipt does not document the static limitation inline")

    summary = {
        "probe": "probe2-dynamic-dispatch",
        "unit_id": "IMP-0091",
        "static_used": report.static_used,
        "dynamic_used": report.dynamic_used,
        "dynamic_method": report.dynamic_method,
        "union_used": report.union_used,
        "discrepancy_kinds": kinds,
        "verdict": report.verdict,
        "reviewer_verdict": reviewer.get("verdict"),
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0091-probe2 static misses dynamic dispatch; named; documented inline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
