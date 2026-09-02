#!/usr/bin/env python3
"""Named probe 2: quote-in-capture + overclaim mutants (partitioned evidence).

This half does not re-score HTTP/sha structure (probe 1's partition). It
requires every recorded quote to occur in the captured bytes (or decoded
GitHub contents), and it requires known-broken mutants to fail:

* CORROBORATED with zero counter-cases (untested inherited position)
* quote not present in the capture
* missing Jenkins counter-case
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402


def main() -> int:
    art = C.REPO / C.ART_REL
    if not art.is_file():
        print("FAILED:RES-0067-probe2 artifact missing")
        return 1
    doc = C.load_artifact()

    ok, why = C.check_quotes(doc)
    print(f"quotes_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0067-probe2 quotes")
        return 1

    ok, why = C.check_anti_adoption(doc)
    print(f"anti_adoption_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0067-probe2 anti-adoption")
        return 1

    aa = doc.get("anti_adoption") or {}
    verdict = str(aa.get("verdict") or "").upper()
    print(f"live_verdict={verdict}")
    if verdict not in C.VERDICTS:
        print("FAILED:RES-0067-probe2 verdict missing")
        return 1

    m1 = copy.deepcopy(doc)
    m1["anti_adoption"]["verdict"] = "CORROBORATED"
    m1["counter_cases"] = []
    mok, mwhy = C.check_anti_adoption(m1)
    print(f"untested_corroboration_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0067-probe2 untested corroboration was accepted")
        return 1

    m2 = copy.deepcopy(doc)
    m2["claims"][0]["rails"][1]["quote"] = "THIS-QUOTE-IS-NOT-IN-ANY-CAPTURE-BYTES"
    mok, mwhy = C.check_quotes(m2)
    print(f"fabricated_quote_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0067-probe2 fabricated quote was accepted")
        return 1

    m3 = copy.deepcopy(doc)
    m3["counter_cases"] = [
        {
            "id": "CC-NOT-JENKINS",
            "engine": "Unrelated",
            "cuts_against_anti_adoption": True,
            "summary": "placeholder without the named Scripted-to-Declarative counter-case",
        }
    ]
    mok, mwhy = C.check_anti_adoption(m3)
    print(f"jenkins_stripped_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0067-probe2 jenkins-stripped counter-case was accepted")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("partitioned_evidence") is not True:
        print("FAILED:RES-0067-probe2 reviewer partition flags")
        return 1
    if rev.get("scope_not_agreement") is not True:
        print("FAILED:RES-0067-probe2 reviewer is agreement-mode")
        return 1

    print(
        "SUCCESS:RES-0067-probe2 quotes mutants partitioned-reviewer "
        f"verdict={verdict}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
