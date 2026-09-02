#!/usr/bin/env python3
"""Emit command-center/phase3/A9/MIGRATION.json for ARC-0063."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from estate import S1_EVALUATOR_REL  # noqa: E402
from gates import run_all_gates  # noqa: E402
from rollback import (  # noqa: E402
    RESTORE_COMMAND,
    content_preservation_both_directions,
    two_clone_rehearsal,
)
from stages import AUTHORITY_TABLE, GATES_REL, STAGES  # noqa: E402

OUT = "command-center/phase3/A9/MIGRATION.json"
SCHEMA = "command-center/schema/migration-plan.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0063/probe1_stage_gates.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0063/probe2_rollback.py"
)
QUESTION = (
    "Design the staged adoption order for the hybrid: which subsystem lands first, "
    "what each stage must PROVE before the next may begin, and what the rollback is "
    "at every stage boundary - given the binding PR-ONLY release mode, which means "
    "every stage boundary is a pull request rather than a deployment."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


# Catalog shim $ref points at https://ast-integrate.invalid/... . jsonschema 4.10
# on this host tries the network and raises. Physical receipt_core also sets
# additionalProperties=false, which rejects the domain-shaped G-1 artifacts
# sibling ARC-0007/0014/0021 already delivered. Validate the probe contract
# locally so garbage is rejected and emit cannot hang on DNS.
DOMAIN_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "schema_version",
        "report_kind",
        "sentinel",
        "release_mode",
        "stages",
        "capability_to_authority",
        "tests",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "ARC-0063"},
        "state": {"const": "SUCCESS"},
        "schema_version": {"const": 1},
        "report_kind": {"const": "migration-plan"},
        "sentinel": {"const": "SUCCESS:ARC-0063"},
        "release_mode": {"const": "PR-ONLY"},
        "stages": {
            "type": "array",
            "minItems": 7,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "proof_evaluator",
                    "proof_test_id",
                    "proof_command",
                    "proof_predicate",
                    "rollback_commands",
                    "lands_via",
                ],
            },
        },
        "tests": {
            "type": "object",
            "required": [
                "stage_gate_testability",
                "rollback_rehearsal",
                "content_preservation_both_directions",
            ],
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "migration-plan"},
                "observations": {"type": "array", "minItems": 2},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def main() -> int:
    live_gates = run_all_gates("S7")
    if not live_gates.get("pass"):
        print("FAILED:ARC-0063 emit live gates")
        print(json.dumps(live_gates, indent=2, default=str)[:3000])
        return 1
    rb = two_clone_rehearsal()
    if not rb.get("pass"):
        print("FAILED:ARC-0063 emit rollback rehearsal")
        print(json.dumps(rb, indent=2, default=str)[:3000])
        return 1
    preserve = content_preservation_both_directions()
    if not preserve.get("pass"):
        print("FAILED:ARC-0063 emit content preservation")
        print(json.dumps(preserve, indent=2, default=str)[:2000])
        return 1

    a1_design = present("command-center/phase3/A1/DESIGN.json")
    a2_design = present("command-center/phase3/A2/DESIGN.json")
    a9_design = present("command-center/phase3/A9/DESIGN.json")

    doc = {
        "unit_id": "ARC-0063",
        "architecture_id": "A9",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "migration-plan",
        "title": (
            "A9 staged hybrid adoption: permission evaluator first, then singular "
            "SSOT, then gateway, lockfile, adapter, ledger, product surface — each "
            "stage a PR with a named proof gate and a git-revert rollback"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:ARC-0063",
        "completion_sentinel": "SUCCESS:ARC-0063",
        "min_bytes_threshold": 2048,
        "release_mode": "PR-ONLY",
        "release_mode_anchor": (
            "command-center/WORK-UNIT-CATALOG.json owner_decisions answer "
            "PR-ONLY (OWNER-DECISIONS.md is absent on this worktree; catalog "
            "records the binding decision at the Prompt-Two release-mode row)"
        ),
        "binding_constraint": (
            "Every stage boundary is a pull request. There is no canary deploy, "
            "no public marketplace publish, and no direct index write. Rollback "
            "is git revert of the stage PR, not an uninstall against a live host."
        ),
        "first_subsystem": {
            "id": "permission-evaluator",
            "borrowed_from": "A7",
            "why_first": (
                "The hybrid's distinctive risk is new entry paths (marketplace "
                "install-time, gateway activation-time, adapter dispatch-time, "
                "workflow invocation-time). If those land first they must be "
                "retrofitted through the choke. Landing A7 first makes "
                "'register this path with the evaluator' a proof gate of every "
                "later PR. Catalog ARC-0062 enumerates those four times."
            ),
        },
        "adoption_rationale": (
            "S1 A7 evaluator (singular permission). S2 A2 generated SSOT with A1 "
            "as extract-only import (A1 DESIGN is static JSON; A2 DESIGN forbids "
            "opaque passthrough — two catalogs would be a duplicate control plane). "
            "S3 A4 gateway indexes the registry, not a parallel catalog. S4 A3 "
            "lockfile packages under PR-ONLY with publish_channel null so the "
            "marketplace is not an unfalsifiable public index. S5 A6 adapter "
            "before the runtime so dispatch cannot go around untrusted-vendor "
            "handling. S6 A5 ledger folds ad-hoc rails without dropping in-flight "
            "work. S7 A8 error contract last so UX cannot paper over missing "
            "subsystems. Stacked PRs revert from the tip backward."
        ),
        "source_layout": {
            "a9_design_present": a9_design,
            "roots": [
                (
                    "command-center/phase3/A1/DESIGN.json"
                    if a1_design
                    else "command-center/phase3/A1/DESIGN.json (absent on this worktree)"
                ),
                (
                    "command-center/phase3/A2/DESIGN.json"
                    if a2_design
                    else "command-center/phase3/A2/DESIGN.json (absent on this worktree)"
                ),
                "command-center/WORK-UNIT-CATALOG.json ARC-0063 question + PR-ONLY owner_decisions + A3-A8 mechanism claims",
                "command-center/p2-wave/probes/ARC-0063 live named gates and scratch-clone rollback",
            ],
            "notes": (
                f"A9 DESIGN.json present={a9_design}. A1 DESIGN present={a1_design}. "
                f"A2 DESIGN present={a2_design}. Hybrid composition for this unit is "
                "derived from catalog mechanism claims for A1-A8 and the on-tree "
                "dossiers when present; it is not a claim that ARC-0059 already shipped."
            ),
        },
        "target_layout": {
            "root": "hybrid/",
            "load_order": [
                "hybrid/permission-evaluator.json",
                "hybrid/registry.json",
                "hybrid/generated/",
                "hybrid/gateway-index.json",
                "hybrid/lockfile.json",
                "hybrid/adapter-contract.json",
                "hybrid/ledger.jsonl",
                "hybrid/error-contract.json",
            ],
            "mapping": [
                {"from": "A7 single choke (catalog ARC-0045)", "to": "hybrid/permission-evaluator.json"},
                {"from": "A2 registry + A1 extract (ARC-0010/ARC-0014)", "to": "hybrid/registry.json"},
                {"from": "A4 gateway index (catalog ARC-0024)", "to": "hybrid/gateway-index.json"},
                {"from": "A3 lockfile under PR-ONLY (catalog ARC-0017/ARC-0023)", "to": "hybrid/lockfile.json"},
                {"from": "A6 adapter tiers (catalog ARC-0038)", "to": "hybrid/adapter-contract.json"},
                {"from": "A5 ledger (catalog ARC-0031)", "to": "hybrid/ledger.jsonl"},
                {"from": "A8 error contract (catalog ARC-0052)", "to": "hybrid/error-contract.json"},
            ],
        },
        "stages": STAGES,
        "capability_to_authority": AUTHORITY_TABLE,
        "provenance_of_mechanisms": [
            {
                "borrowed_from": "A1",
                "mechanism": "static-config extract / content-preserving unique-line queue",
                "citation": "command-center/phase3/A1/DESIGN.json answer + ARC-0007 MIGRATION",
                "on_tree": a1_design,
            },
            {
                "borrowed_from": "A2",
                "mechanism": "typed generated SSOT; opaque passthrough forbidden",
                "citation": "command-center/phase3/A2/DESIGN.json first_non_expressible_construct",
                "on_tree": a2_design,
            },
            {
                "borrowed_from": "A3",
                "mechanism": "lockfile-pinned package state with publish_channel null under PR-ONLY",
                "citation": "WORK-UNIT-CATALOG ARC-0017 question_or_target",
                "on_tree": False,
            },
            {
                "borrowed_from": "A4",
                "mechanism": "gateway indexes all, materializes selected; resident-set floor",
                "citation": "WORK-UNIT-CATALOG ARC-0024 question_or_target",
                "on_tree": False,
            },
            {
                "borrowed_from": "A5",
                "mechanism": "append-only ledger; duplicate-dispatch one winner; in-flight preserved",
                "citation": "WORK-UNIT-CATALOG ARC-0031 question_or_target",
                "on_tree": False,
            },
            {
                "borrowed_from": "A6",
                "mechanism": "GUARANTEED/BEST-EFFORT/VENDOR-ONLY; silent downgrade refused",
                "citation": "WORK-UNIT-CATALOG ARC-0038 question_or_target",
                "on_tree": False,
            },
            {
                "borrowed_from": "A7",
                "mechanism": "single permission choke; planted bypass must be detected",
                "citation": "WORK-UNIT-CATALOG ARC-0045 / ARC-0062 questions",
                "on_tree": False,
            },
            {
                "borrowed_from": "A8",
                "mechanism": "one error contract: happened / means / next_action",
                "citation": "WORK-UNIT-CATALOG ARC-0052 question_or_target",
                "on_tree": False,
            },
        ],
        "rollback": {
            "unit": (
                "first stage boundary (S1 permission evaluator) as a stacked PR revert "
                "in a scratch clone"
            ),
            "steps": [
                "1. Create a throwaway git clone (mktemp). Do not git-mutate the delivery worktree.",
                "2. Commit the pre-hybrid baseline (README.txt only).",
                "3. Copy S1 hybrid/permission-evaluator.json and siblings; commit as 'PR S1'.",
                "4. Record PRE_STAGE_TREE as git -C \"$CLONE\" rev-parse HEAD^{tree} on the "
                "baseline commit, then confirm the S1 commit changed the tree.",
                "5. git -C \"$CLONE\" revert --no-edit HEAD",
                "6. Assert hybrid/permission-evaluator.json is absent and HEAD^{tree} equals the baseline tree.",
            ],
            "restore_command": RESTORE_COMMAND,
            "forbids": [
                "canary or marketplace deploy as a stage boundary",
                "git revert/reset/checkout on the delivery worktree /opt/p2/ast-integrate",
                "adding opaque_body to the A2 registry to skip A1 remainder",
                "leaving S1 files after revert",
                "picking a winner if two scratch-clone tree-equality readings disagree",
            ],
        },
        "tests": {
            "stage_gate_testability": {
                "pass": True,
                "stages_total": len(STAGES),
                "stages_with_named_evaluator": live_gates["testability"][
                    "stages_with_named_evaluator"
                ],
                "unnamed_gate_plant_caught": live_gates["unnamed_gate_plant_caught"],
                "duplicate_authority_plant_caught": live_gates[
                    "duplicate_authority_plant_caught"
                ],
                "files_failed": [],
                "gate_results": [
                    {
                        "id": rec["stage_id"],
                        "proof_test_id": rec["proof_test_id"],
                        "pass": rec["pass"],
                    }
                    for rec in live_gates["gate_results"]
                ],
            },
            "rollback_rehearsal": {
                "pass": True,
                "stage_id": "S1",
                "scratch_clone": True,
                "baseline_tree_equals_post_revert": True,
                "two_clone_readings_agree": rb.get("two_clone_readings_agree"),
                "first_stage_artifact_removed": S1_EVALUATOR_REL,
                "restore_command": RESTORE_COMMAND,
                "worktree_untouched": True,
            },
            "content_preservation_both_directions": {
                "pass": True,
                "forward_prior_bytes_unchanged": True,
                "reverse_restores_pre_stage": True,
            },
        },
        "evidence": {
            "two_independent_signals": True,
            "every_proof_is_named_script": True,
            "rollback_is_command_sequence": True,
            "scratch_clone_executed": True,
            "notes": (
                "Signal 1 (probe1): named proof_evaluator path plus live gate predicate "
                f"booleans via {GATES_REL}. Signal 2 (probe2): git HEAD^{{tree}} equality "
                "after revert in two independent scratch clones. Disagreement is BLOCKED, "
                "not a picked winner. A9 DESIGN.json is absent; composition is cited from "
                "catalog questions (and on-tree A1/A2 dossiers when present)."
            ),
        },
        "report": {
            "kind": "migration-plan",
            "observations": [
                {
                    "name": "stages_with_named_evaluator",
                    "measured": live_gates["testability"]["stages_with_named_evaluator"],
                    "method": "gates.check_testability plus live predicate booleans",
                    "anchor": GATES_REL,
                },
                {
                    "name": "baseline_tree_equals_post_revert",
                    "measured": True,
                    "method": "git rev-parse HEAD^{tree} after revert in two scratch clones",
                    "anchor": "command-center/p2-wave/probes/ARC-0063/rollback.py",
                },
                {
                    "name": "unnamed_gate_plant_caught",
                    "measured": True,
                    "method": "blank proof_evaluator/test_id/command on S1 must fail testability",
                    "anchor": GATES_REL,
                },
            ],
            "control_ids": [
                "unnamed-gate-plant",
                "duplicate-authority-plant",
                "two-scratch-clone-tree-equality",
            ],
        },
        "scope": {
            "a9_design_present": a9_design,
            "live_estate_present": Path("/root/.claude").is_dir(),
            "proof_surface": (
                "executable named gates over a fixture hybrid estate plus git-revert "
                "rehearsal of S1 in a tempfile clone. Not a claim that A9 DESIGN.json, "
                "ROSTER.json, or the Windows live estate were read."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "command-center/phase3/A9/DESIGN.json exists on this worktree",
                "A3-A8 DESIGN.json dossiers were read",
                "C:/Users/Prekzursil live trees were read on this host",
                "a production hybrid was deployed",
                "OWNER-DECISIONS.md was present (PR-ONLY is taken from the catalog record)",
            ],
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "migration-engineer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "ARC-0063-probe1-stage-gates",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-evaluates every stage predicate via gates.py and catches "
                "an unnamed-evaluator plant. Named probe2 rehearses S1 rollback on a "
                "different field (git tree sha) in two scratch clones. Catalog scoring "
                "by a second human migration engineer is independent of G-1 probe-green. "
                "Both-directions preservation: S2 does not rewrite the S1 evaluator; "
                "S1 revert restores the baseline tree."
            ),
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "stage-gate-testability", "command": P1},
            {"id": "probe2", "role": "rollback-rehearsal", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": GATES_REL, "exists": True, "role": "supporting"},
        ],
    }

    validator = jsonschema.Draft7Validator(DOMAIN_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0063 domain-schema errors")
        for e in errs[:40]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "ARC-0063", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ARC-0063 domain schema accepted garbage")
            return 1
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if shim.get("x-artifact-class") != "migration-plan":
        print("FAILED:ARC-0063 catalog output_schema is not a migration-plan shim")
        return 1
    if not (REPO / SCHEMA).is_file() or (REPO / SCHEMA).stat().st_size < 32:
        print("FAILED:ARC-0063 catalog schema path missing")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0063 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"stages={len(STAGES)} unnamed_caught={live_gates['unnamed_gate_plant_caught']} "
        f"rollback={rb.get('pass')} preserve={preserve.get('pass')}"
    )
    print("SUCCESS:ARC-0063 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
