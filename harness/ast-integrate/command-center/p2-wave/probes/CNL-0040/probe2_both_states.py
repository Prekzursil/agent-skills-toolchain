#!/usr/bin/env python3
"""Probe 2: both-states control, negative control, independent recount."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import reviewer as V  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0040-executable-runtime-semantics-for-the-6-judicial-protocols.md"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0040-probe2 {msg}")
    return 1


def main() -> int:
    m = C.measure()
    g = m["gatekeeper_both_states"]
    n = m["family_count_both_states"]
    neg = m["negative_control"]
    extra = m["extra_planted"]
    print(f"gatekeeper silent_on_good={g['silent_on_good']} fires_on_bad={g['fires_on_bad']}")
    print(f"gatekeeper bad_codes={g['bad_codes']}")
    print(f"family_count silent_on_good={n['silent_on_good']} fires_on_bad={n['fires_on_bad']} good_n={n['good_n']} bad_n={n['bad_n']}")
    print(f"negative_control fires={neg['fires']} codes={neg['codes']}")
    print(f"negative_control_verbatim {neg['verbatim']}")
    print(f"extra_planted all_fired={extra['all_fired']}")
    if not g["silent_on_good"]:
        return fail("good-not-silent")
    if not g["fires_on_bad"]:
        return fail("bad-not-fired")
    if "GATEKEEPER_IS_DECIDER" not in g["bad_codes"]:
        return fail("missing-gatekeeper-code")
    if not n["silent_on_good"] or not n["fires_on_bad"]:
        return fail("family-count-both-states")
    if not neg["fires"]:
        return fail("negative-control-silent")
    if not extra["all_fired"]:
        return fail("extra-planted")
    if not m["ok"]:
        return fail("measure-not-ok")

    if not ART.is_file():
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    recorded = doc.get("both_states") or {}
    if recorded.get("fires_on_bad") is not True or recorded.get("silent_on_good") is not True:
        return fail("artifact-both-states-not-recorded")
    rec_neg = doc.get("negative_control") or {}
    if rec_neg.get("verbatim") != neg["verbatim"]:
        return fail("artifact-negative-verbatim-drift")
    if "GATEKEEPER_IS_DECIDER" not in str(rec_neg.get("statement") or ""):
        return fail("artifact-negative-statement")

    tab = V.retabulate(doc)
    print(f"independent_recount verdict={tab['verdict']} disagreement={tab['disagreement']}")
    print(f"independent_recount numbers={json.dumps(tab['numbers'], sort_keys=True)}")
    if tab["disagreement"] or tab["verdict"] != "PASS":
        return fail("independent-recount-block")
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("artifact-reviewer")

    print("SUCCESS:CNL-0040-probe2 both-states negative-control independent-recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
