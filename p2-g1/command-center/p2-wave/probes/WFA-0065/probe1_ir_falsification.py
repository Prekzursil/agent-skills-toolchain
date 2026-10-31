#!/usr/bin/env python3
"""Probe 1: IR expressibility + falsification both-states control.

Live artifact must pass. Stripping a falsification or adopting an unknown IR
kind must fail. Speculative and evidence-backed lists must stay disjoint.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
from check import check_artifact  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0065-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    scan = corpus.scan()
    ok, errs = check_artifact(doc, scan)
    print(f"live_ok={ok} errs={errs[:8]}")
    if not ok:
        print("FAILED:WFA-0065-probe1 live artifact rejected")
        for e in errs:
            print(" ", e)
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["evidence_backed_transfers"]:
        if row.get("falsification"):
            del row["falsification"]
            stripped = True
            break
    if not stripped:
        print("FAILED:WFA-0065-probe1 no falsification to strip")
        return 1
    mok, merrs = check_artifact(mutant, scan)
    print(f"mutant_no_falsification ok={mok} sample={merrs[:4]}")
    if mok:
        print("FAILED:WFA-0065-probe1 missing falsification was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    if not mutant2["evidence_backed_transfers"]:
        print("FAILED:WFA-0065-probe1 no adopted rows")
        return 1
    mutant2["evidence_backed_transfers"][0]["mapping_table"].append(
        {
            "source_role_or_step": "planted Byzantine replica",
            "ir_kind": "replica_set",
            "ir_node": "NOT-AN-IR-KIND",
        }
    )
    m2ok, m2errs = check_artifact(mutant2, scan)
    print(f"mutant_illegal_ir ok={m2ok} sample={m2errs[:4]}")
    if m2ok:
        print("FAILED:WFA-0065-probe1 adopted unknown IR kind was accepted")
        return 1

    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0065-probe1 self-declared {doc.get('state')}")
        return 1
    n_adopt = len(doc.get("evidence_backed_transfers") or [])
    n_spec = len(doc.get("speculative_transfers") or [])
    n_oos = len(doc.get("out_of_scope") or [])
    print(f"adopted={n_adopt} speculative={n_spec} out_of_scope={n_oos}")
    print("SUCCESS:WFA-0065-probe1 ir-falsification both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
