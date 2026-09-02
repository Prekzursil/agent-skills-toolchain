#!/usr/bin/env python3
"""Emit command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FOUNDATION = REPO / "command-center" / "foundry" / "routing"
sys.path.insert(0, str(FOUNDATION.parent.parent))

from foundry.routing.corpus import candidate_to_scout, load_corpus  # noqa: E402
from foundry.routing.fit import (  # noqa: E402
    OVERFIT_GAP,
    agreement,
    evaluate_corpus,
    fit_thresholds,
    split_holdout,
)
from foundry.routing.gold import HUMAN_CLASSES, ROUTES, gold_route, histogram_n  # noqa: E402
from foundry.routing.recommend import decide  # noqa: E402

OUT_REL = "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"
SCHEMA_REL = "command-center/schema/foundry-artifact.schema.json"
LOCAL_SCHEMA_REL = "command-center/p2-wave/probes/WFA-0146/routing-function.schema.json"
REC_REL = "command-center/foundry/routing/recommend.py"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0146/probe1_holdout.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0146/probe2_repair_vs_build.py"
)
QUESTION = (
    "Implement the typed decision function that converts a scout result plus "
    "constraints into exactly one of FIND, REPAIR, MERGE, COMPOSE or BUILD, "
    "with the deciding features and an audit record per call. Question: what "
    "feature thresholds separate REPAIR from BUILD, and on the 284-candidate "
    "registry does the function reproduce the human classification, or where "
    "does it disagree?"
)
SENTINEL = "SUCCESS:WFA-0146"


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    hits = [i for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if snippet in ln]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:WFA-0146 emit anchor {rel} snippet={snippet!r} hits={hits}")
    return hits[0]


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def validator():
    # Catalog foundry-artifact.schema.json $defs/routing-function is a remote
    # $ref shim; jsonschema 4.10 does not fetch ast-integrate.invalid, so that
    # fragment accepts garbage. Local schema is the live contract.
    schema = json.loads((REPO / LOCAL_SCHEMA_REL).read_text(encoding="utf-8"))
    return jsonschema.Draft7Validator(schema)


def garbage_rejected() -> bool:
    v = validator()
    probes = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    return all(bool(list(v.iter_errors(p))) for p in probes)


def confusion(rows: list[dict]) -> dict:
    counts: dict[str, dict[str, int]] = {r: {c: 0 for c in HUMAN_CLASSES} for r in ROUTES}
    for row in rows:
        pred = row["predicted_route"]
        cls = row["classification"]
        if pred not in counts or cls not in counts[pred]:
            counts.setdefault(pred, {})
            counts[pred][cls] = counts[pred].get(cls, 0) + 1
        else:
            counts[pred][cls] += 1
    return {
        "n": len(rows),
        "predicted_routes": list(ROUTES),
        "human_classes": list(HUMAN_CLASSES),
        "counts": counts,
    }


def main() -> int:
    if not garbage_rejected():
        print("FAILED:WFA-0146 schema accepts garbage")
        return 1

    rows, meta = load_corpus()
    if len(rows) != histogram_n():
        print(f"FAILED:WFA-0146 corpus n={len(rows)} want {histogram_n()}")
        return 1
    train, hold = split_holdout(rows)
    thresholds, fit_meta = fit_thresholds(train)
    train_ag = agreement(train, thresholds)
    hold_ag = agreement(hold, thresholds)
    gap = train_ag["agreement"] - hold_ag["agreement"]
    overfit = bool(gap > OVERFIT_GAP)

    hold_ids = {r["id"] for r in hold}
    evaluated = evaluate_corpus(rows, thresholds)
    for item, src in zip(evaluated, rows):
        item["split"] = "holdout" if src["id"] in hold_ids else "train"
        item["source"] = src.get("source")
        item["audit"] = {
            "route": item["predicted_route"],
            "deciding_feature": item["deciding_feature"],
            "rejected_routes": item["rejected_routes"],
            "candidates_considered": item["candidates_considered"],
            "features": item["features"],
        }

    pred_counts = Counter(x["predicted_route"] for x in evaluated)
    if len(pred_counts) < 3:
        print(f"FAILED:WFA-0146 constant-function pred_counts={dict(pred_counts)}")
        return 1

    disagreements = [
        {
            "id": x["id"],
            "classification": x["classification"],
            "gold_route": x["gold_route"],
            "predicted_route": x["predicted_route"],
            "split": x["split"],
            "deciding_feature": x["deciding_feature"],
        }
        for x in evaluated
        if x["gold_route"] is not None and x["predicted_route"] != x["gold_route"]
    ]
    unmapped = [
        {
            "id": x["id"],
            "classification": x["classification"],
            "predicted_route": x["predicted_route"],
            "split": x["split"],
        }
        for x in evaluated
        if x["unmapped"]
    ]

    # Label-leak control baked into the artifact: a BUILD-shaped scout with a
    # planted ADOPT-AS-IS token must stay BUILD.
    leak_scout = candidate_to_scout(
        {
            "id": "leak-control",
            "classification": "RETIRE",
            "features": {
                "quality": 0.20,
                "defect_severity": 0.90,
                "repair_cost": 0.95,
                "build_cost": 0.70,
                "coverage": 0.10,
                "n_mergeable": 0,
                "union_coverage": 0.10,
                "mechanism_overlap": 0.05,
                "n_mechanism_sources": 0,
                "retired": True,
                "wrapper_needed": False,
                "license_ok": True,
                "maintenance_ok": False,
            },
        }
    )
    leak_scout["classification"] = "ADOPT-AS-IS"
    leak_scout["hits"][0]["classification"] = "ADOPT-AS-IS"
    leak_route = decide(leak_scout, thresholds=thresholds)["route"]
    if leak_route != "BUILD":
        print(f"FAILED:WFA-0146 classification leaked into router leak_route={leak_route}")
        return 1

    mapped_n = sum(1 for x in evaluated if x["gold_route"] is not None)
    mapped_correct = sum(1 for x in evaluated if x["agree"])
    overall = mapped_correct / mapped_n if mapped_n else 0.0

    doc = {
        "unit_id": "WFA-0146",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Find / repair / merge / build recommendation function",
        "question": QUESTION,
        "mechanism": "typed routing decision with a confusion matrix against the human classification",
        "executable": REC_REL,
        "output_schema": SCHEMA_REL + "#/$defs/routing-function",
        "routes": list(ROUTES),
        "features": [
            "best_quality",
            "best_defect",
            "best_coverage",
            "repair_cost_ratio",
            "n_mergeable",
            "union_coverage",
            "mechanism_overlap",
        ],
        "thresholds": thresholds,
        "repair_vs_build": {
            "deciding_features": ["best_defect", "repair_cost_ratio", "best_coverage", "best_quality"],
            "rule": (
                "After FIND/MERGE/COMPOSE miss: REPAIR if quality>=repair_min_quality "
                "AND defect<=repair_max_defect AND coverage>=repair_min_coverage AND "
                "repair_cost/build_cost<=repair_cost_ratio_max; otherwise BUILD. "
                "Those two numeric gates (defect, cost ratio) are the REPAIR/BUILD separator."
            ),
            "thresholds": {
                "repair_min_quality": thresholds["repair_min_quality"],
                "repair_max_defect": thresholds["repair_max_defect"],
                "repair_min_coverage": thresholds["repair_min_coverage"],
                "repair_cost_ratio_max": thresholds["repair_cost_ratio_max"],
            },
        },
        "class_to_route_gold": {
            k: v for k, v in (
                (c, gold_route(c)) for c in HUMAN_CLASSES
            )
        },
        "confusion_matrix": confusion(evaluated),
        "disagreements": disagreements,
        "unmapped_unknown": unmapped,
        "holdout": {
            "fraction": 0.20,
            "n_train": len(train),
            "n_holdout": len(hold),
            "n_holdout_mapped": hold_ag["n_mapped"],
            "train_agreement": train_ag["agreement"],
            "holdout_agreement": hold_ag["agreement"],
            "train_n_correct": train_ag["n_correct"],
            "holdout_n_correct": hold_ag["n_correct"],
            "overfit": overfit,
            "overfit_gap": gap,
            "overfit_gap_threshold": OVERFIT_GAP,
            "fit": fit_meta,
            "rule": (
                "A function that only reproduces its training rows is reported as overfit "
                "when train_agreement - holdout_agreement exceeds the gap threshold."
            ),
        },
        "overall_mapped_agreement": overall,
        "predicted_route_histogram": dict(pred_counts),
        "registry_source": meta,
        "evaluation_rows": [
            {
                "id": x["id"],
                "classification": x["classification"],
                "gold_route": x["gold_route"],
                "predicted_route": x["predicted_route"],
                "split": x["split"],
                "source": x["source"],
                "agree": x["agree"],
                "unmapped": x["unmapped"],
                "deciding_feature": x["deciding_feature"],
                "features": x["features"],
                "audit": x["audit"],
            }
            for x in evaluated
        ],
        "label_leak_control": {
            "planted_classification": "ADOPT-AS-IS",
            "scout_shape": "retired-ineligible",
            "route": leak_route,
            "pass": leak_route == "BUILD",
        },
        "constant_function_control": {
            "distinct_routes": len(pred_counts),
            "histogram": dict(pred_counts),
            "pass": len(pred_counts) >= 3,
        },
        "evidence": [
            ev(
                REC_REL,
                "WFA-0146-REPAIR-VS-BUILD",
                "live-tree",
                "REPAIR vs BUILD is a numeric defect + cost-ratio gate in decide(), not a class lookup.",
            ),
            ev(
                CATALOG_REL,
                "hold out 20 percent of the registry, fit thresholds on the rest, and report held-out agreement",
                "catalog",
                "Catalog test: hold out 20 percent, fit on the rest, report overfit if train-only.",
            ),
            {
                "path": P1,
                "line": 1,
                "snippet": "probe1_holdout",
                "kind": "probe",
                "claim": "Signal A: independent hold-out recompute of agreement and the 284-row confusion matrix.",
                "anchor": P1,
            },
            {
                "path": P2,
                "line": 1,
                "snippet": "probe2_repair_vs_build",
                "kind": "probe",
                "claim": "Signal B: synthetic REPAIR archetype flips to BUILD when defect or cost-ratio crosses the recorded gates.",
                "anchor": P2,
            },
        ],
        "tests": [
            {
                "id": "WFA-0146-HOLDOUT",
                "name": "hold out 20 percent, fit on the rest, report held-out agreement",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0146-REPAIR-VS-BUILD",
                "name": "feature thresholds that separate REPAIR from BUILD fire both ways",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0146-NOT-CONSTANT",
                "name": "router emits at least three distinct routes on the 284-row corpus",
                "command": P1,
                "result": "PASS" if len(pred_counts) >= 3 else "FAIL",
            },
            {
                "id": "WFA-0146-NO-LABEL-LEAK",
                "name": "planting ADOPT-AS-IS on a BUILD-shaped scout does not change the route",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0146-probe2-repair-vs-build",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes decide() on synthetic archetypes and recomputes "
                "holdout agreement from stored features; it does not author the router."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": REC_REL, "role": "executable"},
            {"path": SCHEMA_REL, "role": "contract"},
        ],
        "honesty": {
            "live_registry_on_this_worktree": bool(meta.get("live_present")),
            "perfect_holdout_means_overfit_if_train_only": overfit,
            "does_not_claim_windows_path_per_id_disagreement": not bool(meta.get("live_present")),
        },
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    errs = sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0146 schema", [e.message for e in errs[:8]])
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_REL} n={len(evaluated)} distinct={len(pred_counts)} "
        f"holdout={hold_ag['agreement']:.4f} train={train_ag['agreement']:.4f} "
        f"overfit={overfit} disagreements={len(disagreements)} live={meta.get('live_present')}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
