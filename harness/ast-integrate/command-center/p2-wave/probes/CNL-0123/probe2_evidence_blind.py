#!/usr/bin/env python3
"""Probe 2: evidence-blind parent is detectable; both-states re-run.

Oracle B: digest diff — perturb only child evidence, hold verdicts fixed.
Oracle C: counter assertion — planted vote-counter is evidence-blind.

Catalog reviewer_requirement: re-run both-states (split vs unanimous) before
signing. This probe executes that control independently of the author's prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fanin import DISAGREEMENT, PASS  # noqa: E402
from simulate import NEGATIVE_CONTROL_VERBATIM, run_all  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0123-council-of-councils-fan-in-simulation-including-the-disagr.md"
)


def main() -> int:
    sim = run_all()
    if not sim["labels_held_fixed"] or not sim["paths_held_fixed"]:
        print("FAILED:CNL-0123-probe2 verdicts or paths were not held fixed")
        return 1
    if sim["split_labels"] != ["PASS", "PASS", "REFUTED"]:
        print("FAILED:CNL-0123-probe2 labels", sim["split_labels"])
        return 1
    if not sim["honest_digest_moved"]:
        print("FAILED:CNL-0123-probe2 honest parent digest did not move (vote-counting)")
        return 1
    if sim["vote_digest_moved"]:
        print("FAILED:CNL-0123-probe2 vote-counter moved; control is not evidence-blind")
        return 1
    if not sim["evidence_blind_control_fired"]:
        print("FAILED:CNL-0123-probe2 evidence-blind control did not fire")
        return 1
    if sim["vote_split"]["verdict"] != PASS:
        print("FAILED:CNL-0123-probe2 vote-counter did not emit majority PASS")
        return 1
    if sim["split"]["verdict"] != DISAGREEMENT:
        print("FAILED:CNL-0123-probe2 honest split", sim["split"]["verdict"])
        return 1
    if sim["all_pass"]["verdict"] != PASS:
        print("FAILED:CNL-0123-probe2 both-states all-pass", sim["all_pass"]["verdict"])
        return 1
    if sim["perturbed"]["verdict"] != DISAGREEMENT:
        print("FAILED:CNL-0123-probe2 perturbed verdict", sim["perturbed"]["verdict"])
        return 1

    split_gamma = next(r for r in sim["split"]["children"] if r["id"] == "child-gamma")
    pert_gamma = next(r for r in sim["perturbed"]["children"] if r["id"] == "child-gamma")
    if split_gamma["claimed_verdict"] != "REFUTED" or pert_gamma["claimed_verdict"] != "REFUTED":
        print("FAILED:CNL-0123-probe2 gamma verdict not held")
        return 1
    if split_gamma["evidence_sha256"] == pert_gamma["evidence_sha256"]:
        print("FAILED:CNL-0123-probe2 gamma evidence sha256 did not change")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0123-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0123-probe2 self-declared", doc.get("state"))
        return 1
    controls = doc.get("negative_controls") or []
    if not controls:
        print("FAILED:CNL-0123-probe2 negative_controls missing")
        return 1
    verbatim = str(controls[0].get("verbatim") or "")
    if NEGATIVE_CONTROL_VERBATIM not in verbatim and verbatim != NEGATIVE_CONTROL_VERBATIM:
        print("FAILED:CNL-0123-probe2 negative control not recorded verbatim")
        return 1
    if controls[0].get("fired") is not True:
        print("FAILED:CNL-0123-probe2 negative control fired!=true")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("executed_both_states") is not True:
        print("FAILED:CNL-0123-probe2 reviewer did not execute both-states")
        return 1
    rec = doc.get("simulation") or {}
    if rec.get("honest_digest_moved") is not True:
        print("FAILED:CNL-0123-probe2 artifact honest_digest_moved")
        return 1
    if rec.get("vote_digest_moved") is not False:
        print("FAILED:CNL-0123-probe2 artifact vote_digest_moved")
        return 1
    if rec.get("split_parent_digest") != sim["split"]["parent_digest"]:
        print("FAILED:CNL-0123-probe2 artifact split digest")
        return 1
    if rec.get("perturbed_parent_digest") != sim["perturbed"]["parent_digest"]:
        print("FAILED:CNL-0123-probe2 artifact perturbed digest")
        return 1

    print(
        json.dumps(
            {
                    "labels_held_fixed": True,
                "paths_held_fixed": True,
                "honest_digest_moved": True,
                "vote_digest_moved": False,
                "evidence_blind_control_fired": True,
                "split_verdict": sim["split"]["verdict"],
                "all_pass_verdict": sim["all_pass"]["verdict"],
                "vote_verdict": sim["vote_split"]["verdict"],
                "split_gamma_sha256": split_gamma["evidence_sha256"],
                "perturbed_gamma_sha256": pert_gamma["evidence_sha256"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0123-probe2 evidence-blind both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
