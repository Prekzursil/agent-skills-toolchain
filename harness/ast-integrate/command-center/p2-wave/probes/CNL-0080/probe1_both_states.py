#!/usr/bin/env python3
"""Probe 1: both-states FIRE/SILENT + A10 parse-unchanged.

A detector silent in both states measures nothing. The expression must FIRE on
a true fixture and stay SILENT on a false fixture. Parse of the spec string
must accept it unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import CNL_0080_EXPR, SPEC_SIX, parse_unchanged  # noqa: E402
from engine import evaluate_fixture  # noqa: E402
from fixtures_lib import by_id  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0080-executable-stopping-example-unanimity-true-or-max-rounds-1.schema.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0080-probe1 {msg}")
    return 1


def main() -> int:
    parsed = parse_unchanged(CNL_0080_EXPR)
    print(
        "parse_unchanged accepted="
        f"{parsed.accepted} source_verbatim={parsed.source_verbatim!r}"
    )
    if parsed.source_verbatim != CNL_0080_EXPR:
        return fail("parser rewrote the spec expression")
    for expr in SPEC_SIX:
        p = parse_unchanged(expr)
        if p.source_verbatim != expr or not p.accepted:
            return fail(f"A10 rejected required example {expr!r}")
        print(f"A10 accepted unchanged: {expr}")

    fire_u = evaluate_fixture(by_id("fire-unanimity"))
    fire_t = evaluate_fixture(by_id("fire-timer"))
    silent = evaluate_fixture(by_id("silent-contested"))
    silent11 = evaluate_fixture(by_id("silent-round-11"))

    print("VERBATIM fire-unanimity " + json.dumps(fire_u, sort_keys=True, default=str))
    print("VERBATIM fire-timer " + json.dumps(fire_t, sort_keys=True, default=str))
    print("VERBATIM silent-contested " + json.dumps(silent, sort_keys=True, default=str))
    print("VERBATIM silent-round-11 " + json.dumps(silent11, sort_keys=True, default=str))

    if fire_u.get("expression_true") is not True:
        return fail("fire-unanimity did not FIRE")
    if fire_t.get("expression_true") is not True:
        return fail("fire-timer did not FIRE")
    if silent.get("expression_true") is not False:
        return fail("silent-contested did not stay SILENT")
    if silent11.get("expression_true") is not False:
        return fail("silent-round-11 did not stay SILENT")
    if fire_u["outcome_kind"] != "AGREEMENT" or fire_u["unanimity"] is not True:
        return fail("fire-unanimity outcome not AGREEMENT/unanimity=true")
    if fire_t["outcome_kind"] != "TIMER_EXHAUSTION" or fire_t["unanimity"] is not False:
        return fail("fire-timer outcome not TIMER_EXHAUSTION/unanimity=false")
    if fire_t["stop_reason"] != "MAX_ROUNDS":
        return fail("timer stop_reason is not MAX_ROUNDS")
    if fire_u["stop_reason"] != "UNANIMITY":
        return fail("unanimity stop_reason is not UNANIMITY")
    if fire_u["consumer_key"] == fire_t["consumer_key"]:
        return fail("timer and unanimity share a consumer_key — not distinguishable")
    if fire_t["instant_unanimity_trigger"] is not False:
        return fail("timer exhaustion tripped instant-unanimity trigger")

    fired = 2
    silent_n = 2
    print(f"both_states FIRE={fired} SILENT={silent_n} detector_vacuous={fired == 0 and silent_n == 0}")
    if fired == 0 or silent_n == 0:
        return fail("detector silent in one or both states")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNL-0080" not in text:
        return fail("sentinel-absent in artifact")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    expr = (
        (doc.get("expression") or {}).get("verbatim")
        if isinstance(doc.get("expression"), dict)
        else None
    )
    if expr != CNL_0080_EXPR:
        return fail("artifact expression not verbatim spec string")

    print("SUCCESS:CNL-0080-probe1 both-states FIRE/SILENT parse-unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
