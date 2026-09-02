#!/usr/bin/env python3
"""Probe 2: no CONTEST closed by one side; severed dispatch classifies FAILED.

Re-runs the planted contest and the severed confirmer. Does not rewrite the
synthesis artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import protocol as P  # noqa: E402
from dispatch import run_confirmer, terminal_state, write_prompt  # noqa: E402

ART = REPO / P.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0026-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail(f"artifact missing {P.OUT_REL}")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = P.domain(doc)
    if str(doc.get("state") or payload.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"state={doc.get('state')}")

    try:
        P.assert_contests_anchored_and_open(payload.get("lenses") or [])
    except (P.ContestAnchorError, P.UnilateralCloseError) as exc:
        return fail(str(exc))

    planted = P.planted_contest()
    if planted.status != P.CONTEST or not planted.open:
        return fail(f"planted not open CONTEST: {planted.to_dict()}")
    if not planted.raw_anchor or "planted-contest.json" not in planted.raw_anchor:
        return fail(f"planted missing raw anchor {planted.raw_anchor}")
    first_label = planted.first.label
    second_label = planted.second.label
    try:
        planted.close_unilaterally("first")
        return fail("first side closed the CONTEST")
    except P.UnilateralCloseError:
        pass
    try:
        planted.close_unilaterally("second")
        return fail("second side closed the CONTEST")
    except P.UnilateralCloseError:
        pass
    if planted.status != P.CONTEST or not planted.open:
        return fail("CONTEST mutated after unilateral close attempts")
    if planted.first.label != first_label or planted.second.label != second_label:
        return fail("a side's verdict was overwritten")

    agree = P.reconcile(
        P.Verdict(vendor="anthropic", label="LENS-OUTPUT-ABSENT"),
        P.Verdict(vendor="openai", label="LENS-OUTPUT-ABSENT"),
    )
    if agree.status != P.AGREE or agree.raw_anchor is not None:
        return fail(f"identical labels did not AGREE: {agree.to_dict()}")
    try:
        P.reconcile(
            P.Verdict(vendor="anthropic", label="SUCCESS"),
            P.Verdict(vendor="openai", label="FAILED"),
            raw_anchor=None,
        )
        return fail("CONTEST without raw anchor was accepted")
    except P.ContestAnchorError:
        pass

    dispatch_dir = HERE / "dispatches"
    live_prompt = write_prompt(
        dispatch_dir / "probe2-live.prompt.txt",
        "SYN-0014",
        "command-center/receipts/SYN-0014.json",
        "anthropic",
        "openai",
    )
    live = run_confirmer(
        "openai",
        live_prompt,
        dispatch_dir / "probe2-live.json",
        mode="complete",
        lens_id="SYN-0014",
    )
    severed = P.run_severed_control(dispatch_dir)
    if live.get("terminal_state") != "SUCCESS" or not live.get("counts_as_result"):
        return fail(f"live dispatch not SUCCESS: {live}")
    if severed.get("classification") != "severed-stream":
        return fail(f"severed classification={severed.get('classification')}")
    if severed.get("counts_as_result"):
        return fail("severed counted as a result")
    if terminal_state(severed) != "FAILED" or severed.get("terminal_state") != "FAILED":
        return fail(f"severed terminal={severed.get('terminal_state')} (want FAILED)")
    if live.get("exit_code") == 0 and severed.get("exit_code") == 0:
        if live.get("counts_as_result") == severed.get("counts_as_result"):
            return fail("exit-0-only detector is inert")

    control = payload.get("dispatch_control") or {}
    if control.get("terminal_state") != "FAILED" or control.get("counts_as_result"):
        return fail(f"artifact dispatch_control {control}")
    if control.get("classification") != "severed-stream":
        return fail(f"artifact control classification {control.get('classification')}")

    payload = {
        "probe": "probe2-unilateral-and-severed",
        "unit_id": P.UNIT_ID,
        "planted_contest": planted.to_dict(),
        "live_terminal": live.get("terminal_state"),
        "severed_terminal": severed.get("terminal_state"),
        "severed_classification": severed.get("classification"),
        "severed_counts": severed.get("counts_as_result"),
        "agree_control": agree.status,
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        "SUCCESS:SYN-0026-probe2 no contested finding closed by one side; "
        "severed classifies FAILED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
