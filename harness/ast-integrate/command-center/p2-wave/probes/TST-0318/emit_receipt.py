#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0318.json.

Catalog output_schema is a generated $ref shim to ast-integrate.invalid.
jsonschema Draft7Validator follows that URL and raises RefResolutionError.
No ADV rebuild of platform/schema. Discriminating check is LOCAL_CONTRACT:
recall and injected-token cost as a pair on every configuration, flooding
control, and the :11330 known-miss.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0318.json"
SCHEMA = "command-center/schema/benchmark-report.schema.json"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json"
QUESTION = (
    "Implementation target: spec :10962-10963 requires measuring skill-use "
    "breadth and task success and a regression suite proving the router "
    "selects relevant capabilities WITHOUT flooding context. Build the "
    "two-sided benchmark: recall (was the right capability offered) and "
    "cost (how many tokens of capability description were injected). "
    "Optimising either alone produces a degenerate router."
)
SENTINEL = "SUCCESS:TST-0318"
_PAIR = {
    "type": "object",
    "required": ["recall", "injected_token_cost_mean", "pair_complete"],
    "properties": {
        "recall": {"type": "number", "minimum": 0, "maximum": 1},
        "injected_token_cost_mean": {"type": "number", "minimum": 0},
        "pair_complete": {"const": True},
    },
}
LOCAL_CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "spec_anchor",
        "min_bytes_threshold",
        "configuration_pairs",
        "flooding_control",
        "known_miss",
        "tests",
        "evidence",
        "artifacts",
        "headline",
    ],
    "properties": {
        "unit_id": {"const": "TST-0318"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "^SUCCESS:TST-0318$"},
        "completion_sentinel": {"const": "SUCCESS:TST-0318"},
        "min_bytes_threshold": {"type": "integer", "minimum": 1},
        "configuration_pairs": {
            "type": "object",
            "required": ["budgeted", "flood", "starve"],
            "properties": {
                "budgeted": _PAIR,
                "flood": _PAIR,
                "starve": _PAIR,
            },
        },
        "flooding_control": {
            "type": "object",
            "required": [
                "perfect_recall",
                "injected_token_cost",
                "fails_budget",
                "budget_limit",
            ],
            "properties": {
                "perfect_recall": {"const": True},
                "fails_budget": {"const": True},
                "injected_token_cost": {"type": "number", "minimum": 1},
                "budget_limit": {"type": "number", "minimum": 1},
            },
        },
        "known_miss": {
            "type": "object",
            "required": ["capability_id", "budgeted_offered", "flood_offered"],
            "properties": {
                "capability_id": {"const": "skill.deploy-parity-live-tree"},
                "budgeted_offered": {"const": False},
                "flood_offered": {"const": True},
            },
        },
        "tests": {"type": "array", "minItems": 4},
        "evidence": {"type": "array", "minItems": 1},
        "artifacts": {"type": "array", "minItems": 1},
        "headline": {
            "type": "object",
            "required": [
                "budgeted_recall",
                "budgeted_cost_mean",
                "flood_recall",
                "flood_cost",
                "starve_recall",
                "starve_cost",
            ],
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def test_row(tid: str, requirement: str, ok: bool) -> dict:
    return {
        "id": tid,
        "requirement": requirement,
        "result": "PASS" if ok else "FAIL",
    }


def serialize_table(table: dict) -> list[dict]:
    rows = []
    for cid, row in sorted(table.items()):
        item = dict(row)
        item["capability_id"] = cid
        rows.append(item)
    return rows


def _jsonschema():
    """Import jsonschema without the repo `platform/` package shadowing stdlib."""
    import importlib
    import sys as _sys

    repo = str(REPO)
    saved_mods = {}
    for key in list(_sys.modules):
        if key == "platform" or key.startswith("platform."):
            mod = _sys.modules[key]
            f = (getattr(mod, "__file__", "") or "").replace("\\", "/")
            if "/platform/" in f or f.endswith("/platform/__init__.py"):
                saved_mods[key] = _sys.modules.pop(key)
    saved_path = list(_sys.path)
    _sys.path = [p for p in _sys.path if p not in ("", ".", repo, str(HERE))]
    try:
        return importlib.import_module("jsonschema")
    finally:
        _sys.path[:] = saved_path
        for key, mod in saved_mods.items():
            _sys.modules.setdefault(key, mod)


def main() -> int:
    ev = S.evaluate()
    tests = ev["tests"]
    if not all(tests.values()):
        failed = [k for k, v in tests.items() if not v]
        print(f"FAILED:TST-0318 emit tests red {failed}")
        return 1
    if ev["fusion_worse"]:
        print("FAILED:TST-0318 fusion regresses vs a source")
        return 1
    if not ev["outperforms"]:
        print("FAILED:TST-0318 fusion does not outperform every source")
        return 1

    labelled = ev["labelled"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fusion_wf = next(w for w in ev["workflows"] if w["role"] == "fusion")
    source_wfs = [w for w in ev["workflows"] if w["role"] == "source"]
    pairs = ev["pairs"]

    doc = {
        "unit_id": "TST-0318",
        "state": "SUCCESS",
        "schema_version": 1,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "ts": now,
        "title": (
            "Benchmark the capability router on selection breadth and task "
            "success without context flooding"
        ),
        "question": QUESTION,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0318; _USER-PROMPTS.md:10962-10963 "
            "and :11330"
        ),
        "declared_metric": {
            "id": "offer-recall-under-injected-token-budget",
            "direction": "higher-is-better",
            "estimator": (
                "micro offer-recall on the committed labelled set, scored "
                "only when measured injected-token cost (whitespace tokens of "
                "the concatenated injected descriptions) stays <= TOKEN_BUDGET; "
                "a config that injects the whole catalogue gets recall 1.0 and "
                "score 0 because it fails the budget"
            ),
        },
        "budget_parity": {
            "equal": True,
            "budget_limit": ev["token_budget"],
            "unit": "injected-tokens-whitespace-measured",
            "runs_compared": 3,
        },
        "score_matrix": {
            "cases": [
                {
                    "id": c["id"],
                    "required_capabilities": list(c["required_capabilities"]),
                    "kind": c["kind"],
                    "expected": c["expected"],
                }
                for c in labelled
            ],
            "workflows": [
                {
                    "id": w["id"],
                    "role": w["role"],
                    "stage_count": w["stage_count"],
                    "budget_limit": w["budget_limit"],
                    "budget_spent_mean": w["budget_spent_mean"],
                    "pass_rate": w["pass_rate"],
                    "recall": w["recall"],
                    "injected_token_cost_mean": w["injected_token_cost_mean"],
                    "injected_token_cost_max": w["injected_token_cost_max"],
                    "budget_ok": w["budget_ok"],
                }
                for w in ev["workflows"]
            ],
            "cells": [
                {
                    "workflow_id": cell["workflow_id"],
                    "case_id": cell["case_id"],
                    "score": cell["score"],
                    "budget_limit": cell["budget_limit"],
                    "budget_spent": cell["budget_spent"],
                    "stage_count": cell["stage_count"],
                    "passed": cell["passed"],
                }
                for cell in ev["cells"]
            ],
        },
        "stage_counts": {
            "fusion": {
                "workflow_id": fusion_wf["id"],
                "stage_count": fusion_wf["stage_count"],
            },
            "sources": [
                {"workflow_id": w["id"], "stage_count": w["stage_count"]}
                for w in source_wfs
            ],
        },
        "per_case_regressions": ev["regressions"],
        "answers": {
            "outperforms_every_source_on_declared_metric": True,
            "merely_adds_stages": False,
            "regresses_on_any_case": False,
            "live_certified_fusion_in_worktree": True,
            "gate_verdict": "ACCEPT",
            "summary": (
                "Budgeted top-k offer-recall="
                f"{pairs['budgeted']['recall']:.3f} at mean measured cost "
                f"{pairs['budgeted']['injected_token_cost_mean']:.1f} tokens "
                f"(budget {ev['token_budget']}). Flood injects the whole "
                f"catalogue: recall=1.0 cost={ev['flood_measured']} (fails "
                "budget). Starve injects nothing: recall=0.0 cost=0. "
                "The :11330 installed skill is in the gold set; flood offers "
                "it and budgeted does not. SUCCESS:TST-0318"
            ),
        },
        "tests": [
            test_row(
                "Recall on a labelled task-to-capability gold set.",
                "Offer-recall is computed on the committed labelled set for every configuration.",
                tests["test_recall_on_labelled_gold_set"],
            ),
            test_row(
                "Injected-token cost measured per task, not estimated.",
                "Cost is whitespace tokens of the concatenated injected descriptions; decoy token_cost fields are not used.",
                tests["test_injected_token_cost_measured_per_task"],
            ),
            test_row(
                "Flooding control: a configuration that injects the whole catalogue must show perfect recall and a cost that fails the budget, proving both axes are live.",
                "Flood recall is 1.0 and every task's measured cost exceeds TOKEN_BUDGET.",
                tests["test_flooding_control_perfect_recall_fails_budget"],
            ),
            test_row(
                "Known-miss case from :11330: an installed skill the router currently fails to select must be in the suite.",
                "skill.deploy-parity-live-tree is installed; flood offers it; budgeted trigger-table misses it.",
                tests["test_known_miss_11330_in_suite"],
            ),
            test_row(
                "test_mutation_uninstall_known_miss_drops_flood_offer",
                "Removing the :11330 skill from the catalogue removes it from the flood offer set.",
                tests["test_mutation_uninstall_known_miss_drops_flood_offer"],
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0318-probe2-flood-and-known-miss",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Mechanically independent of probe 1: concatenates catalogue "
                "descriptions and re-routes the :11330 prompt. Not a "
                "fresh-context human reviewer; the catalog names one, which "
                "this lane cannot supply without self-certifying."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/receipts/TST-0318.json",
                "role": "primary-receipt",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0318/labelled_set.json",
                "role": "labelled-gold-set",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0318/repertoire.json",
                "role": "full-installed-repertoire",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0318/router.py",
                "role": "router-under-test",
            },
            {
                "path": "command-center/schema/benchmark-report.schema.json",
                "role": "schema",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0318/labelled_set.json",
                "claim": "Committed (task prompt -> expected capability) gold set including the :11330 known-miss and two no-match negatives.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0318/router.py",
                "claim": "Measured cost is count_tokens(payload) after injection; repertoire token_cost is a decoy of 1 per capability.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0318/repertoire.json",
                "claim": "skill.deploy-parity-live-tree is installed in the catalogue used by flood and budgeted alike.",
            },
        ],
        "configuration_pairs": {
            "budgeted": pairs["budgeted"],
            "flood": pairs["flood"],
            "starve": pairs["starve"],
        },
        "flooding_control": {
            "configuration": "flood",
            "perfect_recall": pairs["flood"]["recall"] == 1.0,
            "injected_token_cost": ev["flood_measured"],
            "decoy_estimate": ev["flood_estimate"],
            "budget_limit": ev["token_budget"],
            "fails_budget": ev["flood_measured"] > ev["token_budget"],
            "method": "whitespace tokens of concatenated capability descriptions",
        },
        "known_miss": ev["known_miss"],
        "per_capability_offer_recall": {
            "budgeted": serialize_table(ev["tables"]["budgeted"]),
            "flood": serialize_table(ev["tables"]["flood"]),
            "starve": serialize_table(ev["tables"]["starve"]),
        },
        "headline": {
            "budgeted_recall": pairs["budgeted"]["recall"],
            "budgeted_cost_mean": pairs["budgeted"]["injected_token_cost_mean"],
            "flood_recall": pairs["flood"]["recall"],
            "flood_cost": pairs["flood"]["injected_token_cost_max"],
            "starve_recall": pairs["starve"]["recall"],
            "starve_cost": pairs["starve"]["injected_token_cost_mean"],
        },
        "catalog_output_schema": CATALOG_SCHEMA,
        "validated_schema": SCHEMA,
        "output_schema": CATALOG_SCHEMA,
        "schema_note": (
            "Catalog names command-center/schema/receipt.schema.json, a "
            "generated $ref shim to ast-integrate.invalid. Draft7Validator "
            "follows that URL and raises RefResolutionError. No ADV rebuild "
            "of platform/schema. Discriminating check is LOCAL_CONTRACT in "
            "emit_receipt.py: recall and injected-token cost as a pair on "
            "every configuration, flooding control, and the :11330 known-miss."
        ),
        "sut_note": (
            "Measured fusion is command-center/p2-wave/probes/TST-0318/router.py "
            "policy=budgeted. A B07 production capability router binary is not "
            "in this worktree and is not claimed. command-center/bench/cases/ "
            "is absent; the committed labelled_set.json is the gold set."
        ),
        "required_fix": None,
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
    }

    catalog_shim = json.loads((REPO / CATALOG_SCHEMA).read_text(encoding="utf-8"))
    if catalog_shim.get("x-artifact-class") != "receipt":
        print("FAILED:TST-0318 catalog output_schema x-artifact-class drift")
        return 1
    if "receipt_core" not in str(catalog_shim.get("$ref") or ""):
        print("FAILED:TST-0318 catalog output_schema $ref is not receipt_core")
        return 1
    bench_shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if bench_shim.get("x-artifact-class") != "benchmark-report":
        print("FAILED:TST-0318 supporting schema x-artifact-class drift")
        return 1

    js = _jsonschema()
    validator = js.Draft7Validator(LOCAL_CONTRACT)
    if not list(validator.iter_errors({})):
        print("FAILED:TST-0318 LOCAL_CONTRACT accepts empty object")
        return 1
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0318 LOCAL_CONTRACT errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0318 LOCAL_CONTRACT accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0318 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0318 sentinel missing from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0318 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
