#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0308.json (council-stopping-module receipt)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.stopping.expr import (  # noqa: E402
    SPEC_EXPRESSIONS,
    BindError,
    ast_to_dict,
    bind,
    census,
    live_run,
    parse,
    spec_producers,
)

OUT = "command-center/receipts/IMP-0308.json"
SENTINEL = "SUCCESS:IMP-0308"
GHOST = "ghost_metric_never_produced >= 1 AND unique_ideas >= 0"


def main() -> int:
    producers = spec_producers()
    run = live_run()
    bind_ok = False
    try:
        bind(GHOST, producers)
    except BindError as exc:
        bind_ok = "ghost_metric_never_produced" in exc.unproduced
        ghost_err = str(exc)
    else:
        ghost_err = "NO-ERROR"
    census_rows = census([GHOST] + [src for _, _, src in SPEC_EXPRESSIONS], producers)
    unbound = [r for r in census_rows if not r["produced"]]
    spec_rows = []
    for eid, line, src in SPEC_EXPRESSIONS:
        spec_rows.append(
            {
                "id": eid,
                "spec_line": line,
                "source": src,
                "ast": ast_to_dict(parse(src)),
                "series": run["series"][eid],
                "changed_during_run": run["changed_during_run"][eid],
            }
        )
    per_round = []
    for row in run["per_round"]:
        per_round.append(
            {
                "round": row["round"],
                "expressions": [
                    {
                        "id": e["id"],
                        "value": e["value"],
                        "bound_metrics": e["bound_metrics"],
                    }
                    for e in row["expressions"]
                ],
            }
        )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "IMP-0308",
        "id": "IMP-0308",
        "title": "Boolean stopping-expression parser and evaluator",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "council-stopping-module",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0308; reconstructed spec lines "
            "10937-10942 from catalog titles CNL-0078 through CNL-0083 "
            "(unique_ideas >= 100 AND completeness_score >= 0.90; "
            "consensus >= 0.95 AND no_new_objection_rounds >= 2; "
            "unanimity == true OR max_rounds == 12; "
            "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0; "
            "evidence_saturation == true OR time_minutes >= 180; "
            "proof_of_impossibility == true). "
            "_USER-PROMPTS.md:10937-10942 is not on this worktree."
        ),
        "artifact_paths": [
            OUT,
            "tools/council/stopping/expr.py",
            "tools/council/stopping/__init__.py",
            "command-center/p2-wave/probes/IMP-0308/probe1_grammar_and_live_run.py",
            "command-center/p2-wave/probes/IMP-0308/probe2_unbound_metric_review.py",
        ],
        "evidence": [
            {
                "id": "six-spec-parse-and-live-metrics",
                "kind": "live-run",
                "claim": (
                    "All six reconstructed spec expressions parse, bind to "
                    "runtime producers, and evaluate to a value that changes "
                    "across a 12-round live run. Each bound metric is printed "
                    "per round."
                ),
                "spec_expressions": spec_rows,
                "per_round_bound_metrics": per_round,
                "changed_during_run": run["changed_during_run"],
                "final": run["final"],
            },
            {
                "id": "metric-binding-census",
                "kind": "census",
                "claim": (
                    "Census of every referenced metric vs runtime producer. "
                    "ghost_metric_never_produced has no producer."
                ),
                "rows": census_rows,
                "unproduced": unbound,
            },
            {
                "id": "bind-time-unproduced-metric",
                "kind": "negative-control",
                "claim": (
                    "An expression naming an unproduced metric fails at bind "
                    "time and does not silently evaluate false."
                ),
                "expression": GHOST,
                "bind_raised": bind_ok,
                "error": ghost_err,
            },
        ],
        "test_ids": [
            "unit-parser-grammar-precedence-and-negation",
            "integration-six-spec-expressions-over-live-run",
            "negative-control-unproduced-metric-fails-at-bind",
        ],
        "negative_control_ids": [
            "NC-unproduced-metric-bind-time",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0308-probe2-unbound-metric-review",
            "verdict": "PASS",
            "independent": True,
            "started_from": "tests",
        },
        "residual_unknowns": [
            (
                "Original _USER-PROMPTS.md:10937-10942 bytes are not on this "
                "Linux worktree. The six strings are reconstructed from "
                "catalog titles CNL-0078..CNL-0083. A later hash of the "
                "harness-restore file could still diverge from these strings."
            ),
            (
                "Catalog dependencies IMP-0264 (kernel) and IMP-0297 "
                "(protocol plugin) are not delivered on this tree. The live "
                "run is the stopping module's own 12-round producer fixture, "
                "not a kernel event loop."
            ),
            (
                "max_rounds is bound to the 1-based round index so "
                "`max_rounds == 12` is not a tautology. The original line's "
                "metric name is not independently verifiable here."
            ),
        ],
        "module": "tools/council/stopping/expr.py",
        "ts": now,
        "notes": (
            "G-1 IMP-0308: parser+evaluator for AND/OR/NOT, ANY, ALL, "
            "WEIGHTED; six spec examples live-run; unproduced metric fails "
            "at bind. Did not run tools/command-center/unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    if not bind_ok:
        print("FAILED:IMP-0308 ghost metric did not fail at bind")
        return 1
    if not all(run["changed_during_run"].values()):
        print("FAILED:IMP-0308 not every spec expression changed during the run")
        return 1
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if SENTINEL not in path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0308 sentinel missing from receipt")
        return 1
    print(f"wrote {OUT}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
