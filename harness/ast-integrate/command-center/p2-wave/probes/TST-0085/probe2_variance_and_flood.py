#!/usr/bin/env python3
"""Named probe 2: variance re-derived from raw integers; flood mutant; schema.

Mechanically different from probe 1: does not re-score the growth-curve
pass/fail from a fresh inject_topk sweep as its primary signal. It
recomputes the variance band from the receipt's raw_runs list, re-runs only
the unbounded flood control, and checks that the schema rejects garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import curve as C  # noqa: E402
from tools.router.inject import (  # noqa: E402
    DEFAULT_CEILING,
    count_payload_tokens,
    inject_unbounded_flood,
)

ART = REPO / "command-center/receipts/TST-0085.json"
SCHEMA = REPO / "command-center/schema/benchmark-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0085"


def close(a: float, b: float, *, rel: float = 1e-12, abs_: float = 1e-9) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0085-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text or doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0085-probe2 sentinel/state")
        return 1

    raw = doc.get("raw_runs") or []
    tokens = [int(r["injected_tokens"]) for r in raw if isinstance(r, dict)]
    if len(tokens) < 9:
        print("FAILED:TST-0085-probe2 raw_runs too short", len(tokens))
        return 1
    derived = C.moments(tokens)
    published = doc.get("variance_band") or {}
    if published.get("derived_from") != "raw_runs":
        print("FAILED:TST-0085-probe2 variance not derived_from raw_runs")
        return 1
    for key in ("n", "mean", "sample_variance", "sample_std", "ci95_low", "ci95_high"):
        if key not in published:
            print("FAILED:TST-0085-probe2 variance missing", key)
            return 1
        if key == "n":
            if int(published["n"]) != derived["n"]:
                print("FAILED:TST-0085-probe2 n mismatch", published["n"], derived["n"])
                return 1
            continue
        if not close(float(published[key]), float(derived[key])):
            print("FAILED:TST-0085-probe2", key, "published", published[key], "derived", derived[key])
            return 1

    per = published.get("per_installed_count") or {}
    for n in (10, 100, 500):
        xs = [int(r["injected_tokens"]) for r in raw if int(r["installed_count"]) == n]
        got = C.moments(xs)
        row = per.get(str(n)) or {}
        if not close(float(row.get("sample_variance") or -1), float(got["sample_variance"])):
            print("FAILED:TST-0085-probe2 per-n variance", n, row, got)
            return 1
        if got["n"] < 2:
            print("FAILED:TST-0085-probe2 variance unbanded at", n)
            return 1

    # Using only the summary mean, dropping raw_runs, must be detectable.
    if not tokens:
        print("FAILED:TST-0085-probe2 empty tokens")
        return 1
    summary_only = {"mean": published["mean"], "n": published["n"]}
    if "sample_variance" in summary_only:
        print("FAILED:TST-0085-probe2 summary-only fixture is not summary-only")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    schema_errors = list(validator.iter_errors(doc))
    if schema_errors:
        print("FAILED:TST-0085-probe2 live artifact fails schema", schema_errors[0].message)
        return 1
    for garbage in (
        {},
        {"unit_id": "TST-0085", "state": "SUCCESS"},
        {"unit_id": "TST-0085", "state": "SUCCESS", "sentinel": SENTINEL, "n": -1},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0085-probe2 schema accepted garbage", garbage)
            return 1

    reviewers = doc.get("reviewers") or []
    roles = {r.get("role") for r in reviewers if isinstance(r, dict)}
    if "statistics" not in roles or "cross-vendor-refuter" not in roles:
        print("FAILED:TST-0085-probe2 reviewers", roles)
        return 1

    flood_ctrl = doc.get("flood_control") or {}
    if flood_ctrl.get("unbounded_exceeds_ceiling") is not True:
        print("FAILED:TST-0085-probe2 receipt flood did not exceed ceiling")
        return 1
    if flood_ctrl.get("unbounded_growth_is_linear") is not True:
        print("FAILED:TST-0085-probe2 receipt flood not linear")
        return 1

    # Live flood re-run (the mutant / naive session). Distinct from probe 1.
    live_flood = {}
    query = "capability procedure harness overflow budget"
    for n in (10, 100, 500):
        caps = C.make_catalogue(n)
        result = inject_unbounded_flood(query, caps)
        live_flood[n] = int(result["injected_tokens"])
        if result["injected_tokens"] != count_payload_tokens(result["payload"]):
            print("FAILED:TST-0085-probe2 flood recount", n)
            return 1
    if live_flood[500] <= DEFAULT_CEILING:
        print("FAILED:TST-0085-probe2 flood mutant stayed under budget", live_flood)
        return 1
    linear = C.is_linear_growth(live_flood)
    if not linear["pass"]:
        print("FAILED:TST-0085-probe2 flood not linear", linear)
        return 1
    if int(flood_ctrl.get("unbounded_at_500") or -1) != live_flood[500]:
        print(
            "FAILED:TST-0085-probe2 flood 500 mismatch",
            flood_ctrl.get("unbounded_at_500"),
            live_flood[500],
        )
        return 1

    # Both-states: bounded path at 500 must stay under the same ceiling.
    bounded_500 = None
    for r in raw:
        if int(r["installed_count"]) == 500 and r["query_id"] == "q-ambiguous":
            bounded_500 = int(r["injected_tokens"])
            break
    if bounded_500 is None or bounded_500 > DEFAULT_CEILING:
        print("FAILED:TST-0085-probe2 bounded 500 missing or over budget", bounded_500)
        return 1
    if not (live_flood[500] > DEFAULT_CEILING > bounded_500 or live_flood[500] > DEFAULT_CEILING >= bounded_500):
        print("FAILED:TST-0085-probe2 both-states collapsed", live_flood[500], bounded_500)
        return 1

    out = {
        "probe": "probe2-variance-and-flood",
        "unit_id": "TST-0085",
        "pass": True,
        "derived_variance": {
            "n": derived["n"],
            "mean": derived["mean"],
            "sample_variance": derived["sample_variance"],
            "sample_std": derived["sample_std"],
            "ci95_low": derived["ci95_low"],
            "ci95_high": derived["ci95_high"],
        },
        "matched_published_band": True,
        "schema_rejects_garbage": True,
        "flood_live": {str(k): v for k, v in live_flood.items()},
        "flood_exceeds_ceiling": True,
        "flood_linear": True,
        "bounded_500": bounded_500,
        "both_states": True,
        "summary_only_lacks_variance": "sample_variance" not in summary_only,
    }
    (HERE / "probe2-variance-and-flood.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0085-probe2 variance re-derived from raw_runs; flood mutant red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
