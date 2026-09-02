#!/usr/bin/env python3
"""Probe 1: latency + injected-token curve with dispersion, plus router-disabled null."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    live = C.live_platform_records()
    cost = E.cost_curve(live)
    points = cost["points"]
    if [p["catalogue_size"] for p in points] != list(C.SIZES):
        return fail(f"sizes { [p['catalogue_size'] for p in points] } != {list(C.SIZES)}")
    if cost["trials"] != C.N_TRIALS:
        return fail(f"trials {cost['trials']}")
    if not cost["dispersion_reported"]:
        return fail("dispersion not reported")

    for point in points:
        disabled = point["disabled"]
        budgeted = point["budgeted"]
        naive = point["naive"]
        for arm in (disabled, budgeted, naive):
            lat = arm["latency_ms"]
            for key in ("p10", "p50", "p90", "mean", "stdev", "n"):
                if key not in lat:
                    return fail(f"missing {arm['arm']} latency {key} at n={point['catalogue_size']}")
            if lat["n"] != float(C.N_TRIALS):
                return fail(f"{arm['arm']} n_trials {lat['n']}")
            if lat["p90"] + 1e-9 < lat["p50"]:
                return fail(f"{arm['arm']} p90 < p50")
        if disabled["measured_tokens"] != 0:
            return fail(f"disabled tokens {disabled['measured_tokens']} at n={point['catalogue_size']}")
        if disabled["flood_red"]:
            return fail("disabled arm reported flood")
        if budgeted["flood_red"]:
            return fail(
                f"budgeted crossed ceiling at n={point['catalogue_size']} "
                f"tokens={budgeted['measured_tokens']}"
            )
        if budgeted["tokenizer_count"] != budgeted["measured_tokens"]:
            return fail("budgeted tokenizer_count drifted from measured_tokens")
        if (
            budgeted["measured_tokens"]
            and budgeted["measured_tokens"] == budgeted["char_quarter_estimate"]
        ):
            return fail("budgeted count equals len//4 estimate")

    if cost["bounded_crossed_ceiling"]:
        return fail("bounded injection crossed HARD_CEILING_TOKENS")
    if cost["first_naive_flood_size"] is None:
        return fail("naive arm never flooded; overflow precedent not reproduced on the curve")
    # Null control separates router cost from catalogue-loading: disabled tokens
    # stay 0 at every size while budgeted tokens are positive once hot items exist.
    if not any(p["budgeted"]["measured_tokens"] > 0 for p in points):
        return fail("budgeted never injected tokens")
    if not any(p["added_latency_p50_ms"] > 0 for p in points):
        return fail("budgeted p50 was never above disabled p50")

    out = REPO / C.OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact missing")
    text = out.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in text:
        return fail("catalog sentinel absent")
    art_cost = ((doc.get("measurements") or {}).get("cost")) or {}
    if art_cost.get("budgeted_token_curve") != cost["budgeted_token_curve"]:
        return fail(
            f"artifact token curve drifted live={cost['budgeted_token_curve']} "
            f"art={art_cost.get('budgeted_token_curve')}"
        )
    if art_cost.get("naive_token_curve") != cost["naive_token_curve"]:
        return fail("artifact naive token curve drifted")
    if art_cost.get("first_naive_flood_size") != cost["first_naive_flood_size"]:
        return fail("artifact first_naive_flood_size drifted")

    report = {
        "pass": True,
        "probe": "probe1-cost-curve",
        "unit_id": C.UNIT_ID,
        "sizes": list(C.SIZES),
        "trials": C.N_TRIALS,
        "live_n": len(live),
        "budgeted_token_curve": cost["budgeted_token_curve"],
        "naive_token_curve": cost["naive_token_curve"],
        "first_naive_flood_size": cost["first_naive_flood_size"],
        "bounded_crossed_ceiling": cost["bounded_crossed_ceiling"],
        "added_latency_p50_ms": [p["added_latency_p50_ms"] for p in points],
        "null_disabled_tokens": [p["disabled"]["measured_tokens"] for p in points],
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"SUCCESS:{C.UNIT_ID}-probe1 cost curve sizes={list(C.SIZES)} "
        f"budgeted_tokens={cost['budgeted_token_curve']} "
        f"naive_flood_at={cost['first_naive_flood_size']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
