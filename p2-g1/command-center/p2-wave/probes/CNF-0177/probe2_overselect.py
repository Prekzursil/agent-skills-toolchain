#!/usr/bin/env python3
"""Probe 2: ten adversarial over-select tasks (mechanically different from probe 1).

Reviewer-authored traps: generic asks must not become confident wrong picks;
a kitchen-sink prompt must stay inside top-k/budget on the instrument; the
flood mutant must exceed the budget (detector both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0177-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0177" not in json.dumps(doc):
        print("FAILED:CNF-0177-probe2 sentinel absent")
        return 1
    src = str(doc.get("source_probe") or "")
    ver = str(doc.get("verifier_probe") or "")
    if not src or not ver or src == ver:
        print("FAILED:CNF-0177-probe2 source/verifier missing or identical")
        return 1
    fp = H.fingerprints()
    if fp["source"] == fp["verifier"]:
        print("FAILED:CNF-0177-probe2 probe file fingerprints identical")
        return 1
    if fp["source"] not in src or fp["verifier"] not in ver:
        print("FAILED:CNF-0177-probe2 fingerprint not bound to record")
        print(src)
        print(ver)
        return 1

    adv_path = H.FIX / "adversarial-overselect.json"
    if not adv_path.is_file():
        print("FAILED:CNF-0177-probe2 adversarial fixture missing")
        return 1
    adv = json.loads(adv_path.read_text(encoding="utf-8"))
    tasks = adv.get("tasks") or []
    if len(tasks) != 10:
        print(f"FAILED:CNF-0177-probe2 expected 10 adversarial tasks got {len(tasks)}")
        return 1
    ids = [t["id"] for t in tasks]
    if len(set(ids)) != 10:
        print("FAILED:CNF-0177-probe2 duplicate adversarial ids")
        return 1

    bundle = H.load_frozen()
    inv = bundle["inventory"]
    prod = H.run_tasks(H.route_missing, tasks, inv)
    inst = H.run_tasks(H.route_instrument, tasks, inv)
    flood = H.run_tasks(H.route_flood, tasks, inv)

    generic = [r for r in inst if r["class"] in {"generic-trap", "known-absent-adversarial", "inject-all-ask", "over-select-ask", "flood-ask"}]
    generic_over = [r for r in generic if r["selected"]]
    if generic_over:
        print("FAILED:CNF-0177-probe2 instrument over-selected on generic traps", [r["id"] for r in generic_over])
        return 1

    prod_confident = [r for r in prod if r["selected"] and r.get("confidence") != "fallback"]
    if prod_confident:
        print("FAILED:CNF-0177-probe2 production made a confident pick while absent", prod_confident)
        return 1

    kitchen = next(r for r in inst if r["id"] == "ADV-1")
    if len(kitchen["selected"]) > H.TOP_K:
        print(f"FAILED:CNF-0177-probe2 kitchen-sink selected {len(kitchen['selected'])} > k={H.TOP_K}")
        return 1
    if kitchen["injected_tokens"] > H.BUDGET_TOKENS:
        print("FAILED:CNF-0177-probe2 kitchen-sink flooded on instrument")
        return 1
    if not kitchen["selected"]:
        print("FAILED:CNF-0177-probe2 kitchen-sink selected nothing; trap is not stressing top-k")
        return 1

    flood_max = max(r["injected_tokens"] for r in flood)
    if flood_max <= H.BUDGET_TOKENS:
        print(f"FAILED:CNF-0177-probe2 flood mutant max={flood_max} did not exceed budget")
        return 1

    reviewer = doc.get("reviewer") or {}
    if int(reviewer.get("n_tasks") or 0) != 10:
        print("FAILED:CNF-0177-probe2 reviewer n_tasks")
        return 1

    summary = {
        "probe": "probe2-overselect",
        "unit_id": "CNF-0177",
        "n_adversarial": 10,
        "generic_overselect": [r["id"] for r in generic_over],
        "kitchen_sink_selected": kitchen["selected"],
        "kitchen_sink_tokens": kitchen["injected_tokens"],
        "flood_mutant_max_tokens": flood_max,
        "budget_tokens": H.BUDGET_TOKENS,
        "production_confident_picks": len(prod_confident),
        "source_fp": fp["source"][:16],
        "verifier_fp": fp["verifier"][:16],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0177-probe2 adversarial over-select reviewer tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
