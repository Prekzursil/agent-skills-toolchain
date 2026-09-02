#!/usr/bin/env python3
"""Probe 1: present-tense finding, both-states, ground-truth coverage.

Must fire on a document that states a fixed problem in present tense even
when the architecture-side collision count is 0. Must be silent on a
reconciled past-tense rewrite. Must cover documents READ as ground truth,
not only code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0125-stale-premise-sweep.json"


def main() -> int:
    bs = S.both_states_present_tense()
    print(
        f"fires_on_present_tense_with_real_fix={bs['fires_on_present_tense_with_real_fix']}"
    )
    print(f"silent_on_reconciled_past_tense={bs['silent_on_reconciled_past_tense']}")
    print(f"fix_real_bare_m_nn={bs['fix_real_bare_m_nn']}")
    if not bs.get("ok"):
        print("FAILED:CNF-0125-probe1 both-states present-tense control")
        return 1

    report = S.run_sweep(REPO)
    premises = report["premises"]
    headline = report["headline"]

    present = [
        p
        for p in premises
        if p.get("id") == "FIX-DECISION-LOG-PRESENT-TENSE"
        and p.get("classification") == "stale-premise"
        and p.get("is_ground_truth_document") is True
    ]
    print(f"present_tense_finding_rows={len(present)}")
    if not present:
        print("FAILED:CNF-0125-probe1 present-tense document was not a finding")
        return 1

    inherited = [
        p
        for p in premises
        if p.get("id") == "FIX-BRIEF-F-B-02"
        and p.get("classification") == "inherited-false-blocker"
        and p.get("is_ground_truth_document") is True
    ]
    print(f"brief_inherited_rows={len(inherited)}")
    if not inherited:
        print("FAILED:CNF-0125-probe1 program brief was not an inherited-false-blocker")
        return 1

    gt_sources = {
        p.get("source")
        for p in premises
        if p.get("is_ground_truth_document") is True
    }
    code_only = all("ground-truth" not in str(s) for s in gt_sources)
    print(f"ground_truth_sources={sorted(gt_sources)}")
    if code_only or len(gt_sources) < 2:
        print("FAILED:CNF-0125-probe1 sweep covered code only")
        return 1
    if not headline.get("ground_truth_documents_covered"):
        print("FAILED:CNF-0125-probe1 headline ground-truth coverage false")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0125-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0125-probe1 self-declared {doc.get('state')}")
        return 1
    art_ids = {p.get("id") for p in (doc.get("premises") or [])}
    if "FIX-DECISION-LOG-PRESENT-TENSE" not in art_ids:
        print("FAILED:CNF-0125-probe1 artifact omitted present-tense finding")
        return 1
    if "FIX-BRIEF-F-B-02" not in art_ids:
        print("FAILED:CNF-0125-probe1 artifact omitted program-brief finding")
        return 1

    print(
        "SUCCESS:CNF-0125-probe1 present-tense-finding both-states "
        "ground-truth-docs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
