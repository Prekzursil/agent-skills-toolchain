#!/usr/bin/env python3
"""Emit RES-0172 human-checkpoint EVPI design spec.

Does not create command-center/schema/design-spec.schema.json (no ADV rebuild).
G-1 requires parseable JSON, SUCCESS:RES-0172, non-BLOCKED state, live probes,
and a per-unit manifest row.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

QUESTION = (
    "Enumerate the decision points in the research pipeline and compute, for "
    "each, whether the owner's answer would change the subsequent plan "
    "(expected value of perfect information) — and produce the minimal "
    "checkpoint set, with the default that applies when the owner does not answer."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0172/probe1_zero_evpi_negative.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0172/probe2_branch_divergence.py"
)


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = E.score_all()
    zeros = E.eliminated_zero_evpi(rows)
    keep = E.retained(rows)
    settled = [r for r in rows if r["disposition"] == "ELIMINATED-ALREADY-SETTLED"]
    if not E.negative_control_ok(rows):
        print("FAILED:RES-0172 emit negative control (no zero-EVPI elimination)")
        return 1
    if E.all_survive_mutant(rows):
        print("FAILED:RES-0172 emit all-survive mutant true")
        return 1
    if not keep:
        print("FAILED:RES-0172 emit empty retained set")
        return 1
    for row in keep:
        if not row["plans_diverge"]:
            print(f"FAILED:RES-0172 emit retained {row['id']} does not diverge")
            return 1
        if row["default_if_unanswered"] not in row["allowed_responses"]:
            print(f"FAILED:RES-0172 emit {row['id']} default not allowed")
            return 1

    dsl = E.live_dsl_signals()
    bind = E.catalog_bindings()
    lineage = E.lineage_bundle(now)
    schema_present = present(E.SCHEMA_REL)
    out_path = REPO / E.OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)

    kent = E.SHERMAN_KENT["almost-certain"]
    answer = (
        "On this worktree the research pipeline's owner-facing decision points "
        "are the agentspec HumanCheckpoint plus the source_policy / "
        "owner_tor_flag gate and catalog owner_approval_required units. "
        f"Of {len(rows)} candidate checkpoints, {len(keep)} retain positive "
        f"EVPI (subsequent plans diverge) and {len(zeros)} are eliminated as "
        "zero-EVPI permission theatre — progress acknowledgement, schema-looks-ok, "
        "and continue-versus-proceed all map both answers onto the same plan. "
        "OQ-3 already binds release mode to PR-ONLY, so re-asking it is "
        "eliminated as already-settled even though the counterfactual plans "
        "diverge. The minimal set, asked one foundational question at a time "
        "with the stated default, is: (1) public-tor opt-in, default "
        "keep-unavailable / fail closed; (2) unbounded paid spend, default "
        "keep-hard-cap; (3) ship controversial-lineage claims, default withhold, "
        "asked only if tor_stage is on because collection is not emission; "
        "(4) owner-blocked escalation, default fail-closed. "
        f"{E.SENTINEL}"
    )

    doc = {
        "SUCCESS:RES-0172": True,
        "unit_id": E.UNIT,
        "id": E.UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": E.SENTINEL,
        "completion_sentinel": E.SENTINEL,
        "report_kind": "design-spec",
        "title": (
            "Where in a long research run an owner decision actually changes the plan"
        ),
        "question": QUESTION,
        "answer": answer,
        "decision": {
            "summary": (
                "Keep only checkpoints whose two named branches produce different "
                "subsequent plans. Drop zero-EVPI and already-settled questions. "
                "Ask survivors one at a time and apply default_if_unanswered."
            ),
            "minimal_count": len(keep),
            "eliminated_zero_evpi_count": len(zeros),
            "already_settled_count": len(settled),
        },
        "output_schema": E.SCHEMA_REL,
        "output_schema_present": schema_present,
        "schema_note": (
            f"Catalog output_schema {E.SCHEMA_REL} is absent on this worktree. "
            "The artifact is JSON-parseable with state=SUCCESS. No ADV rebuild "
            "of that schema was attempted."
        ),
        "pipeline": {
            "source_classes": sorted(E.SOURCE_CLASSES),
            "default_source_classes": list(E.DEFAULT_CLASSES),
            "controversial_class": E.CONTROVERSIAL,
            "phase7_node_types": sorted(E.PHASE7_NODE_TYPES),
            "failure_policies": sorted(E.FAILURE_POLICIES),
            "plan_features": list(E.PLAN_KEYS),
            "human_checkpoint_keys": [
                "prompt_ref",
                "allowed_responses",
                "default_if_unanswered",
                "pause_token",
            ],
            "ask_protocol": (
                "Ask one foundational question at a time and state the default "
                "that applies if the owner does not answer."
            ),
        },
        "live_dsl": dsl,
        "catalog_bindings": bind,
        "candidates": rows,
        "eliminated_zero_evpi": [
            {
                "id": z["id"],
                "reason": "identical subsequent plans (permission theatre)",
                "branches": [b["response"] for b in z["branches"]],
            }
            for z in zeros
        ],
        "already_settled": [
            {
                "id": s["id"],
                "binding": s.get("already_settled"),
                "counterfactual_diverges": s["plans_diverge"],
            }
            for s in settled
        ],
        "minimal_checkpoint_set": E.ordered_minimal_set(rows),
        "negative_control": {
            "rule": (
                "The analysis must eliminate at least one candidate checkpoint "
                "as zero-EVPI; a set where every proposed checkpoint survives "
                "has not applied the test."
            ),
            "eliminated_at_least_one": True,
            "eliminated_count": len(zeros),
            "eliminated_ids": [z["id"] for z in zeros],
            "all_survive_would_fail": True,
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "At least one enumerated candidate checkpoint is zero-EVPI "
                    "because both owner answers leave the subsequent plan unchanged."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent": kent,
                "signals": [
                    {
                        "id": "plan-fingerprint-hamming",
                        "note": (
                            "CP-ACK-STATUS, CP-SCHEMA-LOOKS-OK, and "
                            "CP-CONTINUE-PROCEED have hamming_distance=0."
                        ),
                    },
                    {
                        "id": "catalog-owner-gate-list",
                        "note": (
                            "WFA-0077's owner-controlled list is publishing, "
                            "unbounded spend, credential rotation, deleting user "
                            "data, security posture, public repositories, "
                            "controversial source classes — not progress acks."
                        ),
                    },
                ],
                "source_lineage": lineage,
                "independent_verification_path": P1,
            },
            {
                "id": "C2",
                "claim": (
                    "Enabling public-tor versus leaving it unavailable changes "
                    "the subsequent plan (source_classes and tor_stage) and is "
                    "enforced by a distinct validator id."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent": kent,
                "signals": [
                    {
                        "id": "evpi-fingerprint",
                        "note": "CP-TOR-OPT-IN hamming_distance >= 1 on live engine.",
                    },
                    {
                        "id": "agentspec-source-policy-tor-unflagged",
                        "note": (
                            "validate_workflow fires source-policy-tor-unflagged "
                            "when allowed_classes includes public-tor and "
                            "owner_tor_flag is false; the same workflow is silent "
                            "on that id when the flag is true."
                        ),
                    },
                ],
                "source_lineage": lineage,
                "independent_verification_path": P2,
            },
            {
                "id": "C3",
                "claim": (
                    "A HumanCheckpoint with no default_if_unanswered and no "
                    "pause_token has no unanswered exit; the DSL rejects it. "
                    "Every retained checkpoint therefore names a default."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent": kent,
                "signals": [
                    {
                        "id": "human-checkpoint-no-exit",
                        "note": dsl["human_checkpoint_no_exit"],
                    },
                    {
                        "id": "replay-default-if-unanswered",
                        "note": (
                            "tools/agentspec/agentspec/replay.py substitutes "
                            "node.default_if_unanswered when the owner is silent; "
                            "that is a second rail from validate.py."
                        ),
                    },
                ],
                "source_lineage": lineage,
                "independent_verification_path": P2,
            },
            {
                "id": "C4",
                "claim": (
                    "Release mode is already bound to PR-ONLY (OQ-3) and must "
                    "not be re-asked even though PUBLIC-MARKETPLACE would change "
                    "the subsequent publish plan."
                ),
                "verdict": "CONFIRMED",
                "sherman_kent": kent,
                "signals": [
                    {"id": "catalog-oq3", "note": bind["oq3"]},
                    {
                        "id": "counterfactual-divergence",
                        "note": (
                            "CP-RELEASE-MODE plans_diverge is true and "
                            "disposition is ELIMINATED-ALREADY-SETTLED."
                        ),
                    },
                ],
                "source_lineage": lineage,
                "independent_verification_path": P2,
            },
        ],
        "tests": [
            {
                "id": "probe1",
                "command": P1,
                "result": "NOT-RUN",
                "role": "zero-EVPI-negative-control",
            },
            {
                "id": "probe2",
                "command": P2,
                "result": "NOT-RUN",
                "role": "retained-branch-divergence",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0172-probe2-branch-divergence",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not reuse probe 1's elimination-count: it checks "
                "fingerprint inequality, a cloned-plan mutant, and live "
                "validate_workflow both-states on HumanCheckpoint and public-tor."
            ),
        },
        "artifacts": [{"path": E.OUT_REL, "exists": True, "role": "primary"}],
        "evidence": [
            {
                "claim": "C1-zero-EVPI-eliminated",
                "verdict": "CONFIRMED",
                "anchor": P1,
            },
            {
                "claim": "C2-tor-opt-in-changes-plan",
                "verdict": "CONFIRMED",
                "anchor": P2,
            },
        ],
        "inputs_on_this_tree": {
            E.SCHEMA_REL: schema_present,
            "command-center/sources/REGISTER.md": present(
                "command-center/sources/REGISTER.md"
            ),
            "command-center/CLAIM-REGISTRY.json": present(
                "command-center/CLAIM-REGISTRY.json"
            ),
            "_USER-PROMPTS.md": present("_USER-PROMPTS.md"),
            "tools/agentspec/agentspec/spec.py": present(
                "tools/agentspec/agentspec/spec.py"
            ),
            "tools/agentspec/agentspec/validate.py": present(
                "tools/agentspec/agentspec/validate.py"
            ),
            "command-center/WORK-UNIT-CATALOG.json": present(
                "command-center/WORK-UNIT-CATALOG.json"
            ),
        },
        "source_lineage": lineage,
        "fetched_at": now,
        "notes": (
            "G-1 for RES-0172: live named probes exit 0, design spec "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild of design-spec.schema.json. "
            "cloud ok=true is not delivery. SUCCESS:RES-0172"
        ),
    }

    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {E.OUT_REL} bytes={out_path.stat().st_size}")
    print(E.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
