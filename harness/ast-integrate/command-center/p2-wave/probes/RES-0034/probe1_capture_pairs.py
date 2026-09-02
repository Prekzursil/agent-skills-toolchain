#!/usr/bin/env python3
"""Probe 1: re-run all four tasks on both rails; require 3 leaks + 1 control.

Also requires loud degradation on leaks and PORTABLE on the control, and
checks the research artifact records those captured pairs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/research/RES-0034.json"
SENTINEL = (
    "SUCCESS:RES-0034 in the receipt AND at least 3 captured divergent "
    "output pairs plus one captured agreeing pair as the control"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0034-probe1 {msg}")
    return 1


def main() -> int:
    pairs = I.capture_all()
    try:
        leaks, controls = I.assert_inventory(pairs)
    except I.OverclaimError as exc:
        return fail(str(exc))
    print(f"live_leaks={len(leaks)} live_controls={len(controls)}")
    if len(leaks) < 3:
        return fail("fewer than 3 divergent pairs")
    if len(controls) < 1:
        return fail("missing agreeing control")
    for leak in leaks:
        print(
            f"leak[{leak['id']}] divergent={leak['divergent']} "
            f"loud={leak['loud_degradation']['verdict']} "
            f"claude={leak['claude_answer']} codex={leak['codex_answer']}"
        )
        if leak["loud_degradation"]["verdict"] != "DEGRADED":
            return fail(f"{leak['id']} not DEGRADED")
        if I.canonical(leak["claude_answer"]) == I.canonical(leak["codex_answer"]):
            return fail(f"{leak['id']} answers agree")
    control = controls[0]
    print(
        f"control[{control['id']}] divergent={control['divergent']} "
        f"loud={control['loud_degradation']['verdict']} "
        f"answer={control['claude_answer']}"
    )
    if control["divergent"] or control["loud_degradation"]["verdict"] != "PORTABLE":
        return fail("control is not an agreeing PORTABLE pair")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text or "SUCCESS:RES-0034" not in text:
        return fail("sentinel absent")
    body = S.payload(doc)
    recorded = body.get("captured_divergent_pairs") or []
    if len(recorded) < 3:
        return fail("artifact has fewer than 3 captured divergent pairs")
    rec_control = body.get("captured_agreeing_pair") or {}
    if not rec_control:
        return fail("artifact missing agreeing control pair")
    live_ids = {p["id"] for p in leaks}
    rec_ids = {p.get("id") for p in recorded}
    if not live_ids <= rec_ids:
        return fail(f"artifact leak ids {rec_ids} miss live {live_ids}")
    print("SUCCESS:RES-0034-probe1 live capture 3 divergent + 1 agreeing control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
