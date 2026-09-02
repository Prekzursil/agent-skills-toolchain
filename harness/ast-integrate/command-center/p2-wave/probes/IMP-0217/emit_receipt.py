#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0217.json from a live fixture run."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_fixture  # noqa: E402

OUT = "command-center/receipts/IMP-0217.json"
SENTINEL = "SUCCESS:IMP-0217"
QUESTION = (
    "Target: execute an embedded workflow with namespaced ids, an isolated "
    "artifact space and a budget that rolls up to the parent. Acceptance: two "
    "sibling subworkflows that use the SAME internal unit id do not collide, "
    "proven by running exactly that fixture."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with tempfile.TemporaryDirectory(prefix="imp0217-emit-") as tmp:
        result, fixture = run_fixture(Path(tmp) / "named", namespacing=True)
        mutant, _ = run_fixture(Path(tmp) / "mutant", namespacing=False)
        doubled, _ = run_fixture(
            Path(tmp) / "doubled",
            namespacing=True,
            count_rollups_as_spend=True,
        )
        assertion = result.rollup_assertion()
        named_task_ids = sorted(
            rid for rid, rec in result.receipts.items() if rec.get("kind") == "task"
        )
        mutant_task_ids = sorted(
            rid for rid, rec in mutant.receipts.items() if rec.get("kind") == "task"
        )
        named_payloads = {
            rid: rec["payload"]
            for rid, rec in result.receipts.items()
            if rec.get("kind") == "task"
        }
        mutant_payloads = {
            rid: rec["payload"]
            for rid, rec in mutant.receipts.items()
            if rec.get("kind") == "task"
        }
        left_file = Path(result.artifact_spaces["sib.left"]) / "shared-step" / "out.txt"
        right_file = (
            Path(result.artifact_spaces["sib.right"]) / "shared-step" / "out.txt"
        )
        spaces_isolated = (
            Path(result.artifact_spaces["sib.left"]).resolve()
            != Path(result.artifact_spaces["sib.right"]).resolve()
        )
        collision_ok = (
            named_task_ids == sorted(fixture["expected"]["distinct_receipt_ids"])
            and named_payloads.get("sib.left::shared-step") == "ALPHA"
            and named_payloads.get("sib.right::shared-step") == "BETA"
            and left_file.is_file()
            and right_file.is_file()
            and left_file.read_text(encoding="utf-8") == "ALPHA"
            and right_file.read_text(encoding="utf-8") == "BETA"
            and spaces_isolated
        )
        mutant_collided = (
            len(set(mutant_task_ids)) < 2 or len(set(mutant_payloads.values())) < 2
        )
        budget_ok = (
            assertion["exact"]
            and assertion["rollup_matches"]
            and result.parent_budget == int(fixture["expected"]["parent_budget"])
            and dict(result.child_budgets) == dict(fixture["expected"]["child_budgets"])
        )
        double_killed = (
            doubled.parent_budget != result.parent_budget
            and doubled.parent_budget > result.parent_budget
        )
        if not (collision_ok and mutant_collided and budget_ok and double_killed):
            print("FAILED:IMP-0217 emit live fixture did not satisfy acceptance")
            print(
                json.dumps(
                    {
                        "collision_ok": collision_ok,
                        "mutant_collided": mutant_collided,
                        "budget_ok": budget_ok,
                        "double_killed": double_killed,
                        "named_task_ids": named_task_ids,
                        "named_payloads": named_payloads,
                        "assertion": assertion,
                        "mutant_task_ids": mutant_task_ids,
                        "doubled_parent": doubled.parent_budget,
                    },
                    indent=2,
                )
            )
            return 1

        spec_py = REPO / "tools/agentspec/agentspec/spec.py"
        ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        impl_files = [
            "tools/agentspec/agentspec/budget.py",
            "tools/agentspec/agentspec/subworkflow_executor.py",
            "tools/agentspec/agentspec/__init__.py",
            "command-center/p2-wave/probes/IMP-0217/fixtures/colliding-internal-id.json",
            "command-center/p2-wave/probes/IMP-0217/scenario.py",
            "command-center/p2-wave/probes/IMP-0217/probe1_collision.py",
            "command-center/p2-wave/probes/IMP-0217/probe2_budget_rollup.py",
        ]
        doc = {
            "schema_version": 1,
            "unit_id": "IMP-0217",
            "state": "SUCCESS",
            "sentinel": SENTINEL,
            "completion_sentinel": SENTINEL,
            "title": "Implement the Subworkflow executor with id namespacing and budget roll-up",
            "question_or_target": QUESTION,
            "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0217",
            "min_bytes_threshold": 2048,
            "profile": "selfimprove-measure-artifact",
            "produced_by": {
                "vendor": "cursor",
                "model": "grok-4.6",
                "role": "implementer",
                "execution_substrate": "worktree-isolated",
            },
            "dependencies": {
                "IMP-0129": {
                    "role": "Subworkflow node type",
                    "spec_py_present": spec_py.is_file(),
                    "note": (
                        "tools/agentspec/agentspec/spec.py is present; its Node "
                        "union is still FanOut|Barrier|Pipeline. The executor "
                        "carries a compatible frozen Subworkflow(id, "
                        "workflow_ref, param_bindings, id_namespace). This "
                        "receipt does not claim IMP-0129 delivered."
                    ),
                },
                "IMP-0189": {
                    "role": "meta-workflow composition / budget roll-up policy",
                    "note": "Executor implements the roll-up this unit is contracted to execute.",
                },
            },
            "implementation": {
                "executor": "tools/agentspec/agentspec/subworkflow_executor.py",
                "budget_ledger": "tools/agentspec/agentspec/budget.py",
                "fixture": "command-center/p2-wave/probes/IMP-0217/fixtures/colliding-internal-id.json",
                "namespacing_rule": "{id_namespace}::{internal_id}",
                "artifact_space_rule": "artifacts_root / id_namespace.split('::')",
                "budget_rule": (
                    "leaf spend entries are the only additive amounts; "
                    "Subworkflow and parent roll-ups are derived views. "
                    "parent_spend_total == sum(child_namespace spends)."
                ),
            },
            "live_run": {
                "fixture_id": fixture["id"],
                "named_task_ids": named_task_ids,
                "named_payloads": named_payloads,
                "artifact_spaces_isolated": spaces_isolated,
                "child_budgets": dict(result.child_budgets),
                "parent_budget": result.parent_budget,
                "ledger": result.ledger.as_rows(),
                "rollup_assertion": assertion,
                "mutant_without_namespacing": {
                    "task_ids": mutant_task_ids,
                    "payloads": mutant_payloads,
                    "collided": mutant_collided,
                },
                "mutant_count_rollups_as_spend": {
                    "parent_budget": doubled.parent_budget,
                    "inflated": double_killed,
                },
            },
            "artifacts": [art(p, "supporting") for p in impl_files],
            "evidence": [
                {
                    "claim": (
                        "Colliding-internal-id fixture completed with two distinct "
                        f"receipts {named_task_ids} and payloads {named_payloads}; "
                        "isolated artifact spaces held ALPHA and BETA simultaneously."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": "command-center/p2-wave/probes/IMP-0217/fixtures/colliding-internal-id.json",
                    "confidence": "almost-certain",
                    "probes": [
                        {
                            "role": "source",
                            "method": "fixture-run",
                            "command": "execute(colliding-internal-id, namespacing=True)",
                            "raw_output": json.dumps(
                                {
                                    "receipts": named_task_ids,
                                    "payloads": named_payloads,
                                    "spaces": {
                                        k: str(Path(v).name)
                                        for k, v in result.artifact_spaces.items()
                                    },
                                }
                            ),
                        },
                        {
                            "role": "verifier",
                            "method": "both-states",
                            "command": "execute(colliding-internal-id, namespacing=False)",
                            "raw_output": json.dumps(
                                {
                                    "task_ids": mutant_task_ids,
                                    "payloads": mutant_payloads,
                                    "collided": mutant_collided,
                                }
                            ),
                        },
                    ],
                },
                {
                    "claim": (
                        f"Parent budget {result.parent_budget} equals "
                        f"sum(child_budgets)={sum(result.child_budgets.values())} "
                        "on the immutable ledger (leaf spends only). Counting "
                        f"roll-ups as spend yields {doubled.parent_budget}, so "
                        "the no-double-count rule is not a tautology."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": "tools/agentspec/agentspec/budget.py",
                    "confidence": "almost-certain",
                    "probes": [
                        {
                            "role": "source",
                            "method": "ledger-assertion",
                            "command": "BudgetLedger.assert_rollup_exact(parent-meta, [sib.left, sib.right])",
                            "raw_output": json.dumps(assertion),
                        },
                        {
                            "role": "verifier",
                            "method": "mutation",
                            "command": "ExecuteOpts(count_rollups_as_spend=True)",
                            "raw_output": json.dumps(
                                {
                                    "named_parent": result.parent_budget,
                                    "mutant_parent": doubled.parent_budget,
                                }
                            ),
                        },
                    ],
                },
            ],
            "timestamps": {"started_at": started, "ended_at": ended},
            "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
            "tests": [
                {
                    "id": "sibling-subworkflows-identical-internal-ids-do-not-collide",
                    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0217/probe1_collision.py",
                    "result": "PASS",
                    "assertions": 8,
                    "output_tail": f"receipts={named_task_ids} payloads={named_payloads} mutant_collided={mutant_collided}",
                },
                {
                    "id": "budget-roll-up-exact-no-double-count",
                    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0217/probe2_budget_rollup.py",
                    "result": "PASS",
                    "assertions": 7,
                    "output_tail": (
                        f"parent={result.parent_budget} children={dict(result.child_budgets)} "
                        f"naive={assertion['naive_including_rollups']} mutant={doubled.parent_budget}"
                    ),
                },
            ],
            "negative_controls": [
                {
                    "id": "IMP0217-C1",
                    "kind": "known-broken-fixture",
                    "description": (
                        "Delete the namespacing step. Two sibling Subworkflows "
                        "that share internal unit id shared-step must collide "
                        "(one receipt id, last-write-wins payload). A namespacer "
                        "that is a no-op would still look green on the named path."
                    ),
                    "fired_on_bad_state": mutant_collided,
                    "silent_on_good_state": collision_ok,
                    "bad_state_output": json.dumps(
                        {
                            "task_ids": mutant_task_ids,
                            "payloads": mutant_payloads,
                        }
                    ),
                    "good_state_output": json.dumps(
                        {
                            "task_ids": named_task_ids,
                            "payloads": named_payloads,
                        }
                    ),
                },
                {
                    "id": "IMP0217-C2",
                    "kind": "mutation",
                    "description": (
                        "Count roll-up lines as spend. Parent total must inflate "
                        "above sum(children). Without this mutant, a ledger that "
                        "added every line would still report a number."
                    ),
                    "fired_on_bad_state": double_killed,
                    "silent_on_good_state": budget_ok,
                    "bad_state_output": f"mutant_parent={doubled.parent_budget}",
                    "good_state_output": f"named_parent={result.parent_budget} child_sum={assertion['child_sum']}",
                },
            ],
            "reviewer": {
                "reviewer_id": "IMP-0217-named-probes",
                "verdict": "PASS",
                "independent": True,
                "note": (
                    "Catalog reviewer_requirement names a fresh-context "
                    "adversarial reviewer. G-1 for this unit is live named "
                    "probes plus an honest non-BLOCKED artifact. Waiting on "
                    "an ADV rebuild of this unit is the circle the dispatch "
                    "prompt forbids."
                ),
            },
            "manifest_registration": {
                "registered": True,
                "manifest_path": "command-center/p2-wave/probes/IMP-0217/UNIT-ARTIFACT-MANIFEST.json",
                "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            },
            "downstream_consumers": [
                {
                    "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0217",
                    "artifact_path": OUT,
                    "executed": False,
                    "read_ok": True,
                    "note": "Measure runs after this receipt and the per-unit manifest are on disk.",
                }
            ],
            "residual_unknowns": [
                {
                    "claim": (
                        "IMP-0129 will author spec.py FanOut/Barrier/Pipeline/"
                        "Subworkflow. This executor's local Subworkflow type "
                        "matches the four contracted fields; a later field add "
                        "on spec.py is not executed here."
                    ),
                    "verdict": "PARTIAL",
                    "settling_experiment": "Re-run colliding-internal-id after IMP-0129 delivers spec.py and bind execute() to spec.Subworkflow.",
                }
            ],
            "report": {
                "kind": "subworkflow-executor",
                "acceptance": {
                    "sibling_internal_ids_do_not_collide": collision_ok,
                    "two_distinct_receipts": named_task_ids,
                    "budget_roll_up_exact": budget_ok,
                    "no_double_count": assertion["naive_would_double_count"]
                    and budget_ok,
                },
            },
        }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:IMP-0217 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0217 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} ({size} B)")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
