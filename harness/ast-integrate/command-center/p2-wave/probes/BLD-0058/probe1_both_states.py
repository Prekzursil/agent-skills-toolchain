#!/usr/bin/env python3
"""Probe 1: both-states 10x 429s, 529 concurrency control, NOT-CHECKED quotas."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import model as M  # noqa: E402
import quotas as Q  # noqa: E402
import sim as S  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0058.json"
SCHEMA = REPO / "command-center/schema/scale-model.schema.json"
SENTINEL = "SUCCESS:BLD-0058"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0058-probe1 {msg}")
    return 1


def main() -> int:
    import jsonschema

    baseline = Q.catalog_n()
    scaled = baseline * 10
    both = S.both_states_10x(scaled)
    if both["burst_429"] <= 0:
        return fail("burst produced no 429s (vacuous)")
    if both["stagger_429"] != 0:
        return fail(f"stagger 429s={both['stagger_429']}")
    if both["burst_200"] + both["burst_429"] != scaled:
        return fail("burst accounting")
    if both["stagger_200"] != scaled:
        return fail("stagger did not admit all")

    trial = S.overload_trial(8)
    if trial.classification != "VENDOR_OVERLOAD":
        return fail(f"529 class {trial.classification}")
    if not trial.correct_kept_cap:
        return fail(f"correct reduced cap {trial.cap_after_correct}")
    if not trial.naive_reduced_cap:
        return fail("naive control did not reduce — test cannot see a reduction")
    if S.classify_status(429) != "OUR_ARRIVAL_RATE":
        return fail("429 class")

    live = M.build()
    unchecked = [r for r in live["quotas"] if r["status"] == "NOT-CHECKED"]
    if len(unchecked) < 2:
        return fail(f"expected two subscription remaining rows, got {len(unchecked)}")
    for row in unchecked:
        if row["numeric_value"] is not None:
            return fail(f"NOT-CHECKED defaulted {row['id']}={row['numeric_value']}")
        if row["kind"] != "subscription_remaining_usd":
            return fail(f"unexpected NOT-CHECKED kind {row}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    if jsonschema.Draft7Validator(schema).is_valid({"totally": "unrelated"}):
        return fail("schema vacuous")

    rec_both = (doc.get("schedule") or {}).get("both_states") or {}
    if rec_both.get("burst_429") != both["burst_429"]:
        return fail(f"receipt burst_429 {rec_both.get('burst_429')} != {both['burst_429']}")
    if rec_both.get("stagger_429") != 0:
        return fail("receipt stagger not zero")
    rec_unchecked = [r for r in doc.get("quotas") or [] if r.get("status") == "NOT-CHECKED"]
    if len(rec_unchecked) < 2:
        return fail("receipt missing NOT-CHECKED quotas")
    for row in rec_unchecked:
        if row.get("numeric_value") is not None:
            return fail(f"receipt defaulted {row.get('id')}")

    rec_err = {e["http_status"]: e for e in doc.get("error_classes") or []}
    if rec_err.get(529, {}).get("concurrency_after_correct") != 8:
        return fail("receipt 529 reduced concurrency")
    if rec_err.get(429, {}).get("class") != "OUR_ARRIVAL_RATE":
        return fail("receipt 429 class")

    print(
        json.dumps(
            {
                "probe": "probe1-both-states",
                "baseline_n": baseline,
                "scaled_n": scaled,
                "burst_429": both["burst_429"],
                "stagger_429": both["stagger_429"],
                "not_checked": [r["id"] for r in unchecked],
                "529_cap_before": trial.cap_before,
                "529_cap_after": trial.cap_after_correct,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:BLD-0058-probe1 both-states burst_429={both['burst_429']} "
        f"stagger_429=0 529_cap={trial.cap_after_correct} "
        f"not_checked={len(unchecked)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
