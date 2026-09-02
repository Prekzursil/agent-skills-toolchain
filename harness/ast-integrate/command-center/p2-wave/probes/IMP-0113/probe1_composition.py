#!/usr/bin/env python3
"""Named probe 1: linter finding set equals standalone union on known-bad.

Signal 1 is the composer's finding set. Signal 2 is each sub-check run
standalone. A composer that silently drops a sub-check fails this probe.
Also requires the composer to import those sub-checks rather than
reimplement their rules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.checks import RULE_IDS, STANDALONE_MODULES  # noqa: E402
from marketplace.fixtures import BAD, SYNTHETIC_SECRET_BODY, materialize  # noqa: E402
from marketplace.package_linter import composition_sets, lint_package  # noqa: E402
from marketplace.reuse import composer_reuses_subchecks  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0113.json"


def main() -> int:
    materialize()
    reuse = composer_reuses_subchecks()
    sets = composition_sets(BAD)
    report = lint_package(BAD)
    blob = json.dumps(report, sort_keys=True)
    payload = {
        "probe": "probe1-composition",
        "unit_id": "IMP-0113",
        "linter": sets["linter"],
        "union": sets["union"],
        "equal": sets["equal"],
        "all_six_fired": set(sets["union"]) == set(RULE_IDS),
        "finding_count": report["finding_count"],
        "reuse_ok": reuse["ok"],
        "secret_body_absent": SYNTHETIC_SECRET_BODY not in blob,
        "standalone_modules": STANDALONE_MODULES,
    }
    print(json.dumps(payload, sort_keys=True))
    if not reuse["ok"]:
        print("FAILED:IMP-0113-probe1 composer reimplements rules", reuse)
        return 1
    if not sets["equal"]:
        print("FAILED:IMP-0113-probe1 composition lost a sub-check", sets)
        return 1
    if set(sets["union"]) != set(RULE_IDS):
        print("FAILED:IMP-0113-probe1 known-bad did not fire all six rules", sets)
        return 1
    if report["finding_count"] != 6:
        print(f"FAILED:IMP-0113-probe1 finding_count={report['finding_count']} want=6")
        return 1
    if SYNTHETIC_SECRET_BODY in blob:
        print("FAILED:IMP-0113-probe1 secret body leaked into report")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0113-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0113-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0113" not in text:
        print("FAILED:IMP-0113-probe1 sentinel absent")
        return 1
    live_union = ((doc.get("report") or {}).get("known_bad") or {}).get("union")
    if live_union is not None and sorted(live_union) != sorted(sets["union"]):
        print("FAILED:IMP-0113-probe1 receipt union drifted from live", live_union, sets["union"])
        return 1
    print("SUCCESS:IMP-0113-probe1 composition equals standalone union")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
