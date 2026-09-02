#!/usr/bin/env python3
"""Probe 1: instantiate the preset, schema both-states, proper-score and never-resolve controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import instantiate as I  # noqa: E402
import scoring as S  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0112-forecasting-and-expert-elicitation-preset-with-a-proper-sc.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0112-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0112" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    task = I.load_json(I.TASK)
    live = I.instantiate(I.CNL_0112_PRESET, task)
    if not live["ok"]:
        return fail("live instantiate rejected")
    rec = doc.get("instantiation") or {}
    if rec.get("roster_ids") != live["roster_ids"]:
        return fail(f"roster mismatch live={live['roster_ids']} rec={rec.get('roster_ids')}")
    if rec.get("protocol_schedule") != live["protocol_schedule"]:
        return fail("protocol_schedule mismatch")
    if (rec.get("voting") or {}).get("method") != live["voting"]["method"]:
        return fail("voting mismatch")
    if (rec.get("stopping") or {}).get("expression") != live["stopping"]["expression"]:
        return fail("stopping mismatch")
    if live["accepted_ids"] != ["F1", "F2"] or live["rejected_ids"] != ["F3"]:
        return fail(f"classification live accepted={live['accepted_ids']} rejected={live['rejected_ids']}")
    if rec.get("accepted_ids") != live["accepted_ids"] or rec.get("rejected_ids") != live["rejected_ids"]:
        return fail("recorded classification mismatch")

    answers = doc.get("answers") or {}
    if answers.get("scoring_rule") != "logarithmic":
        return fail("scoring_rule is not logarithmic")
    if "UNSCOREABLE" not in str(answers.get("never_resolves") or ""):
        return fail("never_resolves does not name UNSCOREABLE")
    if "REJECT" not in str(answers.get("never_resolves") or ""):
        return fail("never_resolves does not REJECT at emission")

    n_good = I.error_count(doc)
    mutant = {k: v for k, v in doc.items() if k != "preset"}
    n_bad = I.error_count(mutant)
    print(f"schema good_errors={n_good} invalid_errors={n_bad}")
    if n_good != 0:
        return fail(f"schema errors on artifact:{n_good}")
    if n_bad < 1:
        return fail("schema vacuous: mutant without preset accepted")

    proper = S.properness_report()
    print(
        "proper "
        f"log_cal_beats_hedge={proper['log']['prefers_calibrated_to_hedge']} "
        f"log_cal_beats_ext={proper['log']['prefers_calibrated_to_extremist']} "
        f"linear_ext_beats_cal={proper['linear_improper']['prefers_extremist_to_calibrated']}"
    )
    if not proper["log_is_strictly_proper_on_this_fixture"]:
        return fail("log score did not prefer calibrated report")
    if not proper["linear_is_improper_on_this_fixture"]:
        return fail("linear score control did not prefer extremist")

    if live["herding_control_same_evidence_median_collapse"] is not True:
        return fail("herding control silent on median collapse with same evidence")

    print(
        "instantiate "
        f"roster={live['roster_ids']} "
        f"schedule={live['protocol_schedule']} "
        f"vote={live['voting']['method']} "
        f"stop_max={live['stopping']['max_rounds']}"
    )
    print("negative_control NC-unresolvable-emission FIRES on F3 (preference, no source, no date) -> REJECT:UNSCOREABLE; SILENT on F1/F2")
    print("SUCCESS:CNL-0112-probe1 instantiate schema proper-score never-resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
