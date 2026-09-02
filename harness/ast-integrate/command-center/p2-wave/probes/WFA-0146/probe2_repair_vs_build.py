#!/usr/bin/env python3
"""Probe 2: REPAIR vs BUILD threshold both-states + label-leak + schema + anchors.

Signal B is a different mechanism from probe 1: synthetic archetypes, not the
284-row corpus fit. Crossing the recorded defect or cost-ratio gate must flip
REPAIR to BUILD; an irrelevant feature must not.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from foundry.routing.corpus import scout_from_extracted_features  # noqa: E402
from foundry.routing.gold import ROUTES, gold_route  # noqa: E402
from foundry.routing.recommend import decide  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"
SCHEMA = REPO / "command-center/schema/foundry-artifact.schema.json"
REC = "command-center/foundry/routing/recommend.py"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0146-probe2 {msg}")
    return 1


def validator():
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return jsonschema.Draft7Validator({"$ref": "#/$defs/routing-function", "$defs": root["$defs"]})


def resolve_anchor(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}"
    if snippet not in lines[line - 1]:
        return False, f"snippet-miss:{rel}:{line}"
    return True, f"{rel}:{line}"


def archetype(kind: str) -> dict:
    if kind == "FIND":
        return {
            "goal": "find-arch",
            "hits": [
                {
                    "id": "incumbent",
                    "quality": 0.94,
                    "defect_severity": 0.06,
                    "repair_cost": 0.10,
                    "build_cost": 0.80,
                    "coverage": 0.93,
                    "license_ok": True,
                    "retired": False,
                }
            ],
            "scout_features": {
                "n_mergeable": 1,
                "union_coverage": 0.93,
                "mechanism_overlap": 0.15,
                "n_mechanism_sources": 1,
            },
            "constraints": {},
        }
    if kind == "REPAIR":
        return {
            "goal": "repair-arch",
            "hits": [
                {
                    "id": "salvageable",
                    "quality": 0.60,
                    "defect_severity": 0.42,
                    "repair_cost": 0.32,
                    "build_cost": 0.80,
                    "coverage": 0.76,
                    "license_ok": True,
                    "retired": False,
                }
            ],
            "scout_features": {
                "n_mergeable": 1,
                "union_coverage": 0.76,
                "mechanism_overlap": 0.25,
                "n_mechanism_sources": 1,
            },
            "constraints": {},
        }
    if kind == "MERGE":
        return {
            "goal": "merge-arch",
            "hits": [
                {
                    "id": "part-a",
                    "quality": 0.70,
                    "defect_severity": 0.14,
                    "repair_cost": 0.40,
                    "build_cost": 0.85,
                    "coverage": 0.50,
                    "license_ok": True,
                    "retired": False,
                },
                {
                    "id": "part-b",
                    "quality": 0.66,
                    "defect_severity": 0.14,
                    "repair_cost": 0.40,
                    "build_cost": 0.85,
                    "coverage": 0.45,
                    "license_ok": True,
                    "retired": False,
                },
            ],
            "scout_features": {
                "n_mergeable": 2,
                "union_coverage": 0.90,
                "mechanism_overlap": 0.35,
                "n_mechanism_sources": 2,
            },
            "constraints": {},
        }
    if kind == "COMPOSE":
        return {
            "goal": "compose-arch",
            "hits": [
                {
                    "id": "mechanism-src",
                    "quality": 0.64,
                    "defect_severity": 0.20,
                    "repair_cost": 0.45,
                    "build_cost": 0.80,
                    "coverage": 0.48,
                    "license_ok": True,
                    "retired": False,
                }
            ],
            "scout_features": {
                "n_mergeable": 1,
                "union_coverage": 0.48,
                "mechanism_overlap": 0.80,
                "n_mechanism_sources": 2,
            },
            "constraints": {},
        }
    if kind == "BUILD":
        return {
            "goal": "build-arch",
            "hits": [],
            "scout_features": {
                "n_mergeable": 0,
                "union_coverage": 0.0,
                "mechanism_overlap": 0.0,
                "n_mechanism_sources": 0,
            },
            "constraints": {},
        }
    raise ValueError(kind)


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0146" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    T = doc.get("thresholds") or {}
    if not T:
        return fail("no thresholds")

    v = validator()
    errs = list(v.iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    for probe in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(v.iter_errors(probe)):
            return fail("schema accepted garbage")

    got = {}
    for kind in ROUTES:
        got[kind] = decide(archetype(kind), thresholds=T)["route"]
        print(f"archetype {kind} -> {got[kind]}")
        if got[kind] != kind:
            return fail(f"archetype {kind} routed {got[kind]}")
    if len(set(got.values())) != 5:
        return fail(f"archetypes collapsed {got}")

    repair = archetype("REPAIR")
    if decide(repair, thresholds=T)["route"] != "REPAIR":
        return fail("baseline REPAIR missed")

    high_defect = copy.deepcopy(repair)
    high_defect["hits"][0]["defect_severity"] = float(T["repair_max_defect"]) + 0.05
    hd = decide(high_defect, thresholds=T)["route"]
    print(f"repair_plus_defect -> {hd}")
    if hd != "BUILD":
        return fail(f"defect above repair_max_defect routed {hd} want BUILD")

    high_ratio = copy.deepcopy(repair)
    high_ratio["hits"][0]["repair_cost"] = float(T["repair_cost_ratio_max"]) * 0.80 + 0.20
    high_ratio["hits"][0]["build_cost"] = 0.80
    hr = decide(high_ratio, thresholds=T)["route"]
    print(f"repair_plus_ratio -> {hr}")
    if hr != "BUILD":
        return fail(f"ratio above repair_cost_ratio_max routed {hr} want BUILD")

    find = archetype("FIND")
    find_hi = copy.deepcopy(find)
    find_hi["scout_features"]["mechanism_overlap"] = 0.99
    if decide(find, thresholds=T)["route"] != "FIND":
        return fail("FIND baseline")
    if decide(find_hi, thresholds=T)["route"] != "FIND":
        return fail("irrelevant overlap flipped FIND")

    leak = archetype("BUILD")
    leak["classification"] = "ADOPT-AS-IS"
    leak["hits"] = [
        {
            "id": "retired-labelled-adopt",
            "quality": 0.15,
            "defect_severity": 0.95,
            "repair_cost": 0.99,
            "build_cost": 0.70,
            "coverage": 0.05,
            "license_ok": True,
            "retired": True,
            "classification": "ADOPT-AS-IS",
        }
    ]
    leak_route = decide(leak, thresholds=T)["route"]
    print(f"label-leak planted ADOPT-AS-IS on BUILD shape -> {leak_route}")
    if leak_route != "BUILD":
        return fail(f"classification leaked: {leak_route}")

    # Independent holdout recompute from stored features (does not refit).
    hold_rows = [r for r in (doc.get("evaluation_rows") or []) if r.get("split") == "holdout"]
    if len(hold_rows) < 1:
        return fail("no holdout rows")
    mapped = 0
    correct = 0
    for row in hold_rows:
        gold = gold_route(str(row.get("classification")))
        if gold is None:
            continue
        mapped += 1
        scout = scout_from_extracted_features(row.get("features") or {}, str(row.get("id")))
        pred = decide(scout, thresholds=T)["route"]
        if pred != row.get("predicted_route"):
            return fail(f"stored-vs-recomputed route {row.get('id')} {pred} vs {row.get('predicted_route')}")
        if pred == gold:
            correct += 1
    recomputed = correct / mapped if mapped else 0.0
    stored = float((doc.get("holdout") or {}).get("holdout_agreement"))
    if abs(recomputed - stored) > 1e-9:
        return fail(f"holdout recompute {recomputed} vs stored {stored}")

    live = bool((doc.get("registry_source") or {}).get("live_present"))
    if live:
        path = (doc.get("registry_source") or {}).get("live_path")
        if not path or not Path(path).is_file():
            return fail("live_present true but path missing")
    else:
        recon = (doc.get("registry_source") or {}).get("reconstruction")
        if not recon:
            return fail("live_present false but reconstruction unnamed")
        if not (doc.get("honesty") or {}).get("does_not_claim_windows_path_per_id_disagreement"):
            return fail("overclaim: reconstruction claims live per-id disagreement")

    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        return fail("evidence < 2")
    tree = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        snippet = str(row.get("snippet") or "")
        kind = str(row.get("kind") or "")
        if kind == "probe":
            p = REPO / rel if not rel.startswith("PYTHONDONTWRITEBYTECODE") else None
            # probe evidence names a command string; require the script to exist
            if "probe1_holdout.py" in rel:
                if not (HERE / "probe1_holdout.py").is_file():
                    return fail("probe1 missing")
                continue
            if "probe2_repair_vs_build.py" in rel:
                if not (HERE / "probe2_repair_vs_build.py").is_file():
                    return fail("probe2 missing")
                continue
            continue
        line = int(row.get("line") or 0)
        ok, why = resolve_anchor(rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            return fail(f"unresolved anchor {why}")
        if kind == "live-tree":
            tree += 1
    if tree < 1:
        return fail("no live-tree anchor")
    rec_hits = [
        i
        for i, ln in enumerate((REPO / REC).read_text(encoding="utf-8").splitlines(), 1)
        if "WFA-0146-REPAIR-VS-BUILD" in ln
    ]
    if rec_hits != [next(e["line"] for e in evidence if e.get("snippet") == "WFA-0146-REPAIR-VS-BUILD")]:
        return fail(f"repair-vs-build marker line drift {rec_hits}")

    print(
        f"repair_gate defect->{hd} ratio->{hr} archetypes=5 leak={leak_route} "
        f"holdout_recompute={recomputed:.4f}"
    )
    print("SUCCESS:WFA-0146-probe2 repair-vs-build both-states label-leak schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
