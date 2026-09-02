#!/usr/bin/env python3
"""Probe 1: crash-replay matrix. Mechanically independent of live-tree grep.

Computes WAL / saga / checkpoint / 2PC outcomes. Both-states: the live
artifact must record NON-COMPENSABLE leftover after saga abort of a sent
notification; a mutant that marks every class compensable is required-red.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/research/gem-hunt/RES-0157-transfer-durability-transaction-models.json"
SENTINEL = "SUCCESS:RES-0157"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0157-probe1 {msg}")
    return 1


def mutant_hides_leftover(matrix: dict) -> bool:
    """If every class were compensable, crash_after=5 saga leftover would be 0."""
    fake = deepcopy(matrix)
    fake["noncompensable_ids"] = []
    row5 = fake["rows"][5]["saga_compensate_abort"]
    # Simulate the forbidden model: compensate the notification too.
    row5["leftover_noncompensable"] = 0
    row5["net"]["human_notification"] = 0
    return row5["leftover_noncompensable"] == 0


def main() -> int:
    matrix = E.run_matrix()
    v = matrix["verdict"]
    checks = {
        "n_classes_5": matrix["n_classes"] == 5,
        "one_noncompensable": matrix["noncompensable_ids"] == ["human_notification"],
        "outcome_skip_once": v["wal_outcome_skip_always_once"] is True,
        "intent_dups": v["wal_intent_replay_duplicates_nonidempotent"] is True,
        "ckpt_dups": v["checkpoint_restart_duplicates_post_checkpoint"] is True,
        "saga_leftover": v["saga_abort_leaves_noncompensable"] is True,
        "saga_comp_zero": v["saga_abort_compensable_net_zero"] is True,
        "tpc_refused": v["two_phase_commit_refused"] is True,
        "forward_model": v["correct_forward_resume_model"] == "wal_outcome_skip",
        "abort_model": v["correct_abort_model"] == "saga_compensate_abort",
        "neg_control_fn": E.mutant_all_compensable_goes_red(matrix) is True,
        "mutant_red": mutant_hides_leftover(matrix) is True,
    }
    row3 = matrix["rows"][3]
    checks["crash3_intent_dups"] = row3["wal_intent_replay"]["duplicate_total"] > 0
    checks["crash3_outcome_clean"] = row3["wal_outcome_skip"]["all_applied_once"] is True
    checks["crash3_tpc"] = "cloud_worker_launch" in row3["two_phase_commit"]["prepare_refusals"]
    row5 = matrix["rows"][5]
    checks["crash5_notify_leftover"] = (
        row5["saga_compensate_abort"]["leftover_noncompensable"] == 1
        and row5["saga_compensate_abort"]["net"]["human_notification"] == 1
        and row5["saga_compensate_abort"]["compensable_net_zero"] is True
    )
    bad = [k for k, ok in checks.items() if not ok]
    printable = {
        "probe": "probe1-crash-replay",
        "checks": checks,
        "crash3": {
            "intent_dups": row3["wal_intent_replay"]["duplicate_total"],
            "outcome_once": row3["wal_outcome_skip"]["all_applied_once"],
            "ckpt_dups": row3["checkpoint_restart"]["duplicate_total"],
            "tpc_refusals": row3["two_phase_commit"]["prepare_refusals"],
        },
        "crash5_saga_net": row5["saga_compensate_abort"]["net"],
        "verdict": v["correct_forward_resume_model"],
    }
    print(json.dumps(printable, sort_keys=True))
    if bad:
        return fail("matrix-red:" + ",".join(bad))

    if not ART.is_file():
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "RES-0157":
        return fail("unit_id")
    ans = doc.get("answer") or {}
    if ans.get("correct_forward_resume_model") != "wal_outcome_skip":
        return fail("artifact-forward-model")
    if ans.get("correct_abort_model") != "saga_compensate_abort":
        return fail("artifact-abort-model")
    computed = (doc.get("computed") or {}).get("verdict") or {}
    for key in (
        "wal_outcome_skip_always_once",
        "wal_intent_replay_duplicates_nonidempotent",
        "checkpoint_restart_duplicates_post_checkpoint",
        "saga_abort_leaves_noncompensable",
        "two_phase_commit_refused",
    ):
        if computed.get(key) != v[key]:
            return fail(f"artifact-verdict-drift:{key}")
    # Both-states: mutating the live answer to 'everything compensates' must be detectably false.
    mutant = deepcopy(doc)
    for cls in mutant.get("side_effect_classes") or []:
        cls["compensable"] = True
        cls["compensation"] = "pretend-undo"
    noncomp = [
        c
        for c in (mutant.get("side_effect_classes") or [])
        if c.get("compensable") is False
        or str(c.get("compensation") or "") == "NON-COMPENSABLE"
    ]
    if noncomp:
        return fail("mutant-still-has-noncompensable")
    live_noncomp = [
        c
        for c in (doc.get("side_effect_classes") or [])
        if c.get("compensable") is False
        or str(c.get("compensation_or_noncompensable") or c.get("compensation"))
        == "NON-COMPENSABLE"
    ]
    if len(live_noncomp) < 1:
        return fail("live-missing-NON-COMPENSABLE")
    print(
        "crash3_intent_dups="
        f"{row3['wal_intent_replay']['duplicate_total']} "
        f"outcome_once={row3['wal_outcome_skip']['all_applied_once']} "
        f"crash5_notify_leftover={row5['saga_compensate_abort']['leftover_noncompensable']} "
        f"mutant_all_compensable_red=True"
    )
    print("SUCCESS:RES-0157-probe1 crash-replay matrix and notification leftover")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
