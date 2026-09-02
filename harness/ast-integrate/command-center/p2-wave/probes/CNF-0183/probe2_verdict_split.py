#!/usr/bin/env python3
"""Named probe 2: PACKAGE-INCOMPLETE vs CLAIM-REFUTED must not be swapped."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import unshadow as U  # noqa: E402

U.unshadow()
import jsonschema  # noqa: E402
import rehearse as R  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0183.json"
SCHEMA = REPO / "command-center/schema/replication-package.schema.json"


def main() -> int:
    bat = R.battery(REPO)
    inc = bat["incomplete"]
    false = bat["false"]
    naive = bat["naive_incomplete"]
    split = bat["verdict_split"]
    if inc.get("verdict") != "PACKAGE-INCOMPLETE":
        print(f"FAILED:CNF-0183-probe2 incomplete got {inc.get('verdict')}")
        return 1
    named = str(inc.get("missing_element") or "")
    if "count.txt" not in named:
        print(f"FAILED:CNF-0183-probe2 missing_element not count.txt: {named}")
        return 1
    if false.get("verdict") != "CLAIM-REFUTED":
        print(f"FAILED:CNF-0183-probe2 false claim got {false.get('verdict')}")
        return 1
    if not false.get("counter_evidence"):
        print("FAILED:CNF-0183-probe2 CLAIM-REFUTED missing counter_evidence")
        return 1
    if naive.get("verdict") != "CLAIM-REFUTED":
        print("FAILED:CNF-0183-probe2 naive classifier did not conflate")
        return 1
    if not split.get("pass"):
        print("FAILED:CNF-0183-probe2 verdict_split.pass false")
        print(json.dumps(split, indent=2))
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0183-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0183-probe2 self-declared {doc.get('state')}")
        return 1
    by_v = {
        r.get("verdict"): r
        for r in (doc.get("rehearsals") or [])
        if isinstance(r, dict)
    }
    if "PACKAGE-INCOMPLETE" not in by_v or "CLAIM-REFUTED" not in by_v:
        print(f"FAILED:CNF-0183-probe2 receipt missing split verdicts {list(by_v)}")
        return 1
    if "count.txt" not in str(by_v["PACKAGE-INCOMPLETE"].get("missing_element") or ""):
        print("FAILED:CNF-0183-probe2 receipt incompleteness did not name count.txt")
        return 1
    if not by_v["CLAIM-REFUTED"].get("counter_evidence"):
        print("FAILED:CNF-0183-probe2 receipt refute missing counter_evidence")
        return 1
    vs = doc.get("verdict_split") or {}
    if vs.get("incomplete_not_recorded_as_refute") is not True:
        print("FAILED:CNF-0183-probe2 receipt split flag")
        return 1
    if vs.get("refute_not_recorded_as_incomplete") is not True:
        print("FAILED:CNF-0183-probe2 receipt split flag 2")
        return 1

    errs = SC.error_messages(doc, REPO)
    if errs:
        print("FAILED:CNF-0183-probe2 receipt schema-invalid")
        print(errs[0])
        return 1
    if not SC.garbage_rejected(REPO):
        print("FAILED:CNF-0183-probe2 schema accepted garbage")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-verdict-split",
                "unit_id": "CNF-0183",
                "incomplete_verdict": inc["verdict"],
                "missing_element": inc.get("missing_element"),
                "false_verdict": false["verdict"],
                "naive_incomplete_verdict": naive["verdict"],
                "split_pass": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0183-probe2 verdict split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
