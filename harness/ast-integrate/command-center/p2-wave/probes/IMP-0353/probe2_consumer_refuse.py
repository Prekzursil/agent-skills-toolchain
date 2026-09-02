#!/usr/bin/env python3
"""Probe 2: downstream consumer refuses an aborted artifact as a decision.

Starts from consume_as_decision / strip_aborted_label, not an author summary.

Evidence requirement (1): consumer refuses the aborted artifact.
Negative control: strip the aborted label and the same consumer accepts.
Silent-on-good: a completed council is accepted.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.abort import (  # noqa: E402
    ABORTED_LABEL,
    NotADecision,
    consume_as_decision,
    run_council,
    strip_aborted_label,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0353-p2-") as td:
        root = Path(td)
        done = run_council(
            root / "complete.clog",
            council_id="completed",
            artifact_path=root / "complete.json",
        )
        killed = run_council(
            root / "aborted.clog",
            council_id="aborted",
            abort_after_events=6,
            tear_after_bytes=None,
            owner_id="owner",
            abort_reason="kill-switch",
            artifact_path=root / "aborted.json",
        )
        art_aborted = killed["artifact"]
        art_done = done["artifact"]

        if art_aborted.get("abort_label") != ABORTED_LABEL:
            print("FAILED:IMP-0353-probe2 aborted artifact missing ABORTED label")
            return 1
        if art_aborted.get("decision") is None:
            print("FAILED:IMP-0353-probe2 aborted artifact has no decision payload to misuse")
            return 1
        if art_done.get("abort_label") is not None:
            print("FAILED:IMP-0353-probe2 completed artifact is labelled aborted")
            return 1

        refused = False
        reason = ""
        try:
            consume_as_decision(art_aborted)
        except NotADecision as exc:
            refused = True
            reason = str(exc)

        stripped = strip_aborted_label(art_aborted)
        if "abort_label" in stripped:
            print("FAILED:IMP-0353-probe2 strip_aborted_label left abort_label")
            return 1
        accepted_stripped = False
        try:
            consume_as_decision(stripped)
            accepted_stripped = True
        except NotADecision:
            accepted_stripped = False

        still_refused = False
        try:
            consume_as_decision(art_aborted)
        except NotADecision:
            still_refused = True

        accepted_done = False
        try:
            consume_as_decision(art_done)
            accepted_done = True
        except NotADecision:
            accepted_done = False

        out = {
            "probe": "probe2-consumer-refuse",
            "unit_id": "IMP-0353",
            "refused_aborted": refused,
            "refused_reason": reason,
            "accepted_stripped_label": accepted_stripped,
            "original_still_refused": still_refused,
            "accepted_completed": accepted_done,
            "aborted_has_decision_payload": art_aborted.get("decision") is not None,
            "pass": refused and accepted_stripped and still_refused and accepted_done,
        }
        print(json.dumps(out, sort_keys=True))
        if not out["pass"]:
            print("FAILED:IMP-0353-probe2 consumer both-states")
            return 1
        print("SUCCESS:IMP-0353-probe2 consumer refuses aborted; strip-label accepts")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
