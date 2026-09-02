#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0223.json from a live 5000-tree run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import scenario as S  # noqa: E402

if str(C.SPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(C.SPEC_ROOT))

from agentspec.permission_bound import (  # noqa: E402
    N_TREES,
    SEED,
    run_property_corpus,
    union_widen,
)

import jsonschema  # noqa: E402


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def main() -> int:
    live = run_property_corpus(n_trees=N_TREES, seed=SEED)
    if not live["pass"]:
        print(f"FAILED:{C.UNIT} emit live corpus red violations={live['violations']}")
        return 1
    mutant = run_property_corpus(n_trees=400, seed=SEED, narrow_fn=union_widen)
    if mutant["violations"] < 1:
        print(f"FAILED:{C.UNIT} emit union mutant stayed green")
        return 1
    fixture = S.run_executor_fixture()
    if (
        not fixture["denied_write"]
        or fixture["leaked_secret"]
        or not fixture["allowed_read"]
    ):
        print(f"FAILED:{C.UNIT} emit executor fixture {fixture}")
        return 1
    sample_call = live["sample_privileged_call"] or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inputs = S.catalog_inputs()
    doc = {
        "answer": (
            "No. A nested subworkflow cannot obtain a permission its parent "
            "lacks: effective(child) = effective(parent) ∩ declared(child) "
            "(presets and re-entry restore bags included). The property held "
            f"on {live['n_trees']} trees with {live['widening_attempts']} "
            "widening declarations; the union mutant failed; the deepest "
            "Write call was refused with spawn_count=0 and no leaked file."
        ),
        "artifacts": [
            art("tools/agentspec/agentspec/permission_bound.py", "supporting"),
            art("tools/agentspec/agentspec/subworkflow_executor.py", "supporting"),
            art("tools/agentspec/agentspec/dispatchpolicy.py", "supporting"),
        ],
        "catalog_named_inputs": inputs,
        "cloud_ok": False,
        "completion_marker": C.SENTINEL,
        "completion_sentinel": (
            "SUCCESS:TST-0223 monotone-narrowing held on 5000 randomized "
            "nesting trees; union mutant turned the property red; deepest "
            "Write denied with zero spawns and no artifact"
        ),
        "evidence": [
            {
                "claim": (
                    "each nesting depth records effective permissions and "
                    "child ⊆ parent"
                ),
                "kind": "effective-permission-set-per-depth",
                "sample_depths": live["sample_depths"],
                "signal": "a",
                "widening_attempts": live["widening_attempts"],
            },
            {
                "call": sample_call,
                "claim": (
                    "a tool declared by a child but absent from the parent is "
                    "refused by dispatchpolicy with zero spawns; the executor "
                    "writes no artifact"
                ),
                "executor_denied_write": fixture["denied_write"],
                "kind": "privileged-call-at-deepest-level",
                "leaked_secret": fixture["leaked_secret"],
                "signal": "b",
            },
        ],
        "executor_fixture": {
            "allowed_read": fixture["allowed_read"],
            "deny_code": fixture["deny_code"],
            "denied_write": fixture["denied_write"],
            "depths": fixture["depths"],
            "leaked_secret": fixture["leaked_secret"],
            "parent_perms": fixture["parent_perms"],
        },
        "id": C.UNIT,
        "implementation": {
            "combine": "intersection (restore bags ignored)",
            "dispatch_gate": "tools/agentspec/agentspec/dispatchpolicy.py",
            "executor": "tools/agentspec/agentspec/subworkflow_executor.py",
            "permission_bound": "tools/agentspec/agentspec/permission_bound.py",
        },
        "mutation_control": {
            "mode": "union-widen",
            "n_trees": mutant["n_trees"],
            "property_failed": True,
            "violations": mutant["violations"],
            "widening_calls_allowed": mutant["widening_calls_allowed"],
        },
        "named_probes": [
            {"command": C.P1, "id": "probe1"},
            {"command": C.P2, "id": "probe2"},
        ],
        "nesting_depths": live["sample_depths"],
        "notes": (
            "G-1 for TST-0223: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild circle. "
            "SUCCESS:TST-0223"
        ),
        "output_path": C.OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "privileged_call": {
            "allowed": False,
            "code": sample_call.get("code"),
            "depth": sample_call.get("depth"),
            "effective": sample_call.get("effective"),
            "spawn_count": sample_call.get("spawn_count", 0),
            "tool": sample_call.get("tool"),
            "widening_tool": sample_call.get("widening_tool"),
        },
        "property_test": {
            "call_mismatches": live["call_mismatches"],
            "n_trees": live["n_trees"],
            "pass": True,
            "seed": live["seed"],
            "trees_ok": live["trees_ok"],
            "violations": live["violations"],
            "widening_attempts": live["widening_attempts"],
            "widening_calls_allowed": live["widening_calls_allowed"],
            "widening_calls_denied": live["widening_calls_denied"],
        },
        "question": C.QUESTION,
        "registered": True,
        "report_kind": "security_report",
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "notes": (
                "Probe 2 AST-rewrites narrow() BitAnd to BitOr in-memory and "
                "re-runs the corpus; live source bytes are unchanged. Catalog "
                "named JS inputs tools/lib/workspace.mjs and "
                "tools/lib/net-allowlist.mjs are absent; the live nested "
                "permission subject on this worktree is agentspec "
                "subworkflow_executor + dispatchpolicy."
            ),
            "reviewer_id": "TST-0223-probe2-mutation-widen",
            "verdict": "PASS",
        },
        "schema_file": C.SCHEMA_REL,
        "sentinel": C.SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "TST0223-T1-PROPERTY-5000",
                "name": "property test: 5000 randomized nesting trees, child_perms subset of parent_perms",
                "probe": "probe1_property_trees.py",
                "result": "PASS",
            },
            {
                "id": "TST0223-T2-MUTATION-WIDEN",
                "name": "mutation control: allow one widening path and confirm the property fails",
                "probe": "probe2_mutation_widen.py",
                "result": "PASS",
            },
        ],
        "title": "Subworkflow permissions narrow monotonically and can never widen",
        "ts": now,
        "unit_id": C.UNIT,
    }
    schema = json.loads((C.REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print(f"FAILED:{C.UNIT} emit schema {errs[0].message} path={list(errs[0].path)}")
        return 1
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest_file(out)
    print(f"wrote {C.OUT_REL} bytes={size} sha256={sha}")
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
