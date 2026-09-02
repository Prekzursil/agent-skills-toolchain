#!/usr/bin/env python3
"""Named probe 2: both-states control on the settlement engine.

A probe silent in both the broken and healthy states measures nothing.
Silence-as-pass and resolve-by-default must not match the honest histogram.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import settle as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0070-unknown-needs-probe-settlement.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0070-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0070":
        return fail(f"unit_id {doc.get('unit_id')}")

    eng = S.settle_engine(REPO)
    if not eng["pass"]:
        print(json.dumps({k: v for k, v in eng.items() if k not in {"rows", "kind_both_states"}}, sort_keys=True, default=str)[:4000])
        return fail("engine pass=false")
    if not eng["fired_on_bad_state"]:
        return fail("did not fire on known-broken kinds")
    if not eng["silent_on_good_state"]:
        return fail("known-good smoke was not ADOPT-AS-IS")
    if not eng["silence_not_treated_as_pass"]:
        return fail("silence-trap was treated as a pass")
    if not eng["unconstructable_not_resolved_by_default"]:
        return fail("unconstructable resolved by default")
    if eng["mutant_silence_as_adopt_count"] == eng["honest_adopt_count"]:
        return fail("silence-as-adopt mutant equals honest adopt count")
    if eng["n"] != S.CATALOG_CLAIMED_N:
        return fail(f"engine n={eng['n']} want {S.CATALOG_CLAIMED_N}")

    ctrl = doc.get("engine_controls") or {}
    if ctrl.get("honest_adopt_count") != eng["honest_adopt_count"]:
        return fail("artifact honest_adopt_count drifted")
    if ctrl.get("mutant_silence_as_adopt_count") != eng["mutant_silence_as_adopt_count"]:
        return fail("artifact mutant count drifted")
    if ctrl.get("silence_not_treated_as_pass") is not True:
        return fail("artifact silence_not_treated_as_pass")
    if ctrl.get("unconstructable_not_resolved_by_default") is not True:
        return fail("artifact unconstructable defaulted")

    silence_both = (eng.get("kind_both_states") or {}).get("silence-trap") or {}
    if silence_both.get("silent_in_both_states") is not True:
        return fail("silence-trap both-states did not record silence")
    if silence_both.get("discriminates") is True:
        return fail("silence-trap unexpectedly discriminates")

    for kind, n in S.KIND_COUNTS:
        if kind == "silence-trap":
            continue
        rec = (eng.get("kind_both_states") or {}).get(kind) or {}
        if rec.get("discriminates") is not True:
            return fail(f"kind {kind} both-states does not discriminate")

    loc = eng.get("locator_both_states") or {}
    if loc.get("discriminates") is not True:
        return fail("locator both-states does not discriminate")
    if loc.get("empty_candidates_not_treated_as_settled") is not True:
        return fail("empty registry treated as settled")

    for row in doc.get("candidates") or []:
        both = row.get("both_states") or {}
        if "known_good" not in both or "known_broken" not in both:
            return fail(f"row {row.get('id') or row.get('slot')} both_states incomplete")

    payload = {
        "probe": "probe2-both-states",
        "unit_id": "WFA-0070",
        "pass": True,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "silence_not_treated_as_pass": True,
        "unconstructable_not_resolved_by_default": True,
        "honest_adopt_count": eng["honest_adopt_count"],
        "mutant_silence_as_adopt_count": eng["mutant_silence_as_adopt_count"],
        "counts_by_disposition": eng["counts_by_disposition"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"fired_bad={eng['fired_on_bad_state']} good_adopt={eng['silent_on_good_state']} "
        f"silence_unknown={eng['silence_not_treated_as_pass']} "
        f"honest_adopt={eng['honest_adopt_count']} "
        f"mutant_adopt={eng['mutant_silence_as_adopt_count']}"
    )
    print("SUCCESS:WFA-0070-probe2 both-states detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
