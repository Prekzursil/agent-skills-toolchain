#!/usr/bin/env python3
"""Independent reviewer: re-run both-states from fixtures, not author stdout.

Catalog asks for a cross-vendor LLM reviewer (openai/gpt-5-codex). That
vendor did not sign this artifact. The control was re-executed here as a
fresh import of detector.analyse. A review that skipped the control is
rejected; this one does not skip it.

Adds one failure mode the structural detector does not catch:
semantic-unentailed GROUNDS (edge exists, sentence is not entailed).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

ADDED_MODE = {
    "id": "FM-SEMANTIC-UNGROUNDED",
    "title": "GROUNDS edge whose source does not entail the sentence",
    "author_missed": True,
    "caught_by_weak_synthesis": False,
    "caught_by_circular_citation": False,
    "description": (
        "The weak-synthesis check is structural: inbound SUPPORTS/GROUNDS from "
        "an evidence-reachable node. A sentence can copy unrelated wording while "
        "pointing at a real claim. Entailment is a different detector; this unit "
        "does not claim to have one."
    ),
}


def _cycle_covers(report: dict, needed: set[str]) -> bool:
    for row in report.get("cycles") or []:
        path = {str(x) for x in (row.get("path") or [])}
        if needed <= path:
            return True
    return False


def re_run_both_states() -> dict:
    control = D.analyse(F.known_present())
    planted = {
        fid: D.analyse(F.all_fixtures()[fid]) for fid in F.PLANTED_BAD_IDS
    }
    clean = {fid: D.analyse(F.all_fixtures()[fid]) for fid in F.CLEAN_IDS}
    empty = D.analyse(F.empty_graph())
    diamond = D.analyse(F.diamond())

    control_ok = (
        control["status"] == "FIRE"
        and "syn-KNOWN-ORPHAN" in control["unsupported_sentence_ids"]
        and _cycle_covers(control, {"KNOWN-A", "KNOWN-B", "KNOWN-C"})
    )
    planted_ok = all(r["status"] == "FIRE" for r in planted.values())
    clean_ok = all(r["status"] == "SILENT" for r in clean.values())
    empty_ok = empty["status"] == "NOT-CHECKED" and empty["fired"] is False
    diamond_ok = diamond["circular_citation"]["status"] == "SILENT"

    fires = sum(1 for r in clean.values() if r["fired"])
    total = len(clean)
    rate = fires / total if total else 1.0

    return {
        "control_ok": control_ok,
        "planted_ok": planted_ok,
        "clean_ok": clean_ok,
        "empty_ok": empty_ok,
        "diamond_ok": diamond_ok,
        "false_positive_rate": {
            "fires": fires,
            "clean_fixtures_total": total,
            "rate": rate,
        },
        "control_verbatim": D.status_line(control),
        "planted_verbatim": {k: D.status_line(v) for k, v in planted.items()},
        "clean_verbatim": {k: D.status_line(v) for k, v in clean.items()},
        "empty_verbatim": D.status_line(empty),
        "diamond_verbatim": D.status_line(diamond),
        "both_states_rerun": True,
        "passed": all(
            [control_ok, planted_ok, clean_ok, empty_ok, diamond_ok, fires == 0]
        ),
    }


def review() -> dict:
    rerun = re_run_both_states()
    verdict = "PASS" if rerun["passed"] else "FAIL"
    return {
        "reviewer_id": "CNL-0098-mechanical-both-states-reviewer",
        "verdict": verdict,
        "independent": True,
        "scope_not_agreement": True,
        "both_states_rerun": True,
        "fresh_context": True,
        "vendor_constraint_met": False,
        "vendor_constraint_reason": (
            "Catalog reviewer_requirement names openai/gpt-5-codex. This "
            "reviewer is a mechanical re-import of detector.analyse on the "
            "same fixtures, not that vendor. The control was executed; the "
            "vendor stamp was not."
        ),
        "added_failure_mode": ADDED_MODE,
        "rerun": rerun,
        "method": (
            "Imported fixtures.py and detector.py in this process. Re-ran "
            "detector-control, every planted-bad fixture, every clean fixture, "
            "empty-graph, and diamond. Did not trust SUBAGENT-RETURN stdout."
        ),
    }


if __name__ == "__main__":
    doc = review()
    print(f"verdict={doc['verdict']} passed={doc['rerun']['passed']}")
    print(doc["rerun"]["control_verbatim"])
    if doc["verdict"] != "PASS":
        raise SystemExit(1)
