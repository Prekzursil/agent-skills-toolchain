#!/usr/bin/env python3
"""WFA-0101 probe 1: recomposition equality, licence union, schema, sentinel."""
from __future__ import annotations

import ast
import inspect
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from jsonschema import Draft7Validator

from families import all_families
from fusion_op import (
    CATALOG_SCHEMA,
    LOCAL_SCHEMA,
    OUT_REL,
    exact_equal,
    fuse_family,
    named_inputs,
)
from semantic_diff import diff_workflows, self_diff_empty
from workflow_foundry.common_core import extract_family_core, recompose
from workflow_foundry.workflow_ir import Workflow, mutate_stage_gate

ART = REPO / OUT_REL
SCHEMA = REPO / LOCAL_SCHEMA
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0101-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        return fail(f"self-declared:{st}")
    if "SUCCESS:WFA-0101" not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema:{errors[0].message}")
    mutant = deepcopy(doc)
    mutant.pop("families", None)
    if not list(Draft7Validator(schema).iter_errors(mutant)):
        return fail("schema-both-states:deleting-families-still-valid")

    families = doc.get("families") or []
    if len(families) != 20:
        return fail(f"family-count:{len(families)}")
    ids = [f.get("family_id") for f in families]
    expected_ids = [spec.family_id for spec in all_families()]
    if ids != expected_ids:
        return fail(f"family-ids:{ids}")

    live = {spec.family_id: fuse_family(spec) for spec in all_families()}
    ok_n = empty_n = deg_n = 0
    for rec in families:
        fid = rec["family_id"]
        live_rec = live[fid]
        if rec["status"] != live_rec["status"]:
            return fail(f"{fid}:status-drift artifact={rec['status']} live={live_rec['status']}")
        if rec["status"] == "ok":
            ok_n += 1
            if rec.get("core") is None:
                return fail(f"{fid}:ok-but-core-null")
            rec_eq = rec["recomposition"]
            if rec_eq["exact_equal_n"] != rec_eq["n"] or rec_eq["n"] != rec["family_size"]:
                return fail(f"{fid}:recompose {rec_eq}")
            if not rec.get("licence_union_on_core"):
                return fail(f"{fid}:licence-union")
            if set(rec.get("core_licences") or []) != set(rec.get("licence_union") or []):
                return fail(f"{fid}:licence-set")
        else:
            if rec.get("core") is not None or rec.get("deltas"):
                return fail(f"{fid}:non-ok-emitted-core")
            if rec["status"] == "empty-intersection":
                empty_n += 1
                if rec.get("raw_lcs_size") != 0:
                    return fail(f"{fid}:empty-but-raw-lcs:{rec.get('raw_lcs_size')}")
            elif rec["status"] == "degenerate-intersection":
                deg_n += 1
                if int(rec.get("family_size") or 0) < 7:
                    return fail(f"{fid}:degenerate-family-too-small")
                if int(rec.get("raw_lcs_size") or 0) > 1:
                    return fail(f"{fid}:degenerate-raw-lcs")
            else:
                return fail(f"{fid}:unknown-status:{rec['status']}")

    if ok_n < 10 or empty_n < 2 or deg_n != 2:
        return fail(f"mix ok={ok_n} empty={empty_n} deg={deg_n}")

    spec_d1 = next(s for s in all_families() if s.family_id == "D1")
    honest, _ = extract_family_core(list(spec_d1.members))
    if honest.core is None:
        return fail("D1-core-missing")
    for src in spec_d1.members:
        rebuilt = recompose(honest.core, honest.deltas[src.id])
        if not exact_equal(src, rebuilt):
            return fail(f"D1-exact:{src.id}")
        if not self_diff_empty(src):
            return fail(f"D1-self-diff:{src.id}")
        if not diff_workflows(src, rebuilt)["empty"]:
            return fail(f"D1-semantic-recompose:{src.id}")

    mutated = mutate_stage_gate(spec_d1.members[0], 2, {"unanimity": False})
    gate_diff = diff_workflows(spec_d1.members[0], mutated)
    if gate_diff["empty"] or gate_diff["counts"].get("PRESENT-BUT-DIFFERENT", 0) < 1:
        return fail(f"semantic-diff-collapses-gate-mutation:{gate_diff['counts']}")
    src0 = spec_d1.members[0]
    dropped = Workflow(
        id="dropped",
        stages=list(src0.stages[1:]),
        edges=[],
        licences=src0.licences,
    )
    absent = diff_workflows(src0, dropped)
    if absent["counts"].get("ABSENT-IN-RIGHT", 0) < 1:
        return fail(f"semantic-diff-hides-absent-stage:{absent['counts']}")

    if "core.stages" not in inspect.getsource(recompose):
        return fail("recompose-does-not-read-core-stages")
    tree = ast.parse(inspect.getsource(extract_family_core))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    if "degeneracy_check" not in names:
        return fail("extract_family_core-skips-degeneracy_check")

    inputs = named_inputs()
    if doc["corpus"]["live_blueprint_library_present"] != inputs["blueprint-library"]["present"]:
        return fail("corpus-library-presence-lie")
    if str(doc.get("output_schema")) != CATALOG_SCHEMA:
        return fail("output-schema-field")

    print(
        json.dumps(
            {
                "ok": True,
                "ok_families": ok_n,
                "empty": empty_n,
                "degenerate": deg_n,
                "schema_ok": True,
                "schema_both_states": True,
                "sentinel": "SUCCESS:WFA-0101",
            },
            sort_keys=True,
        )
    )
    print(f"ok={ok_n} empty={empty_n} degenerate={deg_n} schema_ok=True both_states=True")
    print("SUCCESS:WFA-0101-probe1 core+delta recomposes exactly; empty/degenerate emit no core")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
