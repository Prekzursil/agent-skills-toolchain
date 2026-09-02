#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0128-workflow-forge-executable-spec.json as WorkflowIR."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from forge import (  # noqa: E402
    MARGIN_FLOOR,
    OPERATORS,
    load_case,
    run_case,
)

OUT = REPO / "command-center/wfa/WFA-0128-workflow-forge-executable-spec.json"
CATALOG_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json#work_units[id=WFA-0128]"
)
QUESTION = (
    "Implementation target: an executable workflow-forge that takes the scout's "
    "candidate set, selects a fusion operator by policy, constructs the fusion, "
    "benchmarks it against its sources, and returns either a certified executable "
    "workflow with its lineage or an honest proof that no fusion beats the best source."
)


def node(nid: str, kind: str, title: str, **fields: object) -> dict:
    out = {
        "id": nid,
        "kind": kind,
        "title": title,
        "source_anchor": fields.pop("source_anchor", CATALOG_ANCHOR),
    }
    out.update(fields)
    return out


def main() -> int:
    complementary = run_case(load_case("complementary"))
    no_gain = run_case(load_case("no-gain"))
    known_bad = run_case(load_case("known-bad-conflict"))
    if complementary.get("terminal") != "CERTIFIED-FUSION":
        print("FAILED:WFA-0128 emit complementary did not certify", complementary.get("reason"))
        return 1
    if no_gain.get("terminal") != "NO-IMPROVEMENT":
        print("FAILED:WFA-0128 emit no-gain did not decline")
        return 1
    if known_bad.get("terminal") != "NO-IMPROVEMENT":
        print("FAILED:WFA-0128 emit known-bad certified a fusion")
        return 1

    stages = [
        node(
            "ingest-scout-candidates",
            "stage",
            "Ingest scout candidate set",
            role="forge-operator",
            input_schema="scout.CandidateSet",
            notes="Takes the WFA-0127 scout ranking; does not re-search.",
        ),
        node(
            "pair-enumerate",
            "stage",
            "Enumerate source pairs",
            role="forge-operator",
            loop={
                "over": "candidate_pairs",
                "convergence": "every pair has a terminal record (CERTIFIED-FUSION or NO-IMPROVEMENT)",
            },
        ),
        node(
            "precondition-check",
            "gate",
            "Refuse illegal pairs before construction",
            role="certifier",
            fail_closed=True,
            refuse_on=[
                "mechanism-conflict",
                "licence-incompatibility",
                "duplicate-control-plane",
            ],
            both_states=(
                "legal complementary pair proceeds; planted scheduler.central vs "
                "scheduler.distributed pair is refused and never constructed"
            ),
        ),
        node(
            "operator-select-by-policy",
            "stage",
            "Select fusion operator from measured pair properties",
            role="forge-operator",
            policy_inputs=["overlap_ratio", "conflict_present", "licence_blocked", "cost_asymmetry"],
            operators=list(OPERATORS),
            selection_rule=(
                "overlap < 0.35 -> union; overlap > 0.65 -> best-of-breed; else stage-splice. "
                "common-core, conditional-hybrid, ensemble, and progressive remain named on the "
                "surface but are not selected by this pair-property policy."
            ),
        ),
        node(
            "construct-fusion",
            "stage",
            "Construct the selected operator's fusion IR",
            role="forge-operator",
            construction_surface=list(OPERATORS),
            notes="Construction is skipped when precondition-check refuses.",
        ),
        node(
            "benchmark-vs-sources",
            "stage",
            "Score fusion against each source on the same goal",
            role="certifier",
            fan_out=["score(source_a)", "score(source_b)", "score(fusion)"],
            barrier="all three scores present before the gate",
            metric_weights={
                "quality": 0.40,
                "coverage": 0.30,
                "recovery": 0.20,
                "usability": 0.10,
            },
            not_a_signal="stage_count (more stages is not better)",
        ),
        node(
            "capability-and-control-plane-detectors",
            "gate",
            "Fail capability loss or duplicate control planes",
            role="certifier",
            fail_closed=True,
            detectors=["capability-superset-of-sources", "single-control-plane"],
        ),
        node(
            "certification-gate",
            "gate",
            "Certify only if fusion beats the best source by the margin floor",
            role="certifier",
            margin_floor=MARGIN_FLOOR,
            never_depends_on="stage_count",
        ),
        node(
            "lineage-and-rollback-rehearsal",
            "stage",
            "Record lineage and restore each source to a runnable smoke fingerprint",
            role="lineage-clerk",
            required_fields=[
                "source_ids",
                "operator",
                "inherited_licence_obligations",
                "attribution",
                "decomposition_keys",
            ],
            rollback="decompose fusion stages by origin_id / origin_stage_id and match smoke fingerprints",
        ),
        node(
            "emit-terminal",
            "stage",
            "Emit exactly one terminal",
            role="forge-operator",
            terminals=["CERTIFIED-FUSION", "NO-IMPROVEMENT"],
            no_improvement_must_name=["best_source_id", "best_source_score", "margin", "margin_definition"],
        ),
    ]

    doc = {
        "record_type": "WorkflowIR",
        "ir_version": "wfa-workflow-ir/0.1",
        "unit_id": "WFA-0128",
        "id": "meta.workflow-forge",
        "title": "workflow-forge executable meta-workflow over fusion and certification",
        "state": "SUCCESS",
        "completion_sentinel": "SUCCESS:WFA-0128",
        "question_or_target": QUESTION,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/WorkflowIR",
        "schema_pack_note": (
            "WFA-0001 schema pack is absent on this worktree. This document is a WorkflowIR "
            "instance by the WFA-0044 construct list (stages, roles, gates, tool policy, "
            "fan-out, barriers, loops with convergence, retries, resume, stopping expression, "
            "lineage, source_anchor on every node). It is not claimed to have been validated "
            "against a missing $defs/WorkflowIR fragment."
        ),
        "ir_has_no_execution_semantics": True,
        "runtime_entrypoint_defined": False,
        "lossy_field_ledger": [],
        "roles": [
            node("role.forge-operator", "role", "Selects operator, constructs, emits terminal"),
            node("role.certifier", "role", "Runs detectors and the certification gate"),
            node("role.lineage-clerk", "role", "Records lineage and runs rollback rehearsal"),
        ],
        "tool_policy": node(
            "tool-policy",
            "tool_policy",
            "Local Python only",
            allow=["python3"],
            deny=["network", "git-write", "secret-read"],
        ),
        "human_checkpoints": [],
        "retries": node(
            "retry-construct",
            "retry",
            "One construct retry then NO-IMPROVEMENT",
            max_attempts=2,
            then="emit NO-IMPROVEMENT rather than loop",
        ),
        "resume": node(
            "resume-from-last-pair",
            "resume",
            "Resume from the last pair with a terminal record",
            cursor="pair_index",
        ),
        "stopping_expression": node(
            "stop-when-every-pair-has-a-terminal",
            "stopping_expression",
            "Stop when no pair remains PENDING",
            expression="all(pair.terminal in {CERTIFIED-FUSION, NO-IMPROVEMENT} for pair in pairs)",
        ),
        "stages": stages,
        "edges": [
            {"from": "ingest-scout-candidates", "to": "pair-enumerate", "source_anchor": CATALOG_ANCHOR},
            {"from": "pair-enumerate", "to": "precondition-check", "source_anchor": CATALOG_ANCHOR},
            {
                "from": "precondition-check",
                "to": "emit-terminal",
                "on": "illegal",
                "source_anchor": CATALOG_ANCHOR,
            },
            {
                "from": "precondition-check",
                "to": "operator-select-by-policy",
                "on": "legal",
                "source_anchor": CATALOG_ANCHOR,
            },
            {"from": "operator-select-by-policy", "to": "construct-fusion", "source_anchor": CATALOG_ANCHOR},
            {"from": "construct-fusion", "to": "benchmark-vs-sources", "source_anchor": CATALOG_ANCHOR},
            {
                "from": "benchmark-vs-sources",
                "to": "capability-and-control-plane-detectors",
                "source_anchor": CATALOG_ANCHOR,
            },
            {
                "from": "capability-and-control-plane-detectors",
                "to": "certification-gate",
                "source_anchor": CATALOG_ANCHOR,
            },
            {
                "from": "certification-gate",
                "to": "lineage-and-rollback-rehearsal",
                "on": "pass",
                "source_anchor": CATALOG_ANCHOR,
            },
            {
                "from": "certification-gate",
                "to": "emit-terminal",
                "on": "fail",
                "source_anchor": CATALOG_ANCHOR,
            },
            {
                "from": "lineage-and-rollback-rehearsal",
                "to": "emit-terminal",
                "source_anchor": CATALOG_ANCHOR,
            },
        ],
        "operators_named": list(OPERATORS),
        "certification_predicates": {
            "margin_floor": MARGIN_FLOOR,
            "fusion_beats_best_source": True,
            "capability_superset": True,
            "single_control_plane": True,
            "lineage_decomposable": True,
            "rollback_rehearsal_green": True,
            "stage_count_is_not_evidence": True,
        },
        "terminals": {
            "CERTIFIED-FUSION": "certified executable workflow plus lineage",
            "NO-IMPROVEMENT": "best_source_id + numeric margin + reason; a valid terminal",
        },
        "reference_interpreter_path": "command-center/p2-wave/probes/WFA-0128/forge.py",
        "reference_interpreter_is_not_an_ir_entrypoint": True,
        "tests_required_discharged": {
            "known_bad_fusion_returns_no_improvement": known_bad["terminal"] == "NO-IMPROVEMENT",
            "every_forge_output_decomposes_and_rollback_rehearsal": complementary["terminal"]
            == "CERTIFIED-FUSION"
            and bool((complementary.get("rollback") or {}).get("pass")),
            "no_improvement_names_best_source_and_margin": bool(
                no_gain.get("best_source_id") and no_gain.get("margin") is not None
            )
            and bool(known_bad.get("best_source_id") and known_bad.get("margin") is not None),
        },
        "live_reference_runs": {
            "complementary": {
                "fixture": "command-center/p2-wave/probes/WFA-0128/fixtures/complementary.json",
                "terminal": complementary["terminal"],
                "operator": complementary.get("operator"),
                "margin": complementary.get("margin"),
                "fusion_id": (complementary.get("fusion") or {}).get("id"),
                "rollback_pass": (complementary.get("rollback") or {}).get("pass"),
            },
            "no_gain": {
                "fixture": "command-center/p2-wave/probes/WFA-0128/fixtures/no-gain.json",
                "terminal": no_gain["terminal"],
                "reason": no_gain.get("reason"),
                "best_source_id": no_gain.get("best_source_id"),
                "margin": no_gain.get("margin"),
            },
            "known_bad_conflict": {
                "fixture": "command-center/p2-wave/probes/WFA-0128/fixtures/known-bad-conflict.json",
                "terminal": known_bad["terminal"],
                "reason": known_bad.get("reason"),
                "fusion_attempted": known_bad.get("fusion_attempted"),
                "best_source_id": known_bad.get("best_source_id"),
                "margin": known_bad.get("margin"),
            },
        },
        "dependencies_on_this_tree": {
            "WFA-0111": "absent; operator policy is inlined in this interpreter",
            "WFA-0118": "absent; certification gate is inlined in this interpreter",
            "WFA-0110": "absent; lineage and rollback rehearsal are inlined",
            "WFA-0127": "absent; scout candidate sets are fixtures, not a live scout",
            "WFA-0001": "absent; schema pack not on this worktree",
        },
        "evidence_requirement": {
            "A": "end-to-end forge run producing CERTIFIED-FUSION on complementary.json",
            "B": "known-bad-conflict.json returns NO-IMPROVEMENT rather than a fusion",
        },
    }

    forbidden = {"entrypoint", "main", "execute", "runtime"}
    top_forbidden = forbidden.intersection(doc)
    if top_forbidden:
        print("FAILED:WFA-0128 IR defines execution keys", sorted(top_forbidden))
        return 1

    def walk(obj: object) -> list[dict]:
        found: list[dict] = []
        if isinstance(obj, dict):
            if "kind" in obj and "id" in obj:
                found.append(obj)
            for v in obj.values():
                found.extend(walk(v))
        elif isinstance(obj, list):
            for v in obj:
                found.extend(walk(v))
        return found

    missing_anchor = [
        n["id"] for n in walk(doc) if "source_anchor" not in n and n.get("kind") != "fusion"
    ]
    ir_nodes = [
        n
        for n in walk(doc)
        if n.get("kind")
        in {
            "stage",
            "gate",
            "role",
            "tool_policy",
            "retry",
            "resume",
            "stopping_expression",
        }
    ]
    missing_anchor = [n["id"] for n in ir_nodes if "source_anchor" not in n]
    if missing_anchor:
        print("FAILED:WFA-0128 IR nodes missing source_anchor", missing_anchor)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:WFA-0128")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
