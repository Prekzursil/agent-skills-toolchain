"""Catalog families D1-D20 and the on-disk postcondition each matched case asserts.

09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent on this worktree. Family *ids* D1-D20
are the catalog's named set. Labels are IR/taxonomy stand-ins from WFA-0044's
required constructs and WFA-0035's required library categories — not a
transcription of the missing library. A later library drop can relabel without
changing ids.
"""
from __future__ import annotations

from typing import Any

# Packaged-artifact-smoke floor: existence + min size + parse + content.
MIN_BYTES = 96

# Each spec: family_id, label, construct (why this family has a distinct oracle),
# gold payload (merged under envelope), extra JSON-pointer checks.
FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "family_id": "D1",
        "label": "ir-stages",
        "construct": "ordered typed stages with source anchors",
        "gold": {
            "stages": [
                {
                    "id": "s1",
                    "type": "task",
                    "source_anchor": "catalog:WFA-0044#stages",
                }
            ]
        },
        "checks": (
            ("stages", "nonempty_list"),
            ("stages.0.id", "nonempty_str"),
            ("stages.0.type", "eq", "task"),
            ("stages.0.source_anchor", "nonempty_str"),
        ),
    },
    {
        "family_id": "D2",
        "label": "ir-roles",
        "construct": "named roles bound to source anchors",
        "gold": {
            "roles": [
                {"id": "extractor", "source_anchor": "catalog:WFA-0044#roles"}
            ]
        },
        "checks": (
            ("roles", "nonempty_list"),
            ("roles.0.id", "eq", "extractor"),
            ("roles.0.source_anchor", "nonempty_str"),
        ),
    },
    {
        "family_id": "D3",
        "label": "ir-gates",
        "construct": "predicate gates that can refuse",
        "gold": {
            "gates": [
                {
                    "id": "g1",
                    "predicate": "artifact.exists AND artifact.min_bytes",
                    "source_anchor": "catalog:WFA-0044#gates",
                }
            ]
        },
        "checks": (
            ("gates", "nonempty_list"),
            ("gates.0.predicate", "nonempty_str"),
            ("gates.0.predicate", "min_len", 8),
        ),
    },
    {
        "family_id": "D4",
        "label": "ir-tool-policy",
        "construct": "allow/deny tool policy on disk",
        "gold": {
            "tool_policy": {
                "allow": ["Read", "Grep"],
                "deny": ["Bash(network)"],
            }
        },
        "checks": (
            ("tool_policy.allow", "nonempty_list"),
            ("tool_policy.deny", "nonempty_list"),
            ("tool_policy.deny.0", "eq", "Bash(network)"),
        ),
    },
    {
        "family_id": "D5",
        "label": "ir-fan-out",
        "construct": "fan-out degree recorded as a number",
        "gold": {"fan_out": {"degree": 3, "kind": "map"}},
        "checks": (
            ("fan_out.degree", "gte", 2),
            ("fan_out.kind", "eq", "map"),
        ),
    },
    {
        "family_id": "D6",
        "label": "ir-barrier",
        "construct": "join barrier over waiters",
        "gold": {"barrier": {"join": "all", "waiters": 3}},
        "checks": (
            ("barrier.join", "in_set", ("all", "any")),
            ("barrier.waiters", "gte", 2),
        ),
    },
    {
        "family_id": "D7",
        "label": "ir-loop-convergence",
        "construct": "loop with a named convergence rule",
        "gold": {
            "loop": {
                "max_iters": 4,
                "convergence": "delta-below-floor",
            }
        },
        "checks": (
            ("loop.max_iters", "gte", 1),
            ("loop.convergence", "nonempty_str"),
        ),
    },
    {
        "family_id": "D8",
        "label": "ir-human-checkpoint",
        "construct": "human checkpoint with a resume token",
        "gold": {
            "checkpoint": {
                "human": True,
                "resume_token": "ckpt-d8-1",
            }
        },
        "checks": (
            ("checkpoint.human", "is_true"),
            ("checkpoint.resume_token", "nonempty_str"),
        ),
    },
    {
        "family_id": "D9",
        "label": "ir-retry",
        "construct": "typed retry budget",
        "gold": {"retry": {"max": 2, "on": ["timeout", "schema-invalid"]}},
        "checks": (
            ("retry.max", "gte", 1),
            ("retry.on", "nonempty_list"),
        ),
    },
    {
        "family_id": "D10",
        "label": "ir-resume",
        "construct": "resume cursor naming a stage",
        "gold": {"resume": {"cursor": "after-s1", "from_stage": "s1"}},
        "checks": (
            ("resume.cursor", "nonempty_str"),
            ("resume.from_stage", "nonempty_str"),
        ),
    },
    {
        "family_id": "D11",
        "label": "ir-stop-expression",
        "construct": "evaluable stopping expression",
        "gold": {
            "stop": {
                "expression": "max_stages<=8 AND NOT error",
                "evaluable": True,
            }
        },
        "checks": (
            ("stop.expression", "nonempty_str"),
            ("stop.evaluable", "is_true"),
        ),
    },
    {
        "family_id": "D12",
        "label": "ir-lineage",
        "construct": "lineage with a source anchor (IR node without one is invalid)",
        "gold": {
            "lineage": {
                "source_anchor": "catalog:WFA-0044#lineage",
                "parent_ids": ["WFA-0044", "WFA-0035"],
            }
        },
        "checks": (
            ("lineage.source_anchor", "nonempty_str"),
            ("lineage.parent_ids", "nonempty_list"),
        ),
    },
    {
        "family_id": "D13",
        "label": "cat-research-evidence",
        "construct": "research/evidence citation locator on disk",
        "gold": {
            "evidence": {
                "citations": [
                    {"id": "c1", "locator": "catalog:WFA-0035#library-categories"}
                ]
            }
        },
        "checks": (
            ("evidence.citations", "nonempty_list"),
            ("evidence.citations.0.locator", "nonempty_str"),
        ),
    },
    {
        "family_id": "D14",
        "label": "cat-engineering-reliability",
        "construct": "repro command with expected exit 0",
        "gold": {
            "reliability": {
                "repro_cmd": "python3 -B command-center/p2-wave/probes/WFA-0112/oracle.py",
                "expected_exit": 0,
            }
        },
        "checks": (
            ("reliability.repro_cmd", "nonempty_str"),
            ("reliability.expected_exit", "eq", 0),
        ),
    },
    {
        "family_id": "D15",
        "label": "cat-security-governance",
        "construct": "deny-unlisted-tools policy flag",
        "gold": {
            "security": {
                "policy_id": "no-network-oracle",
                "deny_unlisted_tools": True,
            }
        },
        "checks": (
            ("security.policy_id", "nonempty_str"),
            ("security.deny_unlisted_tools", "is_true"),
        ),
    },
    {
        "family_id": "D16",
        "label": "cat-product-design",
        "construct": "product verdict artifact keys",
        "gold": {"product": {"verdict": "GO", "artifact_keys": ["verdict", "items"]}},
        "checks": (
            ("product.verdict", "in_set", ("GO", "NO-GO")),
            ("product.artifact_keys", "nonempty_list"),
        ),
    },
    {
        "family_id": "D17",
        "label": "cat-data-science",
        "construct": "held-out split named, n recorded as a number",
        "gold": {"science": {"n": 12, "metric": "oracle-reject-rate", "split": "held-out"}},
        "checks": (
            ("science.n", "gte", 1),
            ("science.split", "eq", "held-out"),
            ("science.metric", "nonempty_str"),
        ),
    },
    {
        "family_id": "D18",
        "label": "cat-collective-intelligence",
        "construct": "council votes with a named aggregation rule",
        "gold": {
            "council": {
                "votes": [{"seat": "skeptic", "vote": "PASS"}],
                "rule": "unanimous-or-record-dissent",
            }
        },
        "checks": (
            ("council.votes", "nonempty_list"),
            ("council.rule", "nonempty_str"),
        ),
    },
    {
        "family_id": "D19",
        "label": "honest-null-stages",
        "construct": "HONEST-NULL stages, never an inferred pipeline",
        "gold": {
            "stages": None,
            "honest_null_reason": "source declares no stages",
        },
        "checks": (
            ("stages", "is_null"),
            ("honest_null_reason", "nonempty_str"),
        ),
    },
    {
        "family_id": "D20",
        "label": "ir-not-runtime",
        "construct": "IR has no execution entrypoint",
        "gold": {
            "execution_entrypoint": None,
            "runtime_lint": "NO-RUNTIME",
        },
        "checks": (
            ("execution_entrypoint", "is_null"),
            ("runtime_lint", "eq", "NO-RUNTIME"),
        ),
    },
)


def family_ids() -> list[str]:
    return [str(f["family_id"]) for f in FAMILIES]


def by_id(family_id: str) -> dict[str, Any]:
    for row in FAMILIES:
        if row["family_id"] == family_id:
            return row
    raise KeyError(family_id)
