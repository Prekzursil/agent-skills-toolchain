#!/usr/bin/env python3
"""Named probe 1: declared write set is a SUPERSET of observed writes.

Signal 1 is the recorder's observed path set. Signal 2 is the on-disk file
list after the real run. Disagreement is BLOCKED. The under-declare fixture
must fail so an always-green checker cannot credit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import measure_all  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0227.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0227-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0227" not in text:
        print("FAILED:IMP-0227-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0227-probe1 self-declared", doc.get("state"))
        return 1

    rec = measure_all()
    positives = rec["positives"]
    if len(positives) != 3:
        print(f"FAILED:IMP-0227-probe1 fixture_count={len(positives)} want=3")
        return 1
    if not rec["all_positive_superset"]:
        print("FAILED:IMP-0227-probe1 declared writes not a superset of observed")
        print(json.dumps(positives, indent=2, default=str)[:3000])
        return 1
    if not rec["underdeclare_fails_as_required"]:
        print("FAILED:IMP-0227-probe1 under-declare fixture did not fail (inert detector)")
        return 1
    under = rec["underdeclare"]["superset"]
    if "out/leak.txt" not in under["underdeclared"]:
        print("FAILED:IMP-0227-probe1 leak path not in underdeclared", under)
        return 1

    fan = next(p for p in positives if p["workflow_id"] == "wf.fanout")
    declared_n = len(fan["superset"]["declared"])
    observed_n = len(fan["superset"]["observed"])
    if not (declared_n > observed_n >= 1):
        print(
            f"FAILED:IMP-0227-probe1 fan-out bound not conservative "
            f"declared={declared_n} observed={observed_n}"
        )
        return 1

    rows = []
    for p in positives:
        rows.append(
            {
                "id": p["workflow_id"],
                "declared": p["superset"]["declared"],
                "observed": p["superset"]["observed"],
                "ok": p["superset"]["ok"],
                "disk_ok": p["disk_superset"]["ok"],
            }
        )
    out = {
        "probe": "probe1-superset",
        "unit_id": "IMP-0227",
        "pass": True,
        "fixtures": rows,
        "underdeclare_failed": True,
        "underdeclared_paths": under["underdeclared"],
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "superset ok on",
        [r["id"] for r in rows],
        "underdeclare fired",
        under["underdeclared"],
    )
    print("SUCCESS:IMP-0227-probe1 declared writes superset of observed writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
