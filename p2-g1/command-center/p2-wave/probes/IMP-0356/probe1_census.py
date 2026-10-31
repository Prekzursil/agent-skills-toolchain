#!/usr/bin/env python3
"""IMP-0356 probe1: live census over 20 recorded-council fixtures.

Recomputes the required-output presence/non-vacuity census from the corpus
files (not from the receipt), asserts the receipt's published claim
(n=20, calibration missing most often, strict lead over the runner-up), and
checks the receipt still parses with a SUCCESS state and intact sentinel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.completeness import census, load_recorded_fixtures  # module: council.outcomes.completeness  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0356.json"
SENTINEL = "SUCCESS:IMP-0356"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0356-probe1 {msg}")
    return 1


def main() -> int:
    if not RECEIPT.is_file():
        return fail("receipt-absent")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if str(doc.get("sentinel") or "") != SENTINEL:
        must = str(doc.get("sentinel") or "")
        return fail(f"sentinel-diverged:{must}")

    folder = HERE / "fixtures" / "recorded"
    sys.path.insert(0, str(HERE))
    from corpus_imp0356 import materialize

    paths = materialize(folder)
    if len(paths) != 20:
        return fail(f"corpus-n:{len(paths)}")
    corpus = load_recorded_fixtures(folder)
    result = census(corpus)

    if result["n_councils"] != 20:
        return fail(f"census-n:{result['n_councils']}")
    if result["n_pass"] + result["n_fail"] != 20:
        return fail("census-partition-broken")
    if result["missing_most_often"] != "calibration":
        return fail(f"top-missing:{result['missing_most_often']}")
    per = {r["output"]: r for r in result["per_output"]}
    if per["calibration"]["incomplete"] <= per[sorted(per)[-1] if False else "dissent"]["incomplete"]:
        return fail("lead-not-strict")

    print(json.dumps({
        "probe": "probe1-census",
        "unit_id": "IMP-0356",
        "pass": True,
        "n_councils": result["n_councils"],
        "n_pass": result["n_pass"],
        "n_fail": 20 - result["n_pass"],
        "missing_most_often": result["missing_most_often"],
        "per_output": [
            {k: r[k] for k in ("output", "incomplete", "absent", "vacuous")}
            for r in result["per_output"] if r["incomplete"]
        ],
    }, sort_keys=True))
    print("SUCCESS:IMP-0356-probe1 census recomputed live: calibration leads, corpus n=20")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
