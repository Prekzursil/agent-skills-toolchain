#!/usr/bin/env python3
"""Probe 1: after fix, rate==1.0 and unresolved==0; fabrication does not close."""
from __future__ import annotations

import ast
import inspect
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator

import closure as C  # noqa: E402
from closure import (  # noqa: E402
    apply_fix,
    candidate_admissible,
    check_closure,
    classify_all,
    filesystem_only_classify,
    naive_fabricate_candidates,
)
from estate import evidence_b, load_head_index, pair_ab, scan_filesystem  # noqa: E402
from fixtures import ESTATE, HEAD_INDEX_PATH, all_refs, materialize  # noqa: E402

UNIT = "WFA-0002"
ART = REPO / "command-center" / "wfa" / "WFA-0002-provenance-closure.json"
SCHEMA = HERE / "probe_report.schema.json"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def inspect_admissible_source() -> str | None:
    src = inspect.getsource(candidate_admissible)
    tree = ast.parse(src)
    reads_sha = "sha256" in src
    reads_path = "anchor_path" in src
    reads_bytes = "bytes" in src
    saw_true = False
    saw_false = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            if node.value.value is True:
                saw_true = True
            if node.value.value is False:
                saw_false = True
    if not reads_sha or not reads_path or not reads_bytes:
        return "candidate_admissible-does-not-read-anchor-fields"
    if saw_true and not saw_false:
        return "candidate_admissible-constant-true"
    return None


def run_fixture_closure() -> dict:
    planted = materialize()
    refs = planted["refs"]
    graph = planted["graph"]
    registry = planted["registry"]
    hits_a = scan_filesystem([ESTATE])
    head = load_head_index(HEAD_INDEX_PATH)
    hits_b = evidence_b(refs, head, repo=None)
    rows = pair_ab(refs, hits_a, hits_b)
    classifications = classify_all(rows)
    before = check_closure(graph, registry)
    fixed = apply_fix(graph, registry, classifications)
    after = check_closure(fixed["graph"], fixed["registry"])
    naive_reg = {
        "candidates": list(registry.get("candidates") or [])
        + naive_fabricate_candidates(refs)
    }
    naive = check_closure(graph, naive_reg)
    fs_only = filesystem_only_classify(rows)
    return {
        "planted": planted,
        "rows": rows,
        "classifications": classifications,
        "before": before,
        "fixed": fixed,
        "after": after,
        "naive": naive,
        "fs_only": fs_only,
    }


def main() -> int:
    err = inspect_admissible_source()
    if err:
        return fail(err)
    if C.candidate_admissible({"id": "x", "name": "x"}):
        return fail("name-only-candidate-was-admissible")
    if C.candidate_admissible(
        {
            "name": "x",
            "provenance": {"anchor_path": "p", "sha256": "abcd", "bytes": 12},
        }
    ):
        return fail("short-sha-was-admissible")

    run = run_fixture_closure()
    refs = run["planted"]["refs"]
    if len(refs) != 40:
        return fail(f"ref-count:{len(refs)}")
    if len(set(refs)) != 40:
        return fail("refs-not-distinct")
    if run["before"]["provenance_edges_unresolved"] != 66:
        return fail(f"before-unresolved:{run['before']}")
    if run["after"]["provenance_edges_unresolved"] != 0:
        return fail(f"after-unresolved:{run['after']}")
    if run["after"]["provenance_resolution_rate"] != 1.0:
        return fail(f"after-rate:{run['after']['provenance_resolution_rate']}")
    if not run["after"]["rate_is_one"]:
        return fail("rate_is_one-false")

    if run["naive"]["provenance_edges_unresolved"] != 66:
        return fail(
            f"fabrication-closed-edges naive_unresolved="
            f"{run['naive']['provenance_edges_unresolved']}"
        )
    if run["naive"]["provenance_resolution_rate"] == 1.0:
        return fail("fabrication-reported-rate-1")

    honest_add = {n for n, c in run["classifications"].items() if c["disposition"] == "ADD"}
    honest_correct = {
        n for n, c in run["classifications"].items() if c["disposition"] == "CORRECT"
    }
    expected_add = set(run["planted"]["add_both"]) | set(run["planted"]["live_only"]) | set(
        run["planted"]["repo_only"]
    )
    expected_correct = set(run["planted"]["phantom"])
    if honest_add != expected_add:
        return fail(f"add-set {sorted(honest_add ^ expected_add)[:8]}")
    if honest_correct != expected_correct:
        return fail(f"correct-set {sorted(honest_correct ^ expected_correct)[:8]}")
    if run["fixed"]["rejected_fabrication"]:
        return fail(f"honest-rejected {run['fixed']['rejected_fabrication']}")

    fs_add = {n for n, c in run["fs_only"].items() if c["disposition"] == "ADD"}
    missed_repo = set(run["planted"]["repo_only"]) - fs_add
    if missed_repo != set(run["planted"]["repo_only"]):
        return fail(f"filesystem-only-mutant-saw-repo-only {sorted(missed_repo)}")

    live_drifts = [r for r in run["rows"] if r.get("drift") == "live-only"]
    repo_drifts = [r for r in run["rows"] if r.get("drift") == "repo-only"]
    if len(live_drifts) != 8:
        return fail(f"live-only-drift:{len(live_drifts)}")
    if len(repo_drifts) != 8:
        return fail(f"repo-only-drift:{len(repo_drifts)}")
    fs_drifts = [c for c in run["fs_only"].values() if c.get("drift")]
    if fs_drifts:
        return fail("filesystem-only-mutant-must-hide-drift")

    for name in run["planted"]["add_both"]:
        row = next(r for r in run["rows"] if r["name"] == name)
        if not row["A_hit"] or not row["B_hit"]:
            return fail(f"{name}:expected-both-hits")
        if not row.get("A_bytes"):
            return fail(f"{name}:A-missing-size")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        return fail(f"self-declared:{st}")
    if "SUCCESS:WFA-0002" not in text:
        return fail("sentinel-absent")
    if doc.get("provenance_resolution_rate") != 1.0:
        return fail("artifact-rate-not-1")
    if doc.get("provenance_edges_unresolved") != 0:
        return fail("artifact-unresolved-not-0")
    if (doc.get("recall_limit") or {}).get("invented_original_40") is not False:
        return fail("invented-original-40")
    classes = doc.get("classifications") or []
    if len(classes) != 40:
        return fail(f"artifact-classifications:{len(classes)}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema:{errors[0].message}")
    mutant = deepcopy(doc)
    mutant.pop("classifications", None)
    if not list(Draft202012Validator(schema).iter_errors(mutant)):
        return fail("schema-both-states:deleting-classifications-still-valid")

    payload = {
        "ok": True,
        "probe": "probe1-closure-rate",
        "unit_id": UNIT,
        "n_refs": 40,
        "n_edges": 66,
        "before_unresolved": run["before"]["provenance_edges_unresolved"],
        "after_unresolved": run["after"]["provenance_edges_unresolved"],
        "after_rate": run["after"]["provenance_resolution_rate"],
        "naive_unresolved": run["naive"]["provenance_edges_unresolved"],
        "add": len(honest_add),
        "correct": len(honest_correct),
        "live_only_drift": len(live_drifts),
        "repo_only_drift": len(repo_drifts),
        "filesystem_only_missed_repo_only": len(missed_repo),
        "schema_ok": True,
        "schema_both_states": True,
        "sentinel": "SUCCESS:WFA-0002",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0002-probe1 after-fix rate=1.0 unresolved=0; "
        "fabrication does not close; A-vs-B drift recorded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
