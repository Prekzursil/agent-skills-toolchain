#!/usr/bin/env python3
"""Probe 1: recompute aggregation, literature extractors, lineage, contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import protocol as P  # noqa: E402


def main() -> int:
    if not P.ART.is_file():
        print("FAILED:RES-0182-probe1 artifact missing")
        return 1
    doc = P.load_json(P.ART)
    live = P.run_protocol()
    errors = []
    stated = str((doc.get("adoption") or {}).get("status") or "")
    if stated != live["adoption"]:
        errors.append(f"adoption-drift:{stated}!={live['adoption']}")
    if float(live["literature_truths"]["LIT-1"]["truth"]) != 4.0:
        errors.append("idea-stage-count-not-4")
    if float(live["literature_truths"]["LIT-2"]["truth"]) != 3.0:
        errors.append("cooke-quantile-count-not-3")
    for qid, truth in live["local_truths"].items():
        row = next(
            (r for r in (doc.get("questions_no_literature") or []) if r.get("id") == qid),
            None,
        )
        if row is None:
            errors.append(f"nl-row-absent:{qid}")
            continue
        if float(row.get("local_truth")) != float(truth):
            errors.append(f"local-drift:{qid}")
        live_eq = live["aggregations"][qid]["equal_weight"]
        stated_eq = ((row.get("aggregation") or {}).get("equal_weight") or {})
        if stated_eq.get("q50") != live_eq["q50"]:
            errors.append(f"eq-median-drift:{qid}")
    checked = P.evaluate(doc)
    if not checked["pass"]:
        errors.extend(checked["errors"])
    payload = {
        "probe": "probe1-recompute",
        "unit_id": P.UNIT,
        "pass": len(errors) == 0,
        "errors": errors,
        "adoption": live["adoption"],
        "lit_misses": live["lit_misses"],
        "nl_hits": live["nl_hits"],
        "idea_stages": live["literature_truths"]["LIT-1"]["truth"],
        "cooke_quantiles": live["literature_truths"]["LIT-2"]["truth"],
        "derivation": "recompute-from-participants-and-snapshot-extractors",
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        print("FAILED:RES-0182-probe1 " + ";".join(errors[:8]))
        return 1
    print(
        f"adoption={live['adoption']} lit_misses={live['lit_misses']} "
        f"nl_hits={live['nl_hits']}/{live['nl_n']} "
        f"idea={int(live['literature_truths']['LIT-1']['truth'])} "
        f"cooke_q={int(live['literature_truths']['LIT-2']['truth'])}"
    )
    print("SUCCESS:RES-0182-probe1 recompute aggregation lineage contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
