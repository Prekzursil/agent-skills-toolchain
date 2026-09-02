#!/usr/bin/env python3
"""Probe 1: golden ACCEPT + four contracted mutants REJECT (detector control).

Both-states: a validator that ACCEPTS the golden and REJECTS each mutant on
its own condition. Silent-on-both or reject-everything fails this probe.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

import receipt_validate as V  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "CC-0002.json"
VALIDATOR = REPO / "command-center" / "receipt_validate.py"


def main() -> int:
    st_rc, st_out = V.run_self_test(REPO)
    print(st_out)
    if st_rc != 0:
        print("FAILED:CC-0002-probe1 self-test")
        return 1
    if st_out.count("got=REJECT") != 4:
        print("FAILED:CC-0002-probe1 expected 4 REJECT rows")
        return 1
    if "want=ACCEPT got=ACCEPT" not in st_out:
        print("FAILED:CC-0002-probe1 golden did not ACCEPT")
        return 1

    empty = subprocess.run(
        [sys.executable, "-B", str(VALIDATOR)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if empty.returncode == 0:
        print("FAILED:CC-0002-probe1 empty walk exited 0")
        return 1
    print(f"empty-walk rc={empty.returncode} fail-closed=True")

    if not RECEIPT.is_file():
        print("FAILED:CC-0002-probe1 live receipt absent")
        return 1
    live = json.loads(RECEIPT.read_text(encoding="utf-8"))
    text = RECEIPT.read_text(encoding="utf-8")
    if "SUCCESS:CC-0002" not in text:
        print("FAILED:CC-0002-probe1 sentinel absent from live receipt")
        return 1
    if str(live.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CC-0002-probe1 self-declared {live.get('state')}")
        return 1

    v, c, r = V.admit_doc(live, REPO)
    print(f"live-receipt verdict={v} codes={c}")
    if v != "ACCEPT":
        print("FAILED:CC-0002-probe1 live receipt not ACCEPT")
        for line in r:
            print(f"  {line}")
        return 1

    # Same four mutants applied to the LIVE self-demonstrating receipt.
    live_mutants = [
        ("m1", V.mutant_m1_missing_completion_sentinel(live), "C2"),
        ("m2", V.mutant_m2_empty_evidence(live), "C2"),
        ("m3", V.mutant_m3_unit_id_not_in_catalog(live), "C3"),
    ]
    for name, doc, expect in live_mutants:
        mv, mc, mr = V.admit_doc(doc, REPO)
        print(f"live-{name} verdict={mv} codes={mc}")
        if mv != "REJECT" or expect not in mc:
            print(f"FAILED:CC-0002-probe1 live {name} want REJECT {expect}")
            for line in mr:
                print(f"  {line}")
            return 1
    m4v, m4c, m4r = V.admit_text(V.mutant_m4_unparseable(), REPO)
    print(f"live-m4 verdict={m4v} codes={m4c}")
    if m4v != "REJECT" or "C1" not in m4c:
        print("FAILED:CC-0002-probe1 live m4")
        return 1

    print(
        "SUCCESS:CC-0002-probe1 detector-control golden-accept four-mutants-reject fail-closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
