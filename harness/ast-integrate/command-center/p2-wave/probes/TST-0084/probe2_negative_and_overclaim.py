#!/usr/bin/env python3
"""Named probe 2: negative control + overclaim gate (independent of probe 1).

1. No-match tasks must return fallback.none with confident=false.
2. Popularity-greedy must be a confident wrong pick on those same tasks
   (proves the fallback path is not vacuous).
3. Usage-pruned source must show recall=0 on rarely-used skills while its
   micro-average stays >= 0.5 — the headline-hides-zero overclaim the catalog
   forbids. Fusion must not.
4. Mutation: drop skill.nul-device-census from a copied index; that row goes red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import metrics as M  # noqa: E402
import scenario as S  # noqa: E402
from router import FALLBACK_ID, route  # noqa: E402

OUT = HERE / "probe2-overclaim.raw.json"
ART = REPO / "command-center/receipts/TST-0084.json"
RARE = frozenset({"skill.nul-device-census", "skill.windows-long-path"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0084-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0084" not in json.dumps(doc):
        return fail("sentinel absent")

    labelled = S.cases()
    caps = S.capabilities()
    full = S.run_policy("full", caps)
    pruned = S.run_policy("usage-pruned", caps)
    greedy = S.run_policy("popularity-greedy", caps)

    negatives = [c for c in labelled if c["kind"] == "negative"]
    if len(negatives) < 2:
        return fail("need >=2 negative cases")
    neg_ids = {c["id"] for c in negatives}
    full_neg = [p for p in full if p["case_id"] in neg_ids]
    if any(p["capability_id"] != FALLBACK_ID or p["confident"] for p in full_neg):
        return fail(f"full negative not fallback {full_neg}")

    greedy_neg = [p for p in greedy if p["case_id"] in neg_ids]
    if not greedy_neg or any(
        (not p["confident"]) or p["capability_id"] == FALLBACK_ID for p in greedy_neg
    ):
        return fail("greedy negative control is vacuous (not a confident wrong pick)")

    # Direct re-route of a no-match prompt (does not reuse evaluate()).
    weather = next(c for c in labelled if c["id"] == "case.weather-none")
    live = route(weather["prompt"], caps, policy="full")
    if live["capability_id"] != FALLBACK_ID or live["confident"]:
        return fail(f"live weather route {live}")

    pruned_table = M.per_capability_table(labelled, pruned)
    full_table = M.per_capability_table(labelled, full)
    pruned_micro = M.micro_recall(pruned_table)
    pruned_over = M.overclaim_hidden_zero(pruned_table, pruned_micro)
    if not pruned_over["hidden_zero_recall"]:
        return fail(f"pruned overclaim gate silent micro={pruned_micro}")
    missing_rare = RARE - set(pruned_over["zero_recall_capabilities"])
    if missing_rare:
        return fail(f"pruned zeros missing rare {missing_rare}")

    full_over = M.overclaim_hidden_zero(full_table, M.micro_recall(full_table))
    if full_over["hidden_zero_recall"] or M.zero_recall_capabilities(full_table):
        return fail("fusion hidden zero")

    mutant_caps = [c for c in caps if c["id"] != "skill.nul-device-census"]
    mutant = [route(c["prompt"], mutant_caps, policy="full") for c in labelled]
    mutant_table = M.per_capability_table(labelled, mutant)
    nul = mutant_table.get("skill.nul-device-census") or {}
    if not (nul.get("gold", 0) >= 1 and nul.get("recall") == 0):
        return fail(f"mutation did not turn rare skill red {nul}")

    claimed_over = (doc.get("overclaim") or {}).get("usage-pruned") or {}
    if claimed_over.get("hidden_zero_recall") is not True:
        return fail("receipt did not record pruned hidden-zero overclaim")

    payload = {
        "probe": "probe2-negative-and-overclaim",
        "unit_id": "TST-0084",
        "full_negatives": full_neg,
        "greedy_negatives": greedy_neg,
        "pruned_overclaim": pruned_over,
        "full_overclaim": full_over,
        "mutant_nul_recall": nul.get("recall"),
        "computed_not_asserted": True,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "neg_fallback": True,
                "greedy_confident_wrong": True,
                "pruned_hidden_zero": True,
                "mutant_nul_recall": nul.get("recall"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0084-probe2 negative-control overclaim-gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
