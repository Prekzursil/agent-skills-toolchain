#!/usr/bin/env python3
"""Probe 2: both-states + jsonschema (mechanically different from probe 1).

Signal 2 loads charter_block.schema.json and Draft202012Validator.
Does not use compiler.py AXIS_MAPS to decide fixture validity.
Also runs the independent reviewer recount and the negative control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compiler as C  # noqa: E402
import reviewer as R  # noqa: E402

RAW = HERE / "probe2-both-states.raw.json"
SCHEMA = HERE / "charter_block.schema.json"
GOOD = HERE / "fixtures" / "known-good.json"
BAD_RISK = HERE / "fixtures" / "planted-bad-prose-enum.json"
BAD_OUT = HERE / "fixtures" / "planted-bad-unknown-output.json"
ART = (
    HERE.parents[3]
    / "command-center/design/council/"
    / "CNL-0003-charter-block-the-typed-fields-a-compiler-actually-branche.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0003-probe2 {msg}")
    return 1


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{list(e.path)}: {e.message}" if e.path else e.message
        for e in validator.iter_errors(doc)
    ]


def main() -> int:
    good = json.loads(GOOD.read_text(encoding="utf-8"))
    bad_risk = json.loads(BAD_RISK.read_text(encoding="utf-8"))
    bad_out = json.loads(BAD_OUT.read_text(encoding="utf-8"))

    good_errs = schema_errors(good)
    bad_risk_errs = schema_errors(bad_risk)
    bad_out_errs = schema_errors(bad_out)
    if good_errs:
        return fail(f"schema SILENT failed on known-good: {good_errs[:3]}")
    if not bad_risk_errs:
        return fail("schema did not FIRE on planted-bad risk_tier prose")
    if not bad_out_errs:
        return fail("schema did not FIRE on planted-bad desired_output prose")

    good_comp = C.select(good)
    bad_comp = C.select(bad_risk)
    if not good_comp.ok:
        return fail(f"compiler not SILENT on known-good: {good_comp.reason}")
    if not bad_comp.fired() or bad_comp.protocol_id is not None:
        return fail("compiler did not FIRE on planted-bad")

    # Losing option is silent in BOTH states — the defect the check exists to catch.
    lose_good = C.losing_select(good)
    lose_bad = C.losing_select(bad_risk)
    if not lose_good.ok or not lose_bad.ok:
        return fail("losing option did not silent-default")
    if lose_bad.protocol_id is None:
        return fail("losing option rejected planted-bad (would make detector vacuous)")

    recount = R.recount()
    want = (
        len(C.RISK_FAMILY) * len(C.OUTPUT_FAMILY) * len(C.INTENT_FAMILY)
    )
    if recount["cartesian"] != want:
        return fail(
            f"reviewer cartesian={recount['cartesian']} compiler={want}"
        )
    cex = recount["counterexample"]
    cex_live = C.select(cex)
    cex_lose = C.losing_select(cex)
    if not cex_live.fired():
        return fail("reviewer counterexample was accepted by live compiler")
    if not cex_lose.ok:
        return fail("reviewer counterexample was not accepted by losing option")

    # Negative control: the state the check is meant to reject, verbatim.
    negative = C.select(C.good_charter(risk_tier="urgent-ish"))
    verbatim = (
        f"ok={negative.ok} protocol_id={negative.protocol_id!r} "
        f"reason={negative.reason}"
    )
    if negative.ok or negative.protocol_id is not None:
        return fail(f"negative control did not reject: {verbatim}")
    if "unknown_enum:risk_tier:urgent-ish" not in negative.reason:
        return fail(f"negative control reason unexpected: {verbatim}")

    if ART.is_file():
        art = json.loads(ART.read_text(encoding="utf-8"))
        if art.get("unit_id") != "CNL-0003":
            return fail("artifact unit_id")
        if "SUCCESS:CNL-0003" not in json.dumps(art):
            return fail("artifact sentinel")
        if str(art.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {art.get('state')}")

    RAW.write_text(
        json.dumps(
            {
                "known_good_schema_errors": good_errs,
                "planted_bad_schema_errors": bad_risk_errs,
                "planted_bad_output_schema_errors": bad_out_errs,
                "known_good_compiler_ok": good_comp.ok,
                "planted_bad_compiler_reason": bad_comp.reason,
                "losing_accepts_planted_bad": lose_bad.ok,
                "reviewer": recount,
                "negative_control_verbatim": verbatim,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        "both-states schema good_errs="
        + str(len(good_errs))
        + " bad_risk_errs="
        + str(len(bad_risk_errs))
        + " compiler_good_ok="
        + str(good_comp.ok)
        + " compiler_bad_reason="
        + bad_comp.reason
        + " reviewer_cartesian="
        + str(recount["cartesian"])
        + " negative="
        + verbatim
    )
    print("SUCCESS:CNL-0003-probe2 both-states + jsonschema + reviewer counterexample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
