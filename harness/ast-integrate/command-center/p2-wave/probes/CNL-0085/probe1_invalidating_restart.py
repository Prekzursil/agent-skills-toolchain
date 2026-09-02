#!/usr/bin/env python3
"""Probe 1: an invalidating change must force a recorded restart.

Mechanism: classifier disposition + presence of restart_record on the event log.
Does not hash pause snapshots (that is probe 2).

Negative control (verbatim): the check refuses quiet continuation of a
question_change (fixtures/quiet-continuation.json). On that planted-bad state
it raises QuietContinuationRefused and does not append an owner_intervention
event to the same run_id. On evidence_add it stays silent (CONTINUE, same run).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from intervention import (  # noqa: E402
    CONTINUE,
    RESTART,
    QuietContinuationRefused,
    apply_intervention,
    classify,
    hash_prefix,
)
from scenario import OPS, scripted_run  # noqa: E402

BAD = HERE / "fixtures" / "quiet-continuation.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0085-probe1 {msg}")
    return 1


def main() -> int:
    planted = json.loads(BAD.read_text(encoding="utf-8"))
    rows = []

    for name in ("evidence_add", "budget_extend"):
        run = scripted_run(run_id=f"run-{name}")
        cursor = len(run.events)
        before = hash_prefix(run.events)
        before_votes = list(run.votes)
        before_dissent = list(run.minority_reports)
        result = apply_intervention(run, OPS[name])
        if result["applied"] != CONTINUE or result["same_run_continued"] is not True:
            return fail(f"{name} did not CONTINUE")
        if run.restart_record is not None:
            return fail(f"{name} wrote a restart_record")
        if hash_prefix(run.events[:cursor]) != before:
            return fail(f"{name} mutated the committed prefix")
        if run.votes != before_votes or run.minority_reports != before_dissent:
            return fail(f"{name} rewrote votes or dissent")
        if classify(OPS[name], run=scripted_run())["disposition"] != CONTINUE:
            return fail(f"{name} classify != CONTINUE")
        rows.append(
            {
                "op": name,
                "disposition": CONTINUE,
                "restart_record": False,
                "prefix_preserved": True,
                "dissent_preserved": True,
            }
        )

    for name in ("question_change", "chair_replace", "evidence_rewrite"):
        run = scripted_run(run_id=f"run-{name}")
        before = hash_prefix(run.events)
        result = apply_intervention(run, OPS[name])
        if result["applied"] != RESTART or result["same_run_continued"] is not False:
            return fail(f"{name} did not RESTART")
        rec = run.restart_record
        if not isinstance(rec, dict) or rec.get("invalidates_run") is not True:
            return fail(f"{name} missing restart_record")
        if rec.get("old_run_id") != run.run_id:
            return fail(f"{name} restart_record run_id mismatch")
        if rec.get("prefix_sha256") != before:
            return fail(f"{name} restart_record prefix hash mismatch")
        if run.status != "RESTART_REQUIRED":
            return fail(f"{name} status={run.status}")
        # Quiet continuation must not have happened: no owner_intervention CONTINUE event.
        continue_events = [
            e
            for e in run.events
            if e.get("type") == "owner_intervention" and e.get("invalidates_run") is False
        ]
        if continue_events:
            return fail(f"{name} quietly continued")
        rows.append(
            {
                "op": name,
                "disposition": RESTART,
                "restart_record": True,
                "quiet_continuation": False,
            }
        )

    # Negative control: planted-bad quiet continuation of question_change.
    run = scripted_run(run_id="run-quiet-bad")
    n_before = len(run.events)
    refused = False
    try:
        apply_intervention(run, planted, force_continue=True)
    except QuietContinuationRefused as exc:
        refused = True
        refused_msg = str(exc)
    else:
        return fail("quiet continuation of question_change was accepted")
    if len(run.events) != n_before:
        return fail("quiet-continuation attempt mutated the log")
    if run.status != "LIVE" or run.restart_record is not None:
        return fail("quiet-continuation attempt closed the run without an explicit restart apply")

    # Both-states: the same check is silent on evidence_add (already asserted CONTINUE).
    negative = {
        "id": "quiet-continuation-question-change",
        "state_meant_to_reject": str(BAD.relative_to(REPO)),
        "what_the_check_does": (
            "raises QuietContinuationRefused on question_change with mode=continue "
            "or force_continue=True; does not append owner_intervention to the same "
            "run_id; does not rewrite prefix events. Silent (CONTINUE) on evidence_add."
        ),
        "fired": refused,
        "verbatim_exception": refused_msg,
        "events_unchanged": True,
    }

    out = {
        "probe": "probe1-invalidating-restart",
        "unit_id": "CNL-0085",
        "pass": True,
        "rows": rows,
        "negative_control": negative,
    }
    print(json.dumps(out, sort_keys=True, ensure_ascii=True))
    print(
        "question_change restart_record=True quiet_continuation=False "
        "evidence_add CONTINUE prefix_preserved=True"
    )
    print(
        "NEGATIVE CONTROL rejects quiet continuation of question_change; "
        f"exception={refused_msg}"
    )
    print("SUCCESS:CNL-0085-probe1 invalidating change forces recorded restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
