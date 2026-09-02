#!/usr/bin/env python3
"""Probe 2: both-states — suite PASS on conforming adapter, FAIL on mutant."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import conforming as C  # noqa: E402
import mutant as M  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0045.json"
REQUIRED_RULES = ("prompt-by-file", "blocking-dispatch", "and-gate")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0045-probe2 {msg}")
    return 1


def rule_has_failure(result: dict, rule: str) -> bool:
    return any(
        (not c.get("pass")) and c.get("rule") == rule for c in result.get("cases") or []
    )


def main() -> int:
    scratch = HERE / "scratch" / "probe2"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)

    good = S.run_suite(C.dispatch, scratch / "good")
    bad = S.run_suite(M.dispatch, scratch / "bad")
    print(
        json.dumps(
            {
                "conforming_pass": good["pass"],
                "conforming_n_pass": good["n_pass"],
                "conforming_n_fail": good["n_fail"],
                "conforming_failed_ids": good["failed_ids"],
                "mutant_pass": bad["pass"],
                "mutant_n_pass": bad["n_pass"],
                "mutant_n_fail": bad["n_fail"],
                "mutant_failed_ids": bad["failed_ids"],
                "negative_per_rule": good["negative_per_rule"],
            },
            sort_keys=True,
        )
    )
    if not good["pass"]:
        return fail("conforming-suite-failed:" + ",".join(good["failed_ids"]))
    if good["n_cases"] < 6:
        return fail(f"too-few-cases:{good['n_cases']}")
    if not all(good["negative_per_rule"].get(r) for r in REQUIRED_RULES):
        return fail(f"missing-negative:{good['negative_per_rule']}")
    if bad["pass"]:
        return fail("mutant-suite-vacuous-pass")
    for rule in REQUIRED_RULES:
        if not rule_has_failure(bad, rule):
            return fail(f"mutant-not-detected-on-rule:{rule}")
        print(f"mutant_detected rule={rule}")

    if not ART.is_file():
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0045" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    both = doc.get("both_states") or {}
    if both.get("conforming_pass") is not True or both.get("mutant_pass") is not False:
        return fail("artifact-both-states-mismatch")

    print("SUCCESS:TST-0045-probe2 both-states conforming-green mutant-red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
