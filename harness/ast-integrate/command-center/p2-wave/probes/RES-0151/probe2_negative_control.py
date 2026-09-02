#!/usr/bin/env python3
"""Probe 2: independent refuter — both-states control, foils, mutant recount."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    diverse_sources,
    mutant_report,
    near_identical_sources,
    string_equality_distinct_count,
    NEAR_IDENTICAL_TEXTS,
)
from metric import load_prereg, score_run, score_run_string_equality, token_counter_fire  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0151-evidence-saturation-stopping-metric.json"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def independent_fire(yields, window, floor, min_sources):
    """Inline rolling-mean recount. Deliberately not metric.fire_index_from_yields."""
    n = len(yields)
    start = max(int(min_sources), int(window))
    for t in range(start, n + 1):
        chunk = yields[t - window : t]
        if len(chunk) < window:
            continue
        mean = sum(chunk) / float(window)
        if mean <= float(floor) + 1e-12:
            return t
    return None


def main() -> int:
    prereg = load_prereg()
    window = int(prereg["window"])
    floor = float(prereg["floor"])
    min_sources = int(prereg["min_sources"])
    early_max = int(prereg["early_max_index"])
    budget = int(prereg["token_counter_foil_budget_tokens"])

    near = score_run(near_identical_sources(), prereg)
    div = score_run(diverse_sources(), prereg)
    near_str = score_run_string_equality(near_identical_sources(), prereg)
    token_near = token_counter_fire(near_identical_sources(), budget)
    token_div = token_counter_fire(diverse_sources(), budget)
    mutants = mutant_report()

    near_idx = independent_fire(near["yields"], window, floor, min_sources)
    div_idx = independent_fire(div["yields"], window, floor, min_sources)
    print(
        json.dumps(
            {
                "near_fired": near["fired"],
                "near_index": near["fire_index"],
                "near_recount": near_idx,
                "near_early": near["early"],
                "near_distinct": near["total_distinct"],
                "string_distinct_paraphrases": string_equality_distinct_count(
                    NEAR_IDENTICAL_TEXTS
                ),
                "string_equality_fired": near_str["fired"],
                "diverse_fired": div["fired"],
                "diverse_recount": div_idx,
                "diverse_distinct": div["total_distinct"],
                "token_near": token_near,
                "token_div": token_div,
                "mutants": mutants["pass"],
            },
            sort_keys=True,
        )
    )

    if near_idx is None or near_idx > early_max:
        print(f"FAILED:RES-0151-probe2 near-identical did not fire early recount={near_idx}")
        return 1
    if near_idx != near["fire_index"]:
        print("FAILED:RES-0151-probe2 near fire_index != independent recount")
        return 1
    if div_idx is not None or div["fired"]:
        print(f"FAILED:RES-0151-probe2 diverse fired recount={div_idx}")
        return 1
    if token_near is None or token_div is None:
        print("FAILED:RES-0151-probe2 token-counter foil silent on a control")
        return 1
    if near_str["fired"]:
        print("FAILED:RES-0151-probe2 string-equality fired on paraphrases")
        return 1
    if string_equality_distinct_count(NEAR_IDENTICAL_TEXTS) != 30:
        print("FAILED:RES-0151-probe2 paraphrase strings were not 30-distinct")
        return 1
    if not mutants["pass"]:
        print("FAILED:RES-0151-probe2 mechanism mutants failed")
        return 1
    if not ART.is_file():
        print("FAILED:RES-0151-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:RES-0151-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0151" not in text:
        print("FAILED:RES-0151-probe2 sentinel-absent")
        return 1

    for row in doc.get("historical_replays") or []:
        yields = row.get("yields") or []
        rec = independent_fire(yields, window, floor, min_sources)
        if rec != row.get("fire_index"):
            print(
                f"FAILED:RES-0151-probe2 historical recount {row.get('run_id')} "
                f"art={row.get('fire_index')} recount={rec}"
            )
            return 1
        print(f"recount {row.get('run_id')} fire_index={rec} n={row.get('n_sources')}")

    nc = doc.get("negative_controls") or {}
    if (nc.get("near_identical") or {}).get("early") is not True:
        print("FAILED:RES-0151-probe2 artifact near_identical.early is not true")
        return 1
    if (nc.get("diverse") or {}).get("fired") is not False:
        print("FAILED:RES-0151-probe2 artifact diverse.fired is not false")
        return 1

    print(
        f"near_early={near['early']} idx={near_idx} diverse_silent={div_idx is None} "
        f"token_both={token_near is not None and token_div is not None} "
        f"mutants={mutants['pass']}"
    )
    print("SUCCESS:RES-0151-probe2 both-states control, foils, independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
