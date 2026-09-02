#!/usr/bin/env python3
"""Probe 2: independent both-states re-run, recruitment trigger, overclaim mutants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402

RAW = HERE / "probe2-recruitment.raw.json"
ART = (
    HERE.parents[3]
    / "command-center/design/council/CNL-0092-missing-expertise-detection-and-the-recruitment-trigger.md"
)


def main() -> int:
    both = E.both_states()
    rec = E.recruitment_cases()
    RAW.write_text(
        json.dumps({"both_states": both, "recruitment": rec}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"reviewer_both_states_pass={both.get('pass')} "
        f"planted_bad_fired={both.get('planted_bad_fired')} "
        f"known_good_silent={both.get('known_good_silent')}"
    )
    print(
        f"recruit_ok={rec.get('pass')} "
        f"qualified={rec['qualified']} "
        f"cosmetic={rec['cosmetic']} "
        f"empty_pool={rec['empty_pool']} "
        f"mutants={rec['mutants']}"
    )
    if not both.get("pass"):
        print("FAILED:CNL-0092-probe2 reviewer both-states")
        return 1
    if not rec.get("pass"):
        print("FAILED:CNL-0092-probe2 recruitment")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        trig = doc.get("recruitment_trigger") or {}
        if trig.get("confident_answer_while_uncovered") is True:
            print("FAILED:CNL-0092-probe2 artifact allows confident answer while uncovered")
            return 1
        if trig.get("cosmetic_recruitment_closes_gap") is True:
            print("FAILED:CNL-0092-probe2 artifact treats cosmetic recruitment as closure")
            return 1
        if "SUCCESS:CNL-0092" not in ART.read_text(encoding="utf-8"):
            print("FAILED:CNL-0092-probe2 sentinel absent")
            return 1
    print("SUCCESS:CNL-0092-probe2 recruitment reviewer-mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
