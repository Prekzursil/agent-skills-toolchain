#!/usr/bin/env python3
"""Named probe 1: isolation both-states + complete true package REPRODUCED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import rehearse as R  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0183.json"


def main() -> int:
    bat = R.battery(REPO)
    iso = bat["isolation"]
    rec = bat["true"]
    if not iso.get("pass"):
        print("FAILED:CNF-0183-probe1 isolation both-states")
        print(json.dumps(iso, indent=2, default=str)[:2000])
        return 1
    if rec.get("verdict") != "REPRODUCED":
        print(f"FAILED:CNF-0183-probe1 expected REPRODUCED got {rec.get('verdict')}")
        print(json.dumps(rec, indent=2, default=str)[:2000])
        return 1
    if iso.get("unguarded_absolute_reachable") is not True:
        print("FAILED:CNF-0183-probe1 unguarded absolute catalog not reachable")
        return 1
    if iso.get("guarded_absolute_reachable") is not False:
        print("FAILED:CNF-0183-probe1 guarded absolute catalog still reachable")
        return 1
    if iso.get("relative_reachable_from_temp") is not False:
        print("FAILED:CNF-0183-probe1 relative catalog reachable from temp cwd")
        return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0183-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0183-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0183" not in text:
        print("FAILED:CNF-0183-probe1 sentinel absent")
        return 1
    view = SC.receipt_view(doc)
    aiso = view["isolation"]
    if aiso.get("pass") is not True or aiso.get("guarded_absolute_reachable") is not False:
        print("FAILED:CNF-0183-probe1 receipt isolation flags")
        return 1
    verdicts = [r.get("verdict") for r in (view["rehearsals"] or []) if isinstance(r, dict)]
    if "REPRODUCED" not in verdicts:
        print(f"FAILED:CNF-0183-probe1 receipt missing REPRODUCED {verdicts}")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-isolation-reproduced",
                "unit_id": "CNF-0183",
                "isolation_pass": True,
                "guarded_absolute_reachable": False,
                "unguarded_absolute_reachable": True,
                "true_verdict": rec["verdict"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0183-probe1 isolation and REPRODUCED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
