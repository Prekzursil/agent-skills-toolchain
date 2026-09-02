#!/usr/bin/env python3
"""Named probe 2: filler-only participation must FAIL the floor.

Starts from the public scorer and the hand-labelled fixture, not from the
author's receipt summary. Reconstructs three empty acknowledgements as raw
strings. Also runs a message-count mutant and a both-states check.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
SAMPLE = HERE / "fixtures" / "hand_labelled_turns.json"
ENGAGEMENT = TOOLS / "council" / "budget" / "engagement.py"
sys.path.insert(0, str(TOOLS))

from council.budget.engagement import (  # noqa: E402
    FLOOR_FAIL,
    EngagementPolicy,
    EngagementTracker,
    content_unit_count,
    score_labelled_sample,
    score_text,
)

CLAIM = "The kernel must record every turn event; a topology write is a bypass."
ACKS = ("ok", "ack", "thanks")


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0299-probe2 {msg}")
    return 1


def main() -> int:
    if not SAMPLE.is_file():
        return fail("hand-labelled sample missing")

    policy = EngagementPolicy(min_content_units=1)
    filler = EngagementTracker(policy, {"seat-a": "seat-a"})
    for msg in ACKS:
        scored = score_text(msg)
        if scored["content_units"] != 0 or not scored["filler_only"]:
            return fail(f"ack scored as substantive: {msg!r} -> {scored}")
        filler.record_turn("seat-a", msg, round_no=1)
    st = filler.status("seat-a")
    if st["message_count"] != 3:
        return fail(f"message_count={st['message_count']}")
    if st["content_units"] != 0:
        return fail(f"content_units={st['content_units']} for filler-only")
    if st["meets_floor"]:
        return fail("NEGATIVE CONTROL FAILED: filler-only satisfied the floor")
    handoffs = filler.evaluate_checkpoint(["seat-a"])
    if not handoffs or handoffs[0].reason != FLOOR_FAIL:
        return fail(f"filler-only checkpoint silent: {handoffs}")

    mutant_would_pass = st["message_count"] >= policy.min_content_units
    honest_passes = st["content_units"] >= policy.min_content_units
    if not mutant_would_pass or honest_passes:
        return fail("content-unit metric collapsed into message count")

    good = EngagementTracker(policy, {"seat-b": "seat-b"})
    good.record_turn("seat-b", CLAIM, round_no=1)
    gst = good.status("seat-b")
    if not gst["meets_floor"] or gst["content_units"] < 1:
        return fail("both-states: a real claim failed the floor")
    if good.evaluate_checkpoint(["seat-b"]):
        return fail("both-states: engaged seat emitted FLOOR_FAIL")

    labelled = score_labelled_sample(SAMPLE)
    if labelled["n"] < 16:
        return fail(f"labelled sample too small n={labelled['n']}")
    if labelled["disagreements"]:
        return fail(
            "labelled disagreements "
            + json.dumps(labelled["disagreements"][:5], sort_keys=True)
        )
    if labelled["agreement"] != 1.0:
        return fail(f"agreement={labelled['agreement']}")

    if content_unit_count("ok") != 0:
        return fail("ok counted as a content unit")
    if content_unit_count(CLAIM) < 1:
        return fail("claim counted as zero content units")

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(TOOLS)
    cli = subprocess.run(
        [sys.executable, "-B", str(ENGAGEMENT), "--three-acks"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    if cli.returncode != 0:
        return fail(f"cli --three-acks rc={cli.returncode} {cli.stderr[-800:]}")
    cli_doc = json.loads(cli.stdout)
    if cli_doc.get("meets_floor") is not False or cli_doc.get("content_units") != 0:
        return fail(f"cli disagreed with in-process scorer: {cli_doc}")

    payload = {
        "probe": "probe2-filler-negative",
        "unit_id": "IMP-0299",
        "pass": True,
        "negative_control": {
            "id": "IMP-0299-FILLER-ONLY-FAILS-FLOOR",
            "fired": True,
            "meets_floor": False,
            "content_units": st["content_units"],
            "message_count": st["message_count"],
        },
        "both_states": {"filler_fires": True, "claim_silent": True},
        "message_count_mutant_would_pass": mutant_would_pass,
        "honest_metric_passes": honest_passes,
        "labelled_sample": {
            "n": labelled["n"],
            "agree": labelled["agree"],
            "agreement": labelled["agreement"],
        },
        "cli_three_acks_meets_floor": cli_doc.get("meets_floor"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"filler_only meets_floor=False labelled_agreement={labelled['agreement']}")
    print("SUCCESS:IMP-0299-probe2 filler-only participation fails the floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
