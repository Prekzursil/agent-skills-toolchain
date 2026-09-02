#!/usr/bin/env python3
"""Named probe 2: owner-file preservation, behaviour restore, named-clock MTTR.

Independent re-execution of T3 and T4 on a freshly created isolated HOME.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drill as D  # noqa: E402

ART = REPO / "command-center/receipts/REL-0006.json"


def main() -> int:
    t3 = D.test_owner_files_and_restore()
    t4 = D.test_restore_mttr()
    print(json.dumps({"t3": t3, "t4": t4}, indent=2, sort_keys=True))
    if t3.get("result") != "PASS":
        print("FAILED:REL-0006-probe2 owner files or restore")
        return 1
    if t4.get("result") != "PASS":
        print("FAILED:REL-0006-probe2 behaviour restore or MTTR")
        return 1
    if not ART.is_file():
        print("FAILED:REL-0006-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:REL-0006" not in text:
        print("FAILED:REL-0006-probe2 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:REL-0006-probe2 self-declared", doc.get("state"))
        return 1
    mttr = ((doc.get("mttr") or {}) if isinstance(doc.get("mttr"), dict) else {}) or {}
    if not (doc.get("mttr") or {}).get("clock_source"):
        # also accept nested under tests T4
        t4_doc = {}
        for t in doc.get("tests") or []:
            if isinstance(t, dict) and t.get("id") == "T4-mttr-named-clock-vs-runbook":
                t4_doc = t
                break
        mttr = t4_doc.get("mttr") or mttr
    clock = str(mttr.get("clock_source") or "")
    if "perf_counter" not in clock and "time.perf_counter" not in clock:
        print("FAILED:REL-0006-probe2 named clock missing from receipt")
        return 1
    if mttr.get("within_slo") is not True:
        print("FAILED:REL-0006-probe2 receipt MTTR not within SLO")
        return 1
    before = (doc.get("acceptance_probe") or {}).get("before") or {}
    after = (doc.get("acceptance_probe") or {}).get("after") or {}
    if before.get("passed") is not False or after.get("passed") is not True:
        print("FAILED:REL-0006-probe2 receipt before/after acceptance quotes missing")
        return 1
    retr = doc.get("retrievability") or {}
    if not retr.get("fetched_sha256") or retr.get("fetched_sha256") != retr.get("manifest_sha256"):
        print("FAILED:REL-0006-probe2 receipt sha256 quotes missing or unequal")
        return 1
    print(
        f"owner_ok=True restored={after.get('output')!r} "
        f"mttr_s={mttr.get('seconds')} clock={clock[:48]}"
    )
    print("SUCCESS:REL-0006-probe2 owner-file preservation behaviour restore MTTR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
