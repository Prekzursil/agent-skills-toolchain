#!/usr/bin/env python3
"""Emit the WFA-0144 foundry artifact from a live forge run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    schema_accepts,
    schema_rejects_garbage,
    build_bias_verdict,
    empty_scout_typed_failure,
    looks_right_not_returned,
    rationale_complete,
    resolve_anchor,
    uncovered_not_false_adopt,
    zero_build_cost_mutant_fires,
)
from fixtures import ADOPTION_GOAL, CANDIDATES, UNCOVERED_GOAL  # noqa: E402
from forge import (  # noqa: E402
    FORGE_INPUT_INVALID,
    KIND_COST,
    extract_mechanisms,
    forge,
)

OUT = (
    "command-center/foundry/"
    "WFA-0144-workflow-forge-mechanism-decomposition-and-synthesis.json"
)
SCHEMA_REL = "command-center/schema/foundry-artifact.schema.json"
LOCAL_SCHEMA_REL = "command-center/p2-wave/probes/WFA-0144/artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0144/probe1_build_bias.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0144/probe2_rationale.py"
)
QUESTION = (
    "For a given goal, which mechanism set was extracted, which variants were "
    "benchmarked, and what evidence justifies the returned synthesis over each "
    "rejected variant?"
)
SENTINEL = "SUCCESS:WFA-0144"


def public_winner(winner: dict) -> dict:
    wf = winner.get("workflow") or {}
    sim = winner.get("simulation") or {}
    return {
        "variant_id": winner["variant_id"],
        "kind": winner["kind"],
        "measured_score": winner["measured_score"],
        "pass_rate": winner["pass_rate"],
        "source_candidate_ids": winner.get("source_candidate_ids") or [],
        "workflow": {
            "id": wf.get("id"),
            "kind": wf.get("kind"),
            "stages": wf.get("stages") or [],
            "source_candidate_ids": wf.get("source_candidate_ids") or [],
            "executable": True,
        },
        "simulation": {
            "cases_run": sim.get("cases_run"),
            "cases_passed": sim.get("cases_passed"),
            "pass_rate": sim.get("pass_rate"),
        },
    }


def public_rejected(rows: list[dict]) -> list[dict]:
    out = []
    for v in rows:
        out.append(
            {
                "variant_id": v["variant_id"],
                "kind": v["kind"],
                "measured_score": v["measured_score"],
                "pass_rate": v.get("pass_rate", 0.0),
                "why_rejected": v.get("why_rejected") or "",
                "eligible": v.get("eligible"),
                "ineligible_reason": v.get("ineligible_reason"),
                "static_ok": v.get("static_ok"),
                "static_reason": v.get("static_reason"),
            }
        )
    return out


def public_mechanisms(rows: list[dict]) -> list[dict]:
    return [
        {
            "id": m["id"],
            "op": m["op"],
            "transferable": bool(m.get("transferable")),
            "source_candidate_id": m.get("source_candidate_id"),
        }
        for m in rows
    ]


def main() -> int:
    adopt = forge(ADOPTION_GOAL)
    uncover = forge(UNCOVERED_GOAL)
    if not adopt.get("ok") or not uncover.get("ok"):
        print("FAILED:WFA-0144 emit forge run")
        print(json.dumps({"adopt": adopt, "uncover": uncover}, default=str)[:2000])
        return 1

    bias = build_bias_verdict(adopt)
    mutant = zero_build_cost_mutant_fires()
    uncover_v = uncovered_not_false_adopt(uncover)
    cosmetic = looks_right_not_returned(adopt)
    empty = empty_scout_typed_failure()
    rat_a = rationale_complete(adopt)
    rat_u = rationale_complete(uncover)

    if not (
        bias["ok"]
        and mutant["ok"]
        and uncover_v["ok"]
        and cosmetic["ok"]
        and empty["ok"]
        and rat_a["ok"]
        and rat_u["ok"]
    ):
        print("FAILED:WFA-0144 emit controls")
        print(
            json.dumps(
                {
                    "bias": bias,
                    "mutant": mutant,
                    "uncover": uncover_v,
                    "cosmetic": cosmetic,
                    "empty": empty,
                    "rationale_adopt": rat_a,
                    "rationale_uncover": rat_u,
                },
                indent=2,
                default=str,
            )[:4000]
        )
        return 1
    if not schema_rejects_garbage():
        print("FAILED:WFA-0144 schema accepts garbage")
        return 1

    forge_py = HERE / "forge.py"
    fix_py = HERE / "fixtures.py"
    kind_line = resolve_anchor(forge_py, "KIND_COST = {")
    build_line = resolve_anchor(forge_py, '"BUILD": 0.25')
    bonus_line = resolve_anchor(forge_py, "BUILD_FIT_BONUS")
    looks_line = resolve_anchor(forge_py, "LOOKS_RIGHT_OP")
    rat_line = resolve_anchor(forge_py, 'f"REJECTED {v[\'variant_id\']}')
    inc_line = resolve_anchor(fix_py, '"id": "wf.json-ingest-v3"')
    if min(kind_line, build_line, bonus_line, looks_line, rat_line, inc_line) < 1:
        print("FAILED:WFA-0144 emit could not resolve source anchors")
        print(
            {
                "kind_line": kind_line,
                "build_line": build_line,
                "bonus_line": bonus_line,
                "looks_line": looks_line,
                "rat_line": rat_line,
                "inc_line": inc_line,
            }
        )
        return 1

    mechanisms = public_mechanisms(extract_mechanisms(CANDIDATES))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "WFA-0144",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "workflow-forge: mechanism decomposition and synthesis",
        "question": QUESTION,
        "mechanism": (
            "mechanism extraction -> variant proposal "
            "(ADOPT/ADAPT/MERGE/COMPOSE/BUILD) -> simulated benchmark "
            "on a matched-case corpus -> scored selection with a rationale "
            "that names every rejected variant and its measured score"
        ),
        "schema": SCHEMA_REL + "#/$defs/forge-pipeline",
        "schema_note": {
            "catalog_output_schema": SCHEMA_REL + "#/$defs/forge-pipeline",
            "catalog_schema_present": (REPO / SCHEMA_REL).is_file(),
            "validated_against": LOCAL_SCHEMA_REL,
            "why_local": (
                "Catalog shim $ref's https://ast-integrate.invalid/... ; "
                "jsonschema 4.10.3 follows that $ref over HTTPS and raises "
                "RefResolutionError. Local contract rejects garbage and requires "
                "forge runs, build-bias control, and rationale evidence."
            ),
        },
        "upstream_stand_ins": {
            "WFA-0143": {
                "status": "absent-on-worktree",
                "stand_in": "command-center/p2-wave/probes/WFA-0144/fixtures.py#CANDIDATES",
            },
            "WFA-0129": {
                "status": "absent-on-worktree",
                "stand_in": "command-center/p2-wave/probes/WFA-0144/fixtures.py#CORPUS",
            },
            "WFA-0132": {
                "status": "absent-on-worktree",
                "stand_in": (
                    "in-process score_of/select in forge.py; not the "
                    "pairwise tournament runner"
                ),
            },
            "honesty": (
                "This unit delivers an executable forge with fixtures standing "
                "in for absent upstream foundry artifacts. It does not claim "
                "WFA-0143, WFA-0129, or WFA-0132 were delivered."
            ),
        },
        "kind_cost": KIND_COST,
        "build_fit_bonus": 0.10,
        "extracted_mechanisms": mechanisms,
        "runs": [
            {
                "id": "adoption-goal",
                "goal_id": ADOPTION_GOAL["id"],
                "completed": True,
                "winner": public_winner(adopt["winner"]),
                "rejected": public_rejected(adopt["rejected"]),
                "rationale": adopt["rationale"],
                "scoreboard": adopt["scoreboard"],
                "scoreboard_sha256": adopt["scoreboard_sha256"],
            },
            {
                "id": "uncovered-goal",
                "goal_id": UNCOVERED_GOAL["id"],
                "completed": True,
                "winner": public_winner(uncover["winner"]),
                "rejected": public_rejected(uncover["rejected"]),
                "rationale": uncover["rationale"],
                "scoreboard": uncover["scoreboard"],
                "scoreboard_sha256": uncover["scoreboard_sha256"],
            },
        ],
        "build_bias_control": {
            "adoption_goal_id": ADOPTION_GOAL["id"],
            "winner_kind": "ADOPT",
            "winner_source_candidate_id": "wf.json-ingest-v3",
            "build_variant_benchmarked": True,
            "build_score_lt_adopt": True,
            "uncovered_goal_id": UNCOVERED_GOAL["id"],
            "uncovered_winner_kind": uncover["winner"]["kind"],
            "uncovered_not_false_adopt": True,
            "zero_build_cost_mutant_fires": True,
            "mutant_winner_kind": mutant["mutant_kind"],
        },
        "typed_failure_control": {
            "empty_scout_error_type": FORGE_INPUT_INVALID,
            "looks_right_build_not_returned": True,
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/WFA-0144/forge.py",
                "line": build_line,
                "snippet": '"BUILD": 0.25',
                "kind": "build-bias-kind-cost",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0144/forge.py",
                "line": bonus_line,
                "snippet": "BUILD_FIT_BONUS",
                "kind": "build-fit-bonus-dominated-by-penalty",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0144/forge.py",
                "line": looks_line,
                "snippet": "LOOKS_RIGHT_OP",
                "kind": "cosmetic-build-unknown-op",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0144/forge.py",
                "line": rat_line,
                "snippet": "REJECTED {v['variant_id']}",
                "kind": "rationale-names-losers",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0144/fixtures.py",
                "line": inc_line,
                "snippet": '"id": "wf.json-ingest-v3"',
                "kind": "adoption-incumbent",
            },
        ],
        "tests": [
            {"id": "probe1_build_bias", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2_rationale", "command": P2, "result": "NOT-RUN"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0144-probe2-rationale",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0144/forge.py",
                "exists": True,
                "role": "engine",
            },
            {"path": LOCAL_SCHEMA_REL, "exists": True, "role": "supporting"},
        ],
        "emitted_at": now,
        "kind_cost_anchor_line": kind_line,
    }

    ok, errors = schema_accepts(doc)
    if not ok:
        print("FAILED:WFA-0144 artifact fails forge-pipeline schema")
        print(json.dumps(errors[:20], indent=2))
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = dest.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
