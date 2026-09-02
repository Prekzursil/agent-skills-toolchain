#!/usr/bin/env python3
"""Named probe 2: recruit partition vs consensus leak (IMP-0274).

Catalog tests:
  * evidence: context diff between a recruited seat and an original seat
  * evidence: independence check of the recruit's first output vs consensus
  * negative control: feed the recruit the consensus transcript and assert FIRE
  * both-states: FIRE on planted-bad, SILENT on known-good
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.participants.elastic import (  # noqa: E402
    REASON_FORBIDDEN_KEY,
    REASON_OUTPUT_ECHO,
    context_diff,
    draft_first_position,
    feed_consensus_transcript,
    first_original_context,
    independence_check,
    recruit,
)
from scenario import CONSENSUS, base_run  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0274-probe2 {msg}")
    return 1


def main() -> int:
    # Known-good: honest partition. Recruit must match original shared facts
    # and the independence check must be SILENT.
    good = recruit(base_run(), leak_consensus=False)
    if not good.recruited:
        return _fail("good path did not recruit")
    orig_id, orig_ctx = first_original_context(good.run)
    recruit_row = good.recruited[0]
    rec_ctx = recruit_row["context"]
    good_diff = context_diff(
        orig_ctx,
        rec_ctx,
        original_seat_id=orig_id,
        recruit_seat_id=str(recruit_row["seat_id"]),
    )
    if not good_diff.partition_match:
        return _fail(f"good partition_match false {good_diff.to_dict()}")
    if good_diff.consensus_leaked_to_recruit:
        return _fail("good path leaked consensus")
    if not good_diff.question_equal or not good_diff.shared_evidence_equal:
        return _fail(f"good context diff {good_diff.to_dict()}")
    if "running_consensus" in rec_ctx or rec_ctx.get("transcript"):
        return _fail("good recruit context contains consensus keys")

    good_output = recruit_row["first_output"]
    expected_good = draft_first_position(rec_ctx)
    if good_output != expected_good:
        return _fail("good first_output was not drafted from the partition")
    if CONSENSUS.lower() in good_output.lower():
        return _fail("good first_output restates consensus")
    good_ind = independence_check(rec_ctx, good_output, CONSENSUS)
    if good_ind.fired or good_ind.status != "SILENT":
        return _fail(f"good independence {good_ind.to_dict()}")

    # Planted-bad / negative control: feed the consensus transcript.
    bad = recruit(base_run(), leak_consensus=True)
    if not bad.recruited:
        return _fail("bad path did not recruit")
    _, orig_ctx_b = first_original_context(bad.run)
    bad_row = bad.recruited[0]
    bad_ctx = bad_row["context"]
    # Same helper applied to an already-clean context (verbatim negative control).
    planted = feed_consensus_transcript(
        recruit(base_run(), leak_consensus=False).recruited[0]["context"],
        consensus=CONSENSUS,
        transcript=base_run()["transcript"],
    )
    planted_output = draft_first_position(planted)
    planted_ind = independence_check(planted, planted_output, CONSENSUS)

    bad_diff = context_diff(
        orig_ctx_b,
        bad_ctx,
        original_seat_id=orig_id,
        recruit_seat_id=str(bad_row["seat_id"]),
    )
    if bad_diff.partition_match:
        return _fail("leaked recruit still partition_match")
    if not bad_diff.consensus_leaked_to_recruit:
        return _fail(f"leak not visible in context diff {bad_diff.to_dict()}")
    if REASON_FORBIDDEN_KEY and "running_consensus" not in bad_diff.forbidden_on_recruit:
        return _fail(f"forbidden keys {bad_diff.forbidden_on_recruit}")

    bad_output = bad_row["first_output"]
    if bad_output != CONSENSUS:
        return _fail(f"leaked first_output did not restate consensus: {bad_output!r}")
    bad_ind = independence_check(bad_ctx, bad_output, CONSENSUS)
    if not bad_ind.fired or bad_ind.status != "FIRE":
        return _fail(f"negative control did not FIRE {bad_ind.to_dict()}")
    if REASON_OUTPUT_ECHO not in bad_ind.reasons:
        return _fail(f"echo reason missing {bad_ind.reasons}")
    if not planted_ind.fired or planted_ind.status != "FIRE":
        return _fail(f"feed_consensus_transcript did not FIRE {planted_ind.to_dict()}")
    if planted_output != CONSENSUS:
        return _fail("planted draft did not echo consensus")

    # Both-states: the same check, two fixtures.
    if not (bad_ind.fired and planted_ind.fired and (not good_ind.fired)):
        return _fail("both-states invariant broken")

    payload = {
        "probe": "probe2-independence-and-context-diff",
        "unit_id": "IMP-0274",
        "pass": True,
        "negative_control": {
            "id": "feed-recruit-consensus-transcript",
            "fired_on_bad": True,
            "silent_on_good": True,
            "bad_status": bad_ind.status,
            "good_status": good_ind.status,
            "planted_status": planted_ind.status,
            "bad_reasons": list(bad_ind.reasons),
            "planted_reasons": list(planted_ind.reasons),
        },
        "context_diff_good": good_diff.to_dict(),
        "context_diff_bad": bad_diff.to_dict(),
        "independence_good": good_ind.to_dict(),
        "independence_bad": bad_ind.to_dict(),
        "good_first_output": good_output,
        "bad_first_output": bad_output,
        "running_consensus": CONSENSUS,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "NEGATIVE_CONTROL fired_on_bad=True silent_on_good=True "
        f"bad={bad_ind.status} good={good_ind.status}"
    )
    print("SUCCESS:IMP-0274-probe2 independence check FIRES on consensus transcript")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
