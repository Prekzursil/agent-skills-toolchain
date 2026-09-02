#!/usr/bin/env python3
"""Probe 2: independent re-derivation of selection-diff and unreachability.

Runs the router on the raw fixtures first. Computes changed-task count,
previously-selected-now-unreachable, and the never-selected classification
WITHOUT reading the confirmation artifact's answers. Only then compares
those derived values to the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import selection as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0055-router-selection-diff.json"


def main() -> int:
    # Derive first. Do not load the artifact until after these numbers exist.
    measured = S.measure()
    derived_changed = int(measured["changed_count"])
    derived_unreach = list(measured["previously_selected_now_unreachable"])
    derived_never = [
        u["capability_id"]
        for u in measured["before_unreachable"]
        if u.get("classification") == "routing-defect"
    ]
    never_as_gap = [
        u["capability_id"]
        for u in measured["before_unreachable"]
        if u.get("classification") == "corpus-gap"
    ]
    planted_after = "skill.secret-scan" in derived_unreach
    dead_letter = "skill.dead-letter" in derived_never
    print(
        "derived_changed="
        + str(derived_changed)
        + " derived_now_unreach="
        + json.dumps(derived_unreach)
        + " routing_defects="
        + json.dumps(derived_never)
        + " planted_after="
        + str(planted_after)
        + " dead_letter_routing_defect="
        + str(dead_letter)
    )
    if never_as_gap:
        print("FAILED:CNF-0055-probe2 never-selected classified as corpus-gap", never_as_gap)
        return 1
    if not dead_letter:
        print("FAILED:CNF-0055-probe2 skill.dead-letter not reported as routing-defect")
        return 1
    if not planted_after:
        print("FAILED:CNF-0055-probe2 planted after-state did not make secret-scan unreachable")
        return 1
    if derived_changed < 1:
        print("FAILED:CNF-0055-probe2 detector silent on known-broken after fixture")
        return 1
    if not measured["control_ok"]:
        print("FAILED:CNF-0055-probe2 before-state control regressing")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0055-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    answers = S.artifact_field(doc, "answers") or {}
    delta = S.artifact_field(doc, "delta") or {}
    recorded_changed = int(delta.get("changed_count") if "changed_count" in delta else answers.get("tasks_with_topk_change") or -1)
    recorded_unreach = list(
        delta.get("previously_selected_now_unreachable")
        or answers.get("previously_selected_now_unreachable")
        or []
    )
    if recorded_changed != derived_changed:
        print(
            f"FAILED:CNF-0055-probe2 changed_count artifact={recorded_changed} derived={derived_changed}"
        )
        return 1
    if sorted(recorded_unreach) != sorted(derived_unreach):
        print(
            "FAILED:CNF-0055-probe2 unreachable set mismatch "
            f"artifact={recorded_unreach} derived={derived_unreach}"
        )
        return 1
    if answers.get("never_selected_classified_as") != "routing-defect":
        print("FAILED:CNF-0055-probe2 artifact did not classify never-selected as routing-defect")
        return 1
    if answers.get("never_selected_not") != "corpus-gap":
        print("FAILED:CNF-0055-probe2 artifact omitted not-corpus-gap")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0055-probe2 self-declared", doc.get("state"))
        return 1
    print("SUCCESS:CNF-0055-probe2 unreachable re-derived; routing-defect not corpus-gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
