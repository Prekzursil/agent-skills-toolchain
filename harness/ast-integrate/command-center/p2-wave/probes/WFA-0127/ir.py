"""WorkflowIR document for workflow-scout. Not a second runtime."""
from __future__ import annotations

from typing import Any

from constants import (
    ARTIFACT_REL,
    DEFAULT_SOURCE_CLASSES,
    SCHEMA_REL,
    SENTINEL,
    STAGE_IDS,
    UNIT_ID,
)

CATALOG_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:98560"


def _node(node_id: str, kind: str, title: str, body: str, **extra: Any) -> dict[str, Any]:
    row = {
        "id": node_id,
        "kind": kind,
        "title": title,
        "body": body,
        "source_anchor": CATALOG_ANCHOR,
    }
    row.update(extra)
    return row


def build_ir() -> dict[str, Any]:
    stages = [
        _node(
            "ingest-goal",
            "stage",
            "Ingest typed goal",
            "Accept goal text, declared mechanisms, licence_allow, allow_build, source_classes.",
        ),
        _node(
            "fan-out-source-classes",
            "stage",
            "Fan-out source classes",
            "Search registry, repository, marketplace, public-docs, papers, and the live WFA-0019 fixture class. A class with zero hits is a recorded miss, not a skip.",
            fan_out=True,
            barrier="search-hits",
        ),
        _node(
            "search-hits",
            "stage",
            "Collect hits",
            "Enumerate candidate records per class. No network. Fixture archaeology surface only on this worktree.",
        ),
        _node(
            "verify-provenance",
            "stage",
            "Verify provenance",
            "Dereference provenance.src as file:line. The cited line must contain every claimed mechanism id. exists-only is insufficient.",
        ),
        _node(
            "verify-licence",
            "stage",
            "Verify licence",
            "UNKNOWN licence => UNKNOWN-NEEDS-PROBE, never ranked. Allow-list excludes copyleft when the goal is permissive-only.",
        ),
        _node(
            "decompose-mechanisms",
            "stage",
            "Decompose mechanisms",
            "Score coverage (goal mechanisms present in the candidate) and Jaccard. Rank by independent evidence, not hit frequency.",
        ),
        _node(
            "rank-dispositions",
            "stage",
            "Rank adopt/adapt/compose",
            "ADOPT at coverage 1.0, ADAPT at coverage >= 0.5, COMPOSE when two partials union to the goal. Do not pad ranked with below-threshold decoys.",
        ),
        _node(
            "anti-rebuild-gate",
            "gate",
            "Anti-rebuild before BUILD",
            "BUILD is considered only if allow_build. The gate cites a verified existing candidate whose coverage of the goal is >= 0.5 and blocks BUILD. A novel goal with no close existing candidate may PASS.",
            fires_before="BUILD",
        ),
        _node(
            "characterise-gap",
            "stage",
            "Characterise gap",
            "If ranked is empty, list missing mechanisms, classes searched, and nearest below-threshold id. Never invent a hit.",
        ),
        _node(
            "emit-result",
            "stage",
            "Emit result",
            "Return ranked (each with provenance_anchor and licence_class), unknown_needs_probe, gap, anti_rebuild, optional BUILD.",
        ),
    ]
    roles = [
        _node("scout", "role", "Scout", "Walks stages; does not self-certify PASS."),
        _node(
            "provenance-verifier",
            "role",
            "Provenance verifier",
            "Content dereference of file:line.",
        ),
        _node(
            "licence-verifier",
            "role",
            "Licence verifier",
            "Allow-list plus most-restrictive join on COMPOSE.",
        ),
        _node(
            "anti-rebuild-gate",
            "role",
            "Anti-rebuild gate",
            "Stand-in for absent WFA-0120 artifact; same fail-closed citation contract.",
        ),
    ]
    return {
        "ir_kind": "WorkflowIR",
        "ir_version": "wfa-0127.1",
        "id": "meta.workflow-scout",
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "completion_sentinel": SENTINEL,
        "title": "workflow-scout executable meta-workflow over the archaeology surface",
        "source_anchor": CATALOG_ANCHOR,
        "output_path": ARTIFACT_REL,
        "output_schema": SCHEMA_REL,
        "not_a_runtime": True,
        "stopping_expression": (
            "all declared source classes searched AND (ranked non-empty OR gap characterised)"
        ),
        "tool_policy": _node(
            "tool-policy",
            "policy",
            "Tool policy",
            "read fixtures and WFA-0019 corpus only; no network; no git write.",
            allowed=["read-registry", "deref-anchor", "licence-lookup"],
            denied=["network", "git-write", "catalog-manifest-write"],
        ),
        "roles": roles,
        "stages": stages,
        "stage_ids": list(STAGE_IDS),
        "source_classes": list(DEFAULT_SOURCE_CLASSES),
        "gates": [
            _node(
                "anti-rebuild",
                "gate",
                "Anti-rebuild",
                "Must fire before any BUILD recommendation. Citation is the existing candidate id.",
                source_anchor="command-center/WORK-UNIT-CATALOG.json:98207",
            )
        ],
        "retries": _node(
            "retries",
            "retry",
            "Two strikes then pivot",
            "After the second identical fingerprint, enumerate two alternatives; do not rebuild ADV.",
        ),
        "resume": _node(
            "resume",
            "resume",
            "Resume checkpoints",
            "Per-source-class hit lists are the resume unit.",
        ),
        "human_checkpoints": [],
        "lossy_field_ledger": [],
        "lineage": {
            "depends_on": ["WFA-0084", "WFA-0060", "WFA-0120"],
            "dependency_status": {
                "WFA-0084": (
                    "ABSENT on this worktree (no command-center/wfa/WFA-0084-registry-query-interface.json). "
                    "Scout binds to a typed fixture query surface with the same class/licence/mechanism axes."
                ),
                "WFA-0060": (
                    "ABSENT on this worktree. Ranking uses coverage of goal mechanisms plus independent "
                    "provenance, not hit frequency."
                ),
                "WFA-0120": (
                    "ABSENT on this worktree. Local anti-rebuild gate implements the named contract: "
                    "reject a planted rebuild and cite the existing id; pass a novel BUILD."
                ),
            },
            "implementation_binding": {
                "runner": "command-center/p2-wave/probes/WFA-0127/scout.py",
                "note": "Binding is outside the IR. The IR has no execution entrypoint.",
            },
        },
        "controls": {
            "held_out_known_answer": {
                "goal": "fixtures/goals/heldout.json",
                "planted_id": "wf-heldout-kanban-drain",
                "hidden_from_goal_text": True,
            },
            "honest_empty": {
                "goal": "fixtures/goals/empty.json",
                "mechanism": "quantum.teleport.workflow",
            },
            "anti_rebuild": {
                "goal": "fixtures/goals/rebuild.json",
                "cited_id": "wf-superior-review",
            },
            "anti_rebuild_pass": {
                "goal": "fixtures/goals/novel_build.json",
            },
        },
        "did_not_do": [
            "Did not consume a live 284-row Prompt One registry (absent on this Linux worktree).",
            "Did not author WFA-0001 schema pack or WFA-0044 IR-spec.",
            "Did not implement workflow-forge (WFA-0128 / WFA-0144).",
            "Did not search a live network marketplace or paper index; papers class is a recorded empty miss.",
            "Did not run tools/command-center/unit_manifest.py --write.",
            "Did not claim cloud ok=true as delivery.",
        ],
        "evidence_requirement": {
            "A": "end-to-end scout run on goal-e2e-drain returns ranked hits each with provenance_anchor and licence_class",
            "B": "held-out goal whose known id is wf-heldout-kanban-drain must appear in top ranked results without being named in the goal",
        },
    }
