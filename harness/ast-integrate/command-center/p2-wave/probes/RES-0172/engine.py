"""EVPI placement for owner checkpoints on the research pipeline.

Live rails (independent of each other):
  1. tools/agentspec — HumanCheckpoint exit rule + source_policy tor flag
  2. command-center/WORK-UNIT-CATALOG.json — OQ-3 PR-ONLY; RES-0138 owner gate

EVPI is plan-change value: 0 iff the two owner answers produce the same
subsequent plan (or the question is already bound). Identical branches are
permission theatre and are eliminated. A candidate set where every checkpoint
survives has not applied the test.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AGENTSPEC_ROOT = REPO / "tools" / "agentspec"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
WORKFLOW_SCHEMA = REPO / "command-center" / "schema" / "workflow.schema.json"
OUT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0172-human-checkpoint-evpi-placement.json"
)
SCHEMA_REL = "command-center/schema/design-spec.schema.json"
UNIT = "RES-0172"
SENTINEL = "SUCCESS:RES-0172"
CONTROVERSIAL = "public-tor"

if str(AGENTSPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC_ROOT))

from agentspec.spec import FAILURE_POLICIES, PHASE7_NODE_TYPES, SOURCE_CLASSES  # noqa: E402
from agentspec.validate import validate_workflow  # noqa: E402

DEFAULT_CLASSES = tuple(sorted(c for c in SOURCE_CLASSES if c != CONTROVERSIAL))
PLAN_KEYS = (
    "source_classes",
    "tor_stage",
    "paid_rails",
    "publish_mode",
    "ship_controversial_lineage",
    "escalate_owner_blocked",
    "progress_ack",
)

SHERMAN_KENT = {
    "almost-certain": {
        "band": "almost-certain",
        "p_lo": 0.93,
        "p_hi": 0.99,
        "note": "Sherman-Kent: almost certain",
    },
    "probable": {
        "band": "probable",
        "p_lo": 0.75,
        "p_hi": 0.92,
        "note": "Sherman-Kent: probable",
    },
}


def base_plan() -> dict[str, Any]:
    return {
        "source_classes": list(DEFAULT_CLASSES),
        "tor_stage": False,
        "paid_rails": False,
        "publish_mode": "PR-ONLY",
        "ship_controversial_lineage": False,
        "escalate_owner_blocked": "fail-closed",
        "progress_ack": True,
    }


def apply_patch(plan: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(plan)
    for key, value in patch.items():
        if key == "source_classes" and isinstance(value, list):
            out[key] = sorted(set(value))
        else:
            out[key] = copy.deepcopy(value)
    return out


def fingerprint(plan: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    for key in PLAN_KEYS:
        val = plan[key]
        payload[key] = sorted(val) if isinstance(val, list) else val
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def hamming(plan_a: dict[str, Any], plan_b: dict[str, Any]) -> int:
    dist = 0
    for key in PLAN_KEYS:
        a, b = plan_a[key], plan_b[key]
        if isinstance(a, list) and isinstance(b, list):
            if sorted(a) != sorted(b):
                dist += 1
        elif a != b:
            dist += 1
    return dist


def candidates() -> list[dict[str, Any]]:
    tor_on = sorted(set(DEFAULT_CLASSES) | {CONTROVERSIAL})
    return [
        {
            "id": "CP-TOR-OPT-IN",
            "stage": "source-class-policy",
            "question": (
                "Enable the public-tor source class for this research run? "
                "Without an explicit owner flag the class is unavailable and "
                "the workflow must fail closed (source-policy-tor-unflagged), "
                "not silently drop the class."
            ),
            "allowed_responses": ["enable-public-tor", "keep-unavailable"],
            "default_if_unanswered": "keep-unavailable",
            "branch_a": {
                "label": "enable-public-tor",
                "patch": {"source_classes": tor_on, "tor_stage": True},
            },
            "branch_b": {
                "label": "keep-unavailable",
                "patch": {
                    "source_classes": list(DEFAULT_CLASSES),
                    "tor_stage": False,
                },
            },
            "ask_if": "always (foundational: which source classes exist)",
        },
        {
            "id": "CP-UNBOUNDED-SPEND",
            "stage": "retrieval-budget",
            "question": (
                "Allow paid retrieval rails beyond the unit timeout and the "
                "already-allocated search budget?"
            ),
            "allowed_responses": ["allow-unbounded-spend", "keep-hard-cap"],
            "default_if_unanswered": "keep-hard-cap",
            "branch_a": {
                "label": "allow-unbounded-spend",
                "patch": {"paid_rails": True},
            },
            "branch_b": {
                "label": "keep-hard-cap",
                "patch": {"paid_rails": False},
            },
            "ask_if": "always (foundational: how far the search may spend)",
        },
        {
            "id": "CP-SHIP-CONTROVERSIAL",
            "stage": "pre-output-legal-gate",
            "question": (
                "May claims whose lineage includes a controversial source class "
                "(public-tor on this DSL) ship in the research artifact, or must "
                "they be withheld pending label + independent corroboration + "
                "legal/safety review?"
            ),
            "allowed_responses": ["ship-with-label-and-review", "withhold"],
            "default_if_unanswered": "withhold",
            "branch_a": {
                "label": "ship-with-label-and-review",
                "patch": {"ship_controversial_lineage": True},
            },
            "branch_b": {
                "label": "withhold",
                "patch": {"ship_controversial_lineage": False},
            },
            "ask_if": "when tor_stage is true (collection is not emission)",
        },
        {
            "id": "CP-ESCALATE-OWNER-BLOCKED",
            "stage": "failure-routing",
            "question": (
                "A unit classified owner-blocked is paused. Resume after owner "
                "approval, or fail closed and keep the stated default?"
            ),
            "allowed_responses": ["pause-for-owner", "fail-closed"],
            "default_if_unanswered": "fail-closed",
            "branch_a": {
                "label": "pause-for-owner",
                "patch": {"escalate_owner_blocked": "pause"},
            },
            "branch_b": {
                "label": "fail-closed",
                "patch": {"escalate_owner_blocked": "fail-closed"},
            },
            "ask_if": "when a live unit is owner-blocked",
        },
        {
            "id": "CP-ACK-STATUS",
            "stage": "progress-report",
            "question": "Have you seen the progress report for this research run?",
            "allowed_responses": ["acknowledged", "noted"],
            "default_if_unanswered": "acknowledged",
            "branch_a": {
                "label": "acknowledged",
                "patch": {"progress_ack": True},
            },
            "branch_b": {
                "label": "noted",
                "patch": {"progress_ack": True},
            },
            "ask_if": "never — planted zero-EVPI negative control",
        },
        {
            "id": "CP-SCHEMA-LOOKS-OK",
            "stage": "cosmetic-confirm",
            "question": (
                "The schema-valid JSON artifact looks correct — OK to continue?"
            ),
            "allowed_responses": ["looks-good", "looks-fine"],
            "default_if_unanswered": "looks-good",
            "branch_a": {"label": "looks-good", "patch": {}},
            "branch_b": {"label": "looks-fine", "patch": {}},
            "ask_if": "never — planted zero-EVPI negative control",
        },
        {
            "id": "CP-CONTINUE-PROCEED",
            "stage": "permission-theatre",
            "question": "Continue the research pipeline?",
            "allowed_responses": ["continue", "proceed"],
            "default_if_unanswered": "continue",
            "branch_a": {"label": "continue", "patch": {}},
            "branch_b": {"label": "proceed", "patch": {}},
            "ask_if": "never — identical subsequent plans (permission theatre)",
        },
        {
            "id": "CP-RELEASE-MODE",
            "stage": "publish",
            "question": (
                "Release mode for artifacts of this program: PR-ONLY, "
                "PRIVATE-CANARY, or PUBLIC-MARKETPLACE?"
            ),
            "allowed_responses": ["PR-ONLY", "PRIVATE-CANARY", "PUBLIC-MARKETPLACE"],
            "default_if_unanswered": "PR-ONLY",
            "branch_a": {
                "label": "PR-ONLY",
                "patch": {"publish_mode": "PR-ONLY"},
            },
            "branch_b": {
                "label": "PUBLIC-MARKETPLACE",
                "patch": {"publish_mode": "PUBLIC-MARKETPLACE"},
            },
            "already_settled": {
                "id": "OQ-3",
                "answer": "PR-ONLY",
                "reason": (
                    "Binding owner answer in WORK-UNIT-CATALOG.json; "
                    "re-asking an answered foundation question is forbidden."
                ),
            },
            "ask_if": "never — already settled",
        },
    ]


def score_one(cand: dict[str, Any]) -> dict[str, Any]:
    plan = base_plan()
    plan_a = apply_patch(plan, cand["branch_a"]["patch"])
    plan_b = apply_patch(plan, cand["branch_b"]["patch"])
    fp_a = fingerprint(plan_a)
    fp_b = fingerprint(plan_b)
    dist = hamming(plan_a, plan_b)
    settled = cand.get("already_settled")
    identical_labels = cand["branch_a"]["label"] == cand["branch_b"]["label"]
    theatre = (not settled) and dist == 0
    if settled:
        disposition = "ELIMINATED-ALREADY-SETTLED"
        retain = False
        evpi = dist
    elif dist == 0 or identical_labels:
        disposition = "ELIMINATED-ZERO-EVPI"
        retain = False
        evpi = 0
    else:
        disposition = "RETAIN"
        retain = True
        evpi = dist
    return {
        "id": cand["id"],
        "stage": cand["stage"],
        "question": cand["question"],
        "allowed_responses": list(cand["allowed_responses"]),
        "default_if_unanswered": cand["default_if_unanswered"],
        "ask_if": cand["ask_if"],
        "branches": [
            {
                "response": cand["branch_a"]["label"],
                "plan_fingerprint": fp_a,
                "plan": {k: plan_a[k] for k in PLAN_KEYS},
            },
            {
                "response": cand["branch_b"]["label"],
                "plan_fingerprint": fp_b,
                "plan": {k: plan_b[k] for k in PLAN_KEYS},
            },
        ],
        "plans_diverge": fp_a != fp_b,
        "hamming_distance": dist,
        "evpi_score": evpi,
        "permission_theatre": theatre,
        "already_settled": settled,
        "disposition": disposition,
        "retain": retain,
    }


def score_all() -> list[dict[str, Any]]:
    return [score_one(c) for c in candidates()]


def retained(rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = rows if rows is not None else score_all()
    return [r for r in rows if r["retain"]]


def eliminated_zero_evpi(
    rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = rows if rows is not None else score_all()
    return [r for r in rows if r["disposition"] == "ELIMINATED-ZERO-EVPI"]


def negative_control_ok(rows: list[dict[str, Any]] | None = None) -> bool:
    return len(eliminated_zero_evpi(rows)) >= 1


def all_survive_mutant(rows: list[dict[str, Any]] | None = None) -> bool:
    rows = rows if rows is not None else score_all()
    return all(r["retain"] for r in rows)


def _minimal_wf(nodes: list[dict[str, Any]], owner_tor: bool = False) -> dict[str, Any]:
    return {
        "id": "res-0172-evpi-probe",
        "spec_version": 7,
        "owner_tor_flag": owner_tor,
        "nodes": nodes,
    }


def _work_unit(*, source_classes: list[str]) -> dict[str, Any]:
    return {
        "type": "WorkUnit",
        "id": "u1",
        "prompt_ref": "research.md",
        "routing": {"vendor": "opus"},
        "tool_permissions": ["Read"],
        "requested_tools": ["Read"],
        "source_policy": {"allowed_classes": source_classes},
        "on_failure": {"owner-blocked": "abort"},
    }


def live_dsl_signals() -> dict[str, Any]:
    human_no_exit = {
        "type": "HumanCheckpoint",
        "id": "h1",
        "prompt_ref": "ask.md",
        "allowed_responses": ["yes", "no"],
    }
    human_default = {**human_no_exit, "default_if_unanswered": "no"}
    human_empty = {
        "type": "HumanCheckpoint",
        "id": "h1",
        "prompt_ref": "ask.md",
        "allowed_responses": [],
        "default_if_unanswered": "no",
    }
    ids_no_exit = {x["id"] for x in validate_workflow(_minimal_wf([human_no_exit]))}
    ids_default = {x["id"] for x in validate_workflow(_minimal_wf([human_default]))}
    ids_empty = {x["id"] for x in validate_workflow(_minimal_wf([human_empty]))}
    tor_off = {
        x["id"]
        for x in validate_workflow(
            _minimal_wf(
                [_work_unit(source_classes=[CONTROVERSIAL])], owner_tor=False
            )
        )
    }
    tor_on = {
        x["id"]
        for x in validate_workflow(
            _minimal_wf(
                [_work_unit(source_classes=[CONTROVERSIAL])], owner_tor=True
            )
        )
    }
    return {
        "phase7_node_types": sorted(PHASE7_NODE_TYPES),
        "source_classes": sorted(SOURCE_CLASSES),
        "failure_policies": sorted(FAILURE_POLICIES),
        "human_checkpoint_no_exit": {
            "ids": sorted(ids_no_exit),
            "fires": "human-checkpoint-no-exit" in ids_no_exit,
        },
        "human_checkpoint_with_default": {
            "ids": sorted(ids_default),
            "no_exit_silent": "human-checkpoint-no-exit" not in ids_default,
        },
        "human_checkpoint_empty_responses": {
            "ids": sorted(ids_empty),
            "fires": "human-checkpoint-responses-empty" in ids_empty,
        },
        "tor_unflagged": {
            "ids": sorted(tor_off),
            "fires": "source-policy-tor-unflagged" in tor_off,
        },
        "tor_flagged": {
            "ids": sorted(tor_on),
            "unflagged_silent": "source-policy-tor-unflagged" not in tor_on,
        },
    }


def _walk_id(obj: Any, target: str) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        if obj.get("id") == target:
            return obj
        for val in obj.values():
            hit = _walk_id(val, target)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for val in obj:
            hit = _walk_id(val, target)
            if hit is not None:
                return hit
    return None


def catalog_bindings() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    oq3 = _walk_id(data, "OQ-3") or {}
    res_138 = None
    wfa_77 = None
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = unit.get("id")
        if uid == "RES-0138":
            res_138 = {
                "id": uid,
                "owner_approval_required": bool(unit.get("owner_approval_required")),
                "title": unit.get("title"),
            }
        elif uid == "WFA-0077":
            wfa_77 = {
                "id": uid,
                "owner_approval_required": bool(unit.get("owner_approval_required")),
                "title": unit.get("title"),
            }
    return {
        "oq3": {
            "id": oq3.get("id"),
            "state": oq3.get("state"),
            "answer": oq3.get("answer"),
            "text": oq3.get("text"),
        },
        "res_0138": res_138,
        "wfa_0077": wfa_77,
        "source_classes_in_dsl": sorted(SOURCE_CLASSES),
    }


def sha256_path(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "resolved_url": f"file:{path}",
            "sha256": None,
            "bytes": 0,
            "exists": False,
        }
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    return {
        "resolved_url": f"file:{rel}",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "exists": True,
    }


def lineage_bundle(fetched_at: str) -> list[dict[str, Any]]:
    paths = [
        AGENTSPEC_ROOT / "agentspec" / "spec.py",
        AGENTSPEC_ROOT / "agentspec" / "validate.py",
        CATALOG,
        WORKFLOW_SCHEMA,
    ]
    out = []
    for path in paths:
        row = sha256_path(path)
        row["fetched_at"] = fetched_at
        out.append(row)
    return out


def ordered_minimal_set(
    rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    keep = {r["id"]: r for r in retained(rows)}
    order = [
        "CP-TOR-OPT-IN",
        "CP-UNBOUNDED-SPEND",
        "CP-SHIP-CONTROVERSIAL",
        "CP-ESCALATE-OWNER-BLOCKED",
    ]
    return [
        {
            "id": cid,
            "order": i + 1,
            "question": keep[cid]["question"],
            "default_if_unanswered": keep[cid]["default_if_unanswered"],
            "branches": [b["response"] for b in keep[cid]["branches"]],
            "ask_if": keep[cid]["ask_if"],
            "protocol": "Ask this one foundational question; wait; do not batch.",
        }
        for i, cid in enumerate(order)
        if cid in keep
    ]


if __name__ == "__main__":
    rows = score_all()
    print(
        f"candidates={len(rows)} retained={len(retained(rows))} "
        f"zero_evpi={len(eliminated_zero_evpi(rows))}"
    )
    print(
        f"negative_control_ok={negative_control_ok(rows)} "
        f"all_survive_mutant={all_survive_mutant(rows)}"
    )
    for row in rows:
        print(
            f"{row['id']} {row['disposition']} evpi={row['evpi_score']} "
            f"diverge={row['plans_diverge']}"
        )
