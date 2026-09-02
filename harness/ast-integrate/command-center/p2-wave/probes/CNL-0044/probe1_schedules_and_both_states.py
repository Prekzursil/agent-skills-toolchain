#!/usr/bin/env python3
"""Probe 1: 7 turn schedules + both-states control + negative control.

Re-runs live. Does not read the design-note argument.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks as C  # noqa: E402
import enumerate as E  # noqa: E402
import semantics as S  # noqa: E402

RAW = HERE / "probe1-schedules-both-states.raw.json"


def main() -> int:
    fam = E.enumerate_family()
    if not fam["agreement"] or fam["measured_n"] != E.EXPECTED_N:
        print("FAILED:CNL-0044-probe1 family enumeration disagreement", fam["measured_n"])
        return 1
    if fam["library"]["present"] and fam["library_family_n"] not in (None, E.EXPECTED_N):
        print("FAILED:CNL-0044-probe1 library family n mismatch", fam["library_family_n"])
        return 1
    ids = fam["ids"]
    if ids != ["P38", "P39", "P40", "P41", "P42", "P43", "P44"]:
        print("FAILED:CNL-0044-probe1 unexpected ids", ids)
        return 1

    verdicts = S.run_all()
    if len(verdicts) != 7:
        print("FAILED:CNL-0044-probe1 verdict count", len(verdicts))
        return 1
    not_ok = [v for v in verdicts if v["executability"] != "EXECUTABLE"]
    if not_ok:
        print("FAILED:CNL-0044-probe1 known-good case not executable", not_ok)
        return 1

    both = C.both_states(verdicts, ids)
    if not both["ok"]:
        print("FAILED:CNL-0044-probe1 both-states", json.dumps(both, indent=2)[:2000])
        return 1
    neg = C.negative_control(verdicts, ids)
    if not neg["result"]["fired"]:
        print("FAILED:CNL-0044-probe1 negative control did not fire")
        return 1

    dups = S.find_duplicates(fam["records"], fam["other_families"])
    if len(dups) != 1 or dups[0]["tradecraft_id"] != "P43" or dups[0]["other_id"] != "P48":
        print("FAILED:CNL-0044-probe1 unexpected duplicates", dups)
        return 1

    doc = {
        "probe": "probe1-schedules-and-both-states",
        "unit_id": "CNL-0044",
        "family": fam["family"],
        "family_n": fam["measured_n"],
        "ids": ids,
        "library_present": fam["library"]["present"],
        "executable": [v["record_id"] for v in verdicts],
        "artifacts": {
            v["record_id"]: v["artifact"]["name"] for v in verdicts
        },
        "duplicates": dups,
        "both_states": {
            "known_good_silent": both["known_good"]["silent"],
            "planted_bad_fired": both["planted_bad"]["fired"],
            "planted_bad_reasons": both["planted_bad"]["reasons"],
            "ok": both["ok"],
        },
        "negative_control_verbatim": neg["verbatim"],
        "pass": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("family_n", "executable", "artifacts", "duplicates", "both_states")}, indent=2))
    print(neg["verbatim"])
    print("SUCCESS:CNL-0044-probe1 schedules both-states negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
