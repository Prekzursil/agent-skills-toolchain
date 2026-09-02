#!/usr/bin/env python3
"""Probe 2: independent both-states re-run, throttle quality, overclaim, anchors."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checks as C  # noqa: E402
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0088-participant-dominance-and-airtime-concentration.md"
)


def resolve_anchor(path: str, line: int, snippet: str) -> tuple[bool, str]:
    full = REPO / path
    if not full.is_file():
        return False, f"missing {path}"
    lines = full.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"{path}:{line} out of range"
    if snippet not in lines[line - 1]:
        return False, f"{path}:{line} snippet mismatch"
    return True, f"{path}:{line}"


def main() -> int:
    bundle = C.both_states()
    errors = C.assert_both_states(bundle)
    print("reviewer_reran_both_states=True")
    print(f"reviewer_planted_fired={bundle['planted_airtime']['fired']}")
    print(f"reviewer_good_silent={bundle['known_good']['silent']}")

    planted = F.planted_bad_airtime()
    claims = F.planted_bad_claims_only()
    good = F.known_good_balanced()
    ind_p = C.independent_max_shares(planted)
    ind_c = C.independent_max_shares(claims)
    ind_g = C.independent_max_shares(good)
    print(
        f"independent_planted max_token={ind_p['max_token_share']} "
        f"max_claim={ind_p['max_surviving_claim_share']}"
    )
    print(
        f"independent_claims max_token={ind_c['max_token_share']} "
        f"max_claim={ind_c['max_surviving_claim_share']}"
    )
    print(
        f"independent_good max_token={ind_g['max_token_share']} "
        f"max_claim={ind_g['max_surviving_claim_share']}"
    )
    tau = D.TAU
    if (ind_p["max_token_share"] or 0) < tau and (
        ind_p["max_surviving_claim_share"] or 0
    ) < tau:
        errors.append("independent shares do not show planted airtime dominance")
    if (ind_c["max_token_share"] or 1) >= tau:
        errors.append("independent claims-only is not even on tokens")
    if (ind_c["max_surviving_claim_share"] or 0) < tau:
        errors.append("independent claims-only missing claim dominance")
    if (ind_g["max_token_share"] or 1) >= tau or (
        ind_g["max_surviving_claim_share"] or 1
    ) >= tau:
        errors.append("independent shares show dominance on known-good")

    tq = C.throttle_quality()
    print(f"wrong_dominant_before={tq['wrong_dominant']['before']}")
    print(f"wrong_dominant_after={tq['wrong_dominant']['after']}")
    print(f"wrong_dominant_improved={tq['wrong_dominant']['improved']}")
    print(f"expert_dominant_before={tq['expert_dominant']['before']}")
    print(f"expert_dominant_after={tq['expert_dominant']['after']}")
    print(f"expert_dominant_degraded={tq['expert_dominant']['degraded']}")
    if not tq["wrong_dominant"]["improved"]:
        errors.append("throttling a wrong-dominant seat did not improve quality")
    if not tq["expert_dominant"]["degraded"]:
        errors.append("throttling a sole-correct expert did not degrade quality")

    tok_rows = C.token_sweep()
    cl_rows = C.claim_sweep()
    first_tok = C.first_fire(tok_rows, "max_token_share")
    first_cl = C.first_fire(cl_rows, "max_surviving_claim_share")
    print(f"first_fire_token={first_tok}")
    print(f"first_fire_claim={first_cl}")
    if not first_tok or (first_tok.get("max_token_share") or 0) < tau:
        errors.append("token sweep did not first-fire at tau")
    silent_below = [r for r in tok_rows if (r["max_token_share"] or 0) < tau]
    if any(r["fired"] for r in silent_below):
        errors.append("token sweep fired below tau")

    if not ART.is_file():
        errors.append("artifact missing")
        for e in errors:
            print(f"FAILED:CNL-0088-probe2 {e}")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    lowered = text.lower()
    if "always improve" in lowered or "always improves" in lowered:
        errors.append("artifact overclaims that throttling always improves quality")
    if doc.get("quality_monotonic") is True:
        errors.append("artifact claims quality_monotonic true")
    qdoc = doc.get("throttle_experiment") or {}
    if qdoc.get("quality_monotonic") is True:
        errors.append("throttle_experiment.quality_monotonic is true")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        errors.append("reviewer.independent is not true")
    if rev.get("executed_both_states_control") is not True:
        errors.append("reviewer did not execute both-states control")
    if "SUCCESS:CNL-0088" not in text:
        errors.append("sentinel absent")
    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        errors.append("artifact evidence < 2")
    for i, row in enumerate(evidence):
        ok, why = resolve_anchor(
            str(row.get("path") or ""),
            int(row.get("line") or 0),
            str(row.get("snippet") or ""),
        )
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            errors.append(f"unresolved evidence {why}")
    if errors:
        for e in errors:
            print(f"FAILED:CNL-0088-probe2 {e}")
        return 1
    print("SUCCESS:CNL-0088-probe2 independent-both-states throttle-quality overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
