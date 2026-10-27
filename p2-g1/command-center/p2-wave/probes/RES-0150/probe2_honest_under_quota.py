#!/usr/bin/env python3
"""Probe 2: negative control — no real counterevidence → UNDER-QUOTA-HONEST, not filled."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cases as K  # noqa: E402
import contract as C  # noqa: E402
import engine as E  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0150-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    if C.HONEST_VERDICT not in text:
        return fail("honest verdict token absent from artifact")

    live_n = E.evaluate_quota(K.run_no_counter(), REPO)
    live_g = E.evaluate_quota(K.run_has_counter(), REPO)
    mutant = E.mutant_count_all_disconfirming(K.run_no_counter())
    print(
        f"N verdict={live_n['verdict']} u={live_n['qualifying_unfavorable']} "
        f"rejected={live_n['padded_rejected']} filled={live_n['filled_with_padding']}"
    )
    print(
        f"G verdict={live_g['verdict']} u={live_g['qualifying_unfavorable']} "
        f"required={live_g['required_n']}"
    )
    print(
        f"mutant verdict={mutant['verdict']} u={mutant['qualifying_unfavorable']} "
        f"would_fill={mutant['filled_with_padding']}"
    )

    if live_n["verdict"] != C.HONEST_VERDICT:
        return fail(f"N verdict {live_n['verdict']} != {C.HONEST_VERDICT}")
    if live_n["qualifying_unfavorable"] != 0:
        return fail("N counted unfavorable items that do not exist")
    if live_n.get("filled_with_padding") is True:
        return fail("engine filled the quota — the failure this unit exists to prevent")
    if live_n["padded_rejected"] < 1:
        return fail("N run did not reject planted fillers")
    if live_g["verdict"] != C.QUOTA_MET:
        return fail("quota engine is silent in the genuine-counterevidence state")
    if mutant["verdict"] != C.QUOTA_MET:
        return fail("mutant did not fill; cannot show both-states vs a filling counter")
    if mutant["verdict"] == live_n["verdict"]:
        return fail("engine indistinguishable from the filling mutant")

    neg = doc.get("negative_control") or {}
    if neg.get("verdict") != C.HONEST_VERDICT:
        return fail("artifact negative_control.verdict mismatch")
    if neg.get("filled") is True:
        return fail("artifact recorded filled=true")
    if neg.get("qualifying_unfavorable") != 0:
        return fail("artifact N qualifying_unfavorable is not 0")
    pos = doc.get("positive_control") or {}
    if pos.get("verdict") != C.QUOTA_MET:
        return fail("artifact positive_control is not QUOTA-MET")

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("reviewer record missing")
    print("reviewer_id=" + str(rev.get("reviewer_id")))
    print(
        "SUCCESS:RES-0150-probe2 UNDER-QUOTA-HONEST on no-counterevidence; "
        "filling mutant discriminated; genuine quota-met"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
