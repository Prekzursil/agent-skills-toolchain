#!/usr/bin/env python3
"""Probe 2: every sampled edge has independent verdict + mechanical score.

Where those two differ, mechanical is reported first. Stripping
mechanical_score from a row must make the checker fail. Schema must
reject garbage. Catalog sentinel must be in the artifact.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import score as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0067-dedup-edge-recheck.json"
SCHEMA = REPO / "command-center/schema/dedup-audit.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def complete(row: dict) -> tuple[bool, str]:
    if not row.get("independent_verdict"):
        return False, "missing-independent_verdict"
    if row.get("mechanical_score") is None:
        return False, "missing-mechanical_score"
    if row.get("original_verdict") not in {"DUPLICATE", "DISTINCT"}:
        return False, "missing-original_verdict"
    ev = row.get("evidence") or {}
    if ev.get("independent_verdict") != row["independent_verdict"]:
        return False, "evidence-independent-mismatch"
    if ev.get("original_verdict") != row["original_verdict"]:
        return False, "evidence-original-mismatch"
    mech_txt = (ev.get("mechanism_text") or {})
    if not mech_txt.get("from") or not mech_txt.get("to"):
        return False, "missing-mechanism-text"
    if row["independent_verdict"] != row.get("mechanical_verdict"):
        if row.get("reported_first") != "mechanical":
            return False, "reported_first-not-mechanical"
        ordered = row.get("verdicts_in_order") or []
        if not ordered or ordered[0].get("kind") != "mechanical":
            return False, "order-not-mechanical-first"
    return True, "ok"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0067-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next(u for u in catalog["work_units"] if u.get("id") == "CNF-0067")
    sentinel = unit["completion_sentinel"]
    if sentinel not in text:
        print("FAILED:CNF-0067-probe2 catalog sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0067-probe2 self-declared {doc.get('state')}")
        return 1
    if doc.get("brief_was_blind") is not True:
        print("FAILED:CNF-0067-probe2 brief_was_blind")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:CNF-0067-probe2 schema-invalid", errs[0].message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print("FAILED:CNF-0067-probe2 schema accepted garbage")
            return 1

    edges = doc.get("sampled_edges") or []
    if len(edges) < 4:
        print(f"FAILED:CNF-0067-probe2 too few edges n={len(edges)}")
        return 1

    claims_path = HERE / "fixtures" / "claims.json"
    claims = json.loads(claims_path.read_text(encoding="utf-8"))["claims"]
    S.assert_controls(claims)

    n_diff = 0
    for i, row in enumerate(edges):
        ok, why = complete(row)
        print(f"edge[{i}] {row.get('edge_id')} complete={ok} {why}")
        if not ok:
            print("FAILED:CNF-0067-probe2 incomplete edge")
            return 1
        left = row["evidence"]["mechanism_text"]["from"]
        right = row["evidence"]["mechanism_text"]["to"]
        live = S.judge_pair(left, right)
        if live["independent_verdict"] != row["independent_verdict"]:
            print("FAILED:CNF-0067-probe2 independent drift")
            return 1
        if live["mechanical_score"] != row["mechanical_score"]:
            print("FAILED:CNF-0067-probe2 mechanical drift")
            return 1
        if row["independent_verdict"] != row.get("mechanical_verdict"):
            n_diff += 1

    mutant = copy.deepcopy(doc)
    del mutant["sampled_edges"][0]["mechanical_score"]
    mok, mwhy = complete(mutant["sampled_edges"][0])
    print(f"mutant_without_score ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0067-probe2 mutant missing score was accepted")
        return 1
    if list(validator.iter_errors(mutant)) == []:
        # schema requires mechanical_score; absence must fail
        print("FAILED:CNF-0067-probe2 schema accepted mutant without score")
        return 1

    print(
        f"n_edges={len(edges)} mechanical_indep_diff={n_diff} "
        f"rate={doc.get('disagreement_rate')}"
    )
    print("SUCCESS:CNF-0067-probe2 edge scores + mechanical-first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
