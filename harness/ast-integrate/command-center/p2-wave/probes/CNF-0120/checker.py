#!/usr/bin/env python3
"""Document-level checks for a CNF-0120 confirmation-audit artifact."""
from __future__ import annotations

from typing import Any

THREE = frozenset({"ABSENT", "EMPTY", "GENUINE_ZERO"})
INTEGRITY = frozenset({"NOT-CHECKED", "ABSENT", "FOLDED-INTO-PASS", "CHECKED"})
SENTINEL = (
    "SUCCESS:CNF-0120 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every item carries one of "
    "the three states with the distinguishing evidence, and the planted "
    "unlabelled item was caught. Any other terminal state is FAILED:CNF-0120 "
    "<classification> with the diagnostic tail attached."
)


def check_artifact(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    if doc.get("unit_id") != "CNF-0120":
        return False, f"unit_id:{doc.get('unit_id')}"
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    if SENTINEL not in (doc.get("sentinel") or "") and SENTINEL not in str(doc):
        return False, "sentinel-absent"
    items = doc.get("items")
    if not isinstance(items, list) or len(items) < 4:
        return False, "items-missing-or-short"
    for i, row in enumerate(items):
        if not isinstance(row, dict):
            return False, f"items[{i}]-not-object"
        three = row.get("three_state")
        if three not in THREE:
            return False, f"items[{i}]-bad-three_state:{three}"
        integ = row.get("integrity_class")
        if integ not in INTEGRITY:
            return False, f"items[{i}]-bad-integrity:{integ}"
        ev = row.get("evidence")
        if not isinstance(ev, dict):
            return False, f"items[{i}]-evidence-missing"
        if "subject_exists" not in ev or "probe_ran" not in ev:
            return False, f"items[{i}]-evidence-incomplete"
        why = str(ev.get("why_not_the_other_two") or "")
        if len(why) < 16:
            return False, f"items[{i}]-no-distinguishing-evidence"
        if three == "ABSENT" and ev.get("finding_count") == 0 and ev.get("probe_ran") is True:
            return False, f"items[{i}]-absent-folded-into-zero"
        if three == "ABSENT" and ev.get("subject_exists") is True and ev.get("probe_ran") is True:
            # Present subject with a completed probe cannot be ABSENT.
            if ev.get("finding_count") == 0:
                return False, f"items[{i}]-absent-vs-zero-merged"
    idx = {str(r.get("id")): r for r in items if isinstance(r, dict)}
    planted = idx.get("FIXTURE-PLANTED-UNLABELLED")
    if not planted or planted.get("integrity_class") != "FOLDED-INTO-PASS":
        return False, "planted-unlabelled-not-caught"
    absent = idx.get("FIXTURE-ABSENT-DIR")
    if not absent or absent.get("three_state") != "ABSENT":
        return False, "absent-dir-not-ABSENT"
    if absent.get("three_state") == "GENUINE_ZERO":
        return False, "absent-dir-reported-as-nothing-to-check"
    empty_d = idx.get("FIXTURE-EMPTY-DIR")
    empty_a = idx.get("FIXTURE-EMPTY-ARRAY")
    if not empty_d or empty_d.get("three_state") != "EMPTY":
        return False, "empty-dir-not-EMPTY"
    if not empty_a or empty_a.get("three_state") != "EMPTY":
        return False, "empty-array-not-EMPTY"
    zero = idx.get("FIXTURE-GENUINE-ZERO")
    if not zero or zero.get("three_state") != "GENUINE_ZERO":
        return False, "genuine-zero-not-GENUINE_ZERO"
    gate = idx.get("FIXTURE-UNRUNNABLE-GATE")
    if not gate or gate.get("integrity_class") != "NOT-CHECKED":
        return False, "unrunnable-gate-not-NOT-CHECKED"
    if gate.get("integrity_class") == "FOLDED-INTO-PASS":
        return False, "unrunnable-gate-silent-pass"
    labelled = idx.get("FIXTURE-LABELLED-NOT-CHECKED")
    if not labelled or labelled.get("integrity_class") != "NOT-CHECKED":
        return False, "labelled-control-misclassified"
    ctrl = doc.get("controls") or {}
    if ctrl.get("planted_unlabelled_caught") is not True:
        return False, "controls.planted_unlabelled_caught-not-true"
    if ctrl.get("absent_dir_not_nothing_to_check") is not True:
        return False, "controls.absent_dir-not-true"
    if ctrl.get("unrunnable_gate_not_silent_pass") is not True:
        return False, "controls.unrunnable-not-true"
    sm = doc.get("summary") or {}
    if int(sm.get("folded_into_pass") or 0) < 1:
        return False, "summary-folded-into-pass-zero"
    return True, f"items={len(items)} folded={sm.get('folded_into_pass')} absent={sm.get('absent')}"
