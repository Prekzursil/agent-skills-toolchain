#!/usr/bin/env python3
"""Probe 1: known-present control.

Plant 'no unit fails' next to a receipt measuring 12 of 103. The extractor
must fire and the flagged sentence must carry a scope-bounded rewrite.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import scanner as S  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0015.json"
SENTINEL = "SUCCESS:SYN-0015"


def main() -> int:
    kp = C.known_present()
    print(
        json.dumps(
            {
                "ok": kp["ok"],
                "plant_hits": kp["plant_hits"],
                "overclaim_count": kp["overclaim_count"],
                "rewrite_ok": kp["rewrite_ok"],
                "measured_ok": kp["measured_ok"],
                "work_confirmed": kp["work_confirmed"],
            },
            sort_keys=True,
        )
    )
    if not kp["ok"]:
        print("FAILED:SYN-0015-probe1 known-present plant did not fire with rewrite")
        return 1
    row = kp["rows"][0]
    rw = row["corrected_sentence"]
    if "12" not in rw or "103" not in rw:
        print("FAILED:SYN-0015-probe1 rewrite missing 12 of 103")
        return 1
    if int(row["measured_population"]["measured_n"]) != 12:
        print("FAILED:SYN-0015-probe1 measured_n != 12")
        return 1
    if int(row["measured_population"]["population_n"]) != 103:
        print("FAILED:SYN-0015-probe1 population_n != 103")
        return 1

    if not ART.is_file():
        print("FAILED:SYN-0015-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:SYN-0015-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    art_hits = [
        f
        for f in (doc.get("flagged_sentences") or [])
        if isinstance(f, dict)
        and (
            str(f.get("quantifier") or "").lower() == "no unit"
            or "no unit" in str(f.get("sentence") or "").lower()
        )
    ]
    if not art_hits:
        print("FAILED:SYN-0015-probe1 artifact omitted the known-present flag")
        return 1
    if not str(art_hits[0].get("corrected_sentence") or "").strip():
        print("FAILED:SYN-0015-probe1 artifact flag has empty rewrite")
        return 1
    if str(art_hits[0].get("underlying_work_verdict")) != "CONFIRMED":
        print("FAILED:SYN-0015-probe1 rewrite is a work defect; must be CONFIRMED")
        return 1
    mp = art_hits[0].get("measured_population") or {}
    if mp.get("measured_n") != 12 or mp.get("population_n") != 103:
        print("FAILED:SYN-0015-probe1 artifact denominator is not 12 of 103")
        return 1
    honest, why = C.artifact_honesty(doc)
    print(f"artifact_honesty={honest} {why}")
    if not honest:
        print("FAILED:SYN-0015-probe1 artifact honesty")
        return 1
    rec = S.load_receipt(HERE / "fixtures" / "known-present" / "receipt.json")
    print(f"receipt_measured={rec['measured_n']} of {rec['population_n']}")
    print("SUCCESS:SYN-0015-probe1 known-present overclaim fires with rewrite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
