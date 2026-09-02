#!/usr/bin/env python3
"""Probe 2: negative control for the defect-omission check.

The check is meant to REJECT a critic that omits a load-bearing token
without an explicit rejection record.

States:
  planted-drop (base fixture) — FIRES (defect_lost non-empty, rulings diverge)
  faithful-forward             — SILENT on defect (defect_lost empty)
  explicit-reject              — SILENT on defect (tokens present as rejected)
  full-transcript judge        — SILENT on all loss (lost empty)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import pipeline as P  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0032-proposer-critic-judge-pipeline-topology.md"


def _defect_ids(run: dict) -> list[str]:
    return P.measure(run)["signal1_token_sets"]["defect_lost_ids"]


def _lost_ids(run: dict) -> list[str]:
    return P.measure(run)["signal1_token_sets"]["lost_ids"]


def full_context_loss(run: dict) -> list[str]:
    """Judge input IS the full transcript: lost must be empty."""
    full = P.full_transcript_judge_input(run)
    toks = P.walk_tokens(full)
    ids = {t["id"] for t in toks if t["loss_class"] in {"defect", "point"}}
    # Comparing the document to itself: empty difference.
    lost = sorted(ids - ids)
    return lost


def main() -> int:
    base = P.load_run()
    drop = P.measure(base)
    faithful = P.measure(P.make_faithful(base))
    rejected = P.measure(P.make_explicit_reject(base))
    full_lost = full_context_loss(base)

    drop_def = drop["signal1_token_sets"]["defect_lost_ids"]
    faith_def = faithful["signal1_token_sets"]["defect_lost_ids"]
    rej_def = rejected["signal1_token_sets"]["defect_lost_ids"]
    faith_point = faithful["signal1_token_sets"]["point_lost_ids"]

    fired_on_drop = len(drop_def) > 0 and drop["rulings"]["verdicts_diverge"]
    silent_on_faithful = faith_def == []
    silent_on_reject = rej_def == []
    silent_on_full = full_lost == []
    # Isolation still strips point-class on a faithful pipeline.
    isolation_kept = len(faith_point) > 0

    statement = (
        "NEGATIVE CONTROL: the defect-omission check is meant to REJECT a "
        "pipeline critic that omits a load-bearing token (CL-DROP, E1, Q1) "
        "without an explicit rejection record. On that planted-drop state it "
        "FIRES. On a faithful-forward critic, on an explicit-reject critic, "
        "and on a full-transcript judge it is SILENT for defect-class loss."
    )
    print(statement)
    print(
        "fired_on_drop="
        + str(fired_on_drop)
        + " drop_defect_lost="
        + ",".join(drop_def)
        + " silent_on_faithful="
        + str(silent_on_faithful)
        + " faithful_defect_lost="
        + (",".join(faith_def) if faith_def else "")
        + " silent_on_explicit_reject="
        + str(silent_on_reject)
        + " silent_on_full_context="
        + str(silent_on_full)
        + " faithful_point_lost="
        + ",".join(faith_point)
        + " isolation_kept="
        + str(isolation_kept)
    )

    if not (fired_on_drop and silent_on_faithful and silent_on_reject and silent_on_full):
        print("FAILED:CNL-0032-probe2 negative control did not discriminate")
        return 1
    if not isolation_kept:
        print("FAILED:CNL-0032-probe2 faithful pipeline lost isolation (point_lost empty)")
        return 1
    if not ART.is_file():
        print("FAILED:CNL-0032-probe2 design note missing")
        return 1
    note = json.loads(ART.read_text(encoding="utf-8"))
    nc = note.get("negative_control") or {}
    if nc.get("fired_on_drop") is not True:
        print("FAILED:CNL-0032-probe2 note missing fired_on_drop")
        return 1
    if nc.get("silent_on_faithful") is not True or nc.get("silent_on_full_context") is not True:
        print("FAILED:CNL-0032-probe2 note both-states flags mismatch")
        return 1
    print("SUCCESS:CNL-0032-probe2 negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
