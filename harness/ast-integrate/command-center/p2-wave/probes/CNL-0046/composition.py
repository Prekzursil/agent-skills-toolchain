#!/usr/bin/env python3
"""Executable META-COMPOSITION semantics for CNL-0046.

The Windows harness file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not on
this worktree. Family membership is taken from the catalog's named list
(CNL-0046 question_or_target) and confirmed by an independent recount:
regex over the catalog versus the family field on these records.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FAMILY = "META-COMPOSITION"
EXPECTED_N = 7
NAMED = (
    ("P52", "nested-subcouncils-meta-council"),
    ("P53", "escalation-ladder"),
    ("P54", "cross-vendor-mirrored"),
    ("P55", "shadow-council"),
    ("P56", "minority-report-mandatory"),
    ("P57", "stopping-rule-tournament"),
    ("P58", "owner-in-the-loop-stepwise"),
)
NAMED_IDS = tuple(pid for pid, _ in NAMED)
ACTIONS = frozenset(
    {
        "OPEN_CHILD",
        "RUN_INNER",
        "FAN_IN",
        "WATCH",
        "SEIZE_FLOOR",
        "ESCALATE",
        "MIRROR_STEP",
        "COMPARE",
        "SHADOW_OBSERVE",
        "SHADOW_SEAL",
        "MAJORITY_LOCK",
        "MINORITY_ATTACH",
        "TOURNAMENT_EVAL",
        "OWNER_GATE",
        "TERMINAL",
    }
)
TURN = {
    "P52": frozenset({"parent_outer", "child_inner"}),
    "P53": frozenset({"seize_on_trigger"}),
    "P54": frozenset({"parallel_clocks"}),
    "P55": frozenset({"silent_no_floor"}),
    "P56": frozenset({"post_decision_slot"}),
    "P57": frozenset({"tournament_last_floor"}),
    "P58": frozenset({"owner_boundary"}),
    "P02": frozenset({"exclusive_floor"}),
    "P07": frozenset({"exclusive_floor"}),
    "P20": frozenset({"parallel_silent"}),
}
STOP = {
    "P52": frozenset({"wait_children"}),
    "P53": frozenset({"override_escalate"}),
    "P54": frozenset({"both_mirrors"}),
    "P55": frozenset({"shadow_isolated"}),
    "P56": frozenset({"delay_for_minority"}),
    "P57": frozenset({"tournament_pick"}),
    "P58": frozenset({"owner_gate"}),
    "P02": frozenset({"complete_n_rounds"}),
    "P07": frozenset({"hard_stop_on_vote"}),
    "P20": frozenset({"rounds_until_stability"}),
}
TURN_CLASH = {
    frozenset({"parent_outer", "seize_on_trigger"}),
    frozenset({"parent_outer", "parallel_clocks"}),
    frozenset({"parent_outer", "owner_boundary"}),
    frozenset({"seize_on_trigger", "silent_no_floor"}),
    frozenset({"seize_on_trigger", "tournament_last_floor"}),
    frozenset({"seize_on_trigger", "owner_boundary"}),
    frozenset({"parallel_clocks", "owner_boundary"}),
    frozenset({"silent_no_floor", "post_decision_slot"}),
    frozenset({"tournament_last_floor", "owner_boundary"}),
    frozenset({"exclusive_floor"}),
}
STOP_CLASH = {
    frozenset({"wait_children", "override_escalate"}),
    frozenset({"wait_children", "tournament_pick"}),
    frozenset({"wait_children", "owner_gate"}),
    frozenset({"override_escalate", "delay_for_minority"}),
    frozenset({"override_escalate", "tournament_pick"}),
    frozenset({"both_mirrors", "tournament_pick"}),
    frozenset({"both_mirrors", "owner_gate"}),
    frozenset({"shadow_isolated", "tournament_pick"}),
    frozenset({"delay_for_minority", "tournament_pick"}),
    frozenset({"delay_for_minority", "owner_gate"}),
    frozenset({"tournament_pick", "owner_gate"}),
    frozenset({"hard_stop_on_vote", "complete_n_rounds"}),
}


def _step(
    sid: str, actor: str, action: str, bound: str, nxt: str | None
) -> dict[str, Any]:
    return {
        "id": sid,
        "actor": actor,
        "action": action,
        "bound": bound,
        "next": nxt,
    }


PROTOCOLS: list[dict[str, Any]] = [
    {
        "id": "P52",
        "slug": "nested-subcouncils-meta-council",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P52"]),
        "stop_tags": sorted(STOP["P52"]),
        "composition_preconditions": [
            "at_least_two_child_protocol_ids",
            "fan_in_rule_in_majority_owner_cite_child_evidence",
            "child_completion_before_parent_synthesis",
            "no_two_children_with_exclusive_floor_on_one_roster",
            "parent_may_not_overrule_child_without_citing_child_evidence",
        ],
        "turn_schedule": [
            _step("start", "parent_chair", "OPEN_CHILD", "n_children>=2", "run"),
            _step("run", "children", "RUN_INNER", "each_child.stopping", "fan_in"),
            _step("fan_in", "parent_chair", "FAN_IN", "cite_each_child_record", "end"),
            _step("end", "runtime", "TERMINAL", "parent_stopping_after_children", None),
        ],
        "missing_element": None,
    },
    {
        "id": "P53",
        "slug": "escalation-ladder",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P53"]),
        "stop_tags": sorted(STOP["P53"]),
        "composition_preconditions": [
            "ordered_rungs_with_executable_triggers",
            "each_rung_names_successor_protocol_or_owner_gate",
            "deadlock_detector_distinct_from_slow_progress",
            "seize_floor_only_on_trigger_fire",
        ],
        "turn_schedule": [
            _step("start", "detector", "WATCH", "progress_metric", "seize"),
            _step("seize", "escalator", "SEIZE_FLOOR", "one_turn", "rung"),
            _step("rung", "escalator", "ESCALATE", "rung_table", "end"),
            _step("end", "runtime", "TERMINAL", "rung_terminal_or_resume", None),
        ],
        "missing_element": None,
    },
    {
        "id": "P54",
        "slug": "cross-vendor-mirrored",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P54"]),
        "stop_tags": sorted(STOP["P54"]),
        "composition_preconditions": [
            "at_least_two_vendor_partitions",
            "identical_inner_protocol_card_and_charter",
            "no_cross_talk_until_compare",
            "compare_rule_executable",
        ],
        "turn_schedule": [
            _step("start", "splitter", "OPEN_CHILD", "n_mirrors>=2", "run"),
            _step("run", "mirrors", "MIRROR_STEP", "inner.stopping_each", "compare"),
            _step("compare", "comparator", "COMPARE", "divergence_threshold", "end"),
            _step("end", "runtime", "TERMINAL", "both_mirrors_and_compare", None),
        ],
        "missing_element": None,
    },
    {
        "id": "P55",
        "slug": "shadow-council",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P55"]),
        "stop_tags": sorted(STOP["P55"]),
        "composition_preconditions": [
            "shadow_seats_cannot_take_primary_floor",
            "shadow_read_access_subset_named",
            "shadow_verdict_recorded_not_mixed_into_primary_votes",
            "shadow_stop_must_not_trigger_primary_stop",
        ],
        "turn_schedule": [
            _step("start", "primary", "RUN_INNER", "primary.stopping", "observe"),
            _step("observe", "shadow", "SHADOW_OBSERVE", "no_floor_token", "seal"),
            _step("seal", "shadow", "SHADOW_SEAL", "shadow_record_only", "end"),
            _step("end", "runtime", "TERMINAL", "primary_stop_shadow_isolated", None),
        ],
        "missing_element": None,
    },
    {
        "id": "P56",
        "slug": "minority-report-mandatory",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P56"]),
        "stop_tags": sorted(STOP["P56"]),
        "composition_preconditions": [
            "inner_protocol_emits_majority_or_decision",
            "dissent_exists_or_designated_minority_seat",
            "preservation_path_to_synthesis_is_structural",
            "synthesis_blocked_until_minority_attached",
        ],
        "turn_schedule": [
            _step("start", "inner", "RUN_INNER", "inner.stopping", "lock"),
            _step("lock", "majority", "MAJORITY_LOCK", "decision_record", "minority"),
            _step("minority", "minority_seat", "MINORITY_ATTACH", "must_exist", "end"),
            _step("end", "runtime", "TERMINAL", "decision_plus_minority", None),
        ],
        "missing_element": None,
    },
    {
        "id": "P57",
        "slug": "stopping-rule-tournament",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P57"]),
        "stop_tags": sorted(STOP["P57"]),
        "composition_preconditions": [
            "at_least_two_candidate_stopping_expressions",
            "tournament_scoring_rule_executable",
            "each_candidate_statically_valid",
            "exactly_one_winner_armed_as_live_stop",
        ],
        "turn_schedule": [
            _step("start", "arms", "TOURNAMENT_EVAL", "n_candidates>=2", "pick"),
            _step("pick", "chair", "TOURNAMENT_EVAL", "scoring_rule", "end"),
            _step("end", "runtime", "TERMINAL", "winning_stop_only", None),
        ],
        "missing_element": None,
    },
    {
        "id": "P58",
        "slug": "owner-in-the-loop-stepwise",
        "family": FAMILY,
        "turn_tags": sorted(TURN["P58"]),
        "stop_tags": sorted(STOP["P58"]),
        "composition_preconditions": [
            "owner_seat_with_halt_continue_restart_rights",
            "step_boundaries_named_on_inner_protocol",
            "invalidating_changes_force_restart_not_quiet_continue",
            "audit_records_owner_gate_outcome",
        ],
        "turn_schedule": [
            _step("start", "inner", "RUN_INNER", "until_step_boundary", "gate"),
            _step("gate", "owner", "OWNER_GATE", "halt_continue_restart", "end"),
            _step("end", "runtime", "TERMINAL", "owner_halt_or_inner_complete", None),
        ],
        "missing_element": None,
    },
]


def catalog_named_members() -> list[tuple[str, str]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = None
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == "CNL-0046":
            unit = item
            break
    if unit is None:
        raise RuntimeError("CNL-0046 missing from catalog")
    question = str(unit.get("question_or_target") or "")
    blob = re.search(r"\((P52 .+?P58 [a-z0-9-]+)\)", question)
    if not blob:
        raise RuntimeError("CNL-0046 named list not found in question_or_target")
    return [(pid, slug) for pid, slug in re.findall(r"(P\d{2}) ([a-z0-9-]+)", blob.group(1))]


def schedule_ok(schedule: list[dict[str, Any]]) -> tuple[bool, str | None]:
    if not schedule:
        return False, "empty_schedule"
    ids = [str(s.get("id") or "") for s in schedule]
    if len(set(ids)) != len(ids) or "" in ids:
        return False, "duplicate_or_empty_step_id"
    if ids[0] != "start":
        return False, "first_step_not_start"
    if schedule[-1].get("action") != "TERMINAL" or schedule[-1].get("next") is not None:
        return False, "last_step_not_terminal"
    by_id = {s["id"]: s for s in schedule}
    for step in schedule:
        action = str(step.get("action") or "")
        if action not in ACTIONS:
            return False, f"unknown_action:{action}"
        if not step.get("actor") or not step.get("bound"):
            return False, f"missing_actor_or_bound:{step.get('id')}"
        nxt = step.get("next")
        if nxt is None:
            continue
        if nxt not in by_id:
            return False, f"dangling_next:{step.get('id')}->{nxt}"
    return True, None


def protocol_verdict(rec: dict[str, Any]) -> dict[str, Any]:
    missing = rec.get("missing_element")
    ok, why = schedule_ok(list(rec.get("turn_schedule") or []))
    if ok and not missing:
        return {
            "id": rec["id"],
            "slug": rec["slug"],
            "verdict": "EXECUTABLE",
            "missing_element": None,
            "schedule_ok": True,
        }
    return {
        "id": rec["id"],
        "slug": rec.get("slug"),
        "verdict": "NOT-EXECUTABLE",
        "missing_element": missing or why or "unspecified",
        "schedule_ok": ok,
    }


def pair_conflicts(a: str, b: str) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    for ta in TURN.get(a, ()):
        for tb in TURN.get(b, ()):
            if frozenset({ta, tb}) in TURN_CLASH:
                reasons.append(
                    {"axis": "turn_control", "left": ta, "right": tb, "a": a, "b": b}
                )
    for sa in STOP.get(a, ()):
        for sb in STOP.get(b, ()):
            if frozenset({sa, sb}) in STOP_CLASH:
                reasons.append(
                    {"axis": "stopping", "left": sa, "right": sb, "a": a, "b": b}
                )
    return reasons


def all_meta_pairs() -> list[dict[str, Any]]:
    rows = []
    ids = list(NAMED_IDS)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            reasons = pair_conflicts(a, b)
            axes = sorted({r["axis"] for r in reasons})
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "conflict": bool(reasons),
                    "axes": axes,
                    "reasons": reasons,
                }
            )
    return rows


def family_records(records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    src = records if records is not None else PROTOCOLS
    return [r for r in src if r.get("family") == FAMILY]


def check_bundle(
    records: list[dict[str, Any]],
    compositions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Empty findings = SILENT (known-good). Non-empty = FIRES (reject state)."""
    findings: list[dict[str, Any]] = []
    fam = family_records(records)
    ids = [r.get("id") for r in fam]
    if len(fam) != EXPECTED_N:
        findings.append(
            {
                "code": "FAMILY_COUNT",
                "expected": EXPECTED_N,
                "actual": len(fam),
                "ids": ids,
            }
        )
    if set(ids) != set(NAMED_IDS):
        findings.append(
            {
                "code": "FAMILY_IDS",
                "expected": list(NAMED_IDS),
                "actual": ids,
            }
        )
    for rec in fam:
        verdict = protocol_verdict(rec)
        if verdict["verdict"] == "NOT-EXECUTABLE":
            findings.append(
                {
                    "code": "NOT_EXECUTABLE_OR_MISSING_SCHEDULE",
                    "id": rec.get("id"),
                    "missing_element": verdict["missing_element"],
                }
            )
        pre = rec.get("composition_preconditions") or []
        if len(pre) < 3:
            findings.append(
                {
                    "code": "PRECONDITIONS_THIN",
                    "id": rec.get("id"),
                    "n": len(pre),
                }
            )
    for comp in compositions or []:
        members = [m for m in (comp.get("members") or []) if isinstance(m, str)]
        if len(members) < 2:
            findings.append({"code": "COMPOSITION_TOO_SMALL", "id": comp.get("id")})
            continue
        expected_axes: set[str] = set()
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                for reason in pair_conflicts(a, b):
                    expected_axes.add(reason["axis"])
        marked_axes = set(comp.get("marked_axes") or [])
        if expected_axes - marked_axes:
            findings.append(
                {
                    "code": "CONFLICT_UNMARKED",
                    "id": comp.get("id"),
                    "members": members,
                    "missing_axes": sorted(expected_axes - marked_axes),
                }
            )
        if marked_axes - expected_axes:
            findings.append(
                {
                    "code": "CONFLICT_OVERCLAIMED",
                    "id": comp.get("id"),
                    "members": members,
                    "extra_axes": sorted(marked_axes - expected_axes),
                }
            )
    return findings


def known_good_compositions() -> list[dict[str, Any]]:
    rows = []
    for pair in all_meta_pairs():
        rows.append(
            {
                "id": f"{pair['a']}x{pair['b']}",
                "members": [pair["a"], pair["b"]],
                "marked_axes": list(pair["axes"]),
            }
        )
    rows.append(
        {
            "id": "leaf-ok-two-delphi",
            "members": ["P20", "P20"],
            "marked_axes": [],
        }
    )
    rows.append(
        {
            "id": "leaf-clash-roundrobin-oxford",
            "members": ["P02", "P07"],
            "marked_axes": ["turn_control", "stopping"],
        }
    )
    return rows


def planted_bad_count() -> list[dict[str, Any]]:
    return [r for r in deepcopy(PROTOCOLS) if r["id"] != "P56"]


def planted_bad_schedule() -> list[dict[str, Any]]:
    recs = deepcopy(PROTOCOLS)
    for rec in recs:
        if rec["id"] == "P53":
            rec["turn_schedule"] = []
            rec["missing_element"] = None
    return recs


def planted_bad_conflict() -> list[dict[str, Any]]:
    comps = known_good_compositions()
    for comp in comps:
        if comp["id"] == "P57xP58":
            comp["marked_axes"] = []
    return comps


def dump_fixtures() -> dict[str, Path]:
    fx = HERE / "fixtures"
    fx.mkdir(parents=True, exist_ok=True)
    mapping = {
        "known_good_records.json": PROTOCOLS,
        "known_good_compositions.json": known_good_compositions(),
        "planted_bad_count.json": planted_bad_count(),
        "planted_bad_schedule.json": planted_bad_schedule(),
        "planted_bad_conflict.json": planted_bad_conflict(),
        "conflict_pairs.json": all_meta_pairs(),
    }
    paths: dict[str, Path] = {}
    for name, payload in mapping.items():
        path = fx / name
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        paths[name] = path
    return paths


def both_states() -> dict[str, Any]:
    good_findings = check_bundle(PROTOCOLS, known_good_compositions())
    bad_count = check_bundle(planted_bad_count(), known_good_compositions())
    bad_sched = check_bundle(planted_bad_schedule(), known_good_compositions())
    bad_conf = check_bundle(PROTOCOLS, planted_bad_conflict())
    return {
        "known_good": {
            "fires": bool(good_findings),
            "findings": good_findings,
            "verbatim": json.dumps(good_findings, sort_keys=True),
        },
        "planted_bad_count": {
            "fires": bool(bad_count),
            "findings": bad_count,
            "verbatim": json.dumps(bad_count, sort_keys=True),
        },
        "planted_bad_schedule": {
            "fires": bool(bad_sched),
            "findings": bad_sched,
            "verbatim": json.dumps(bad_sched, sort_keys=True),
        },
        "planted_bad_conflict": {
            "fires": bool(bad_conf),
            "findings": bad_conf,
            "verbatim": json.dumps(bad_conf, sort_keys=True),
        },
        "silent_on_good": not good_findings,
        "fires_on_bad_count": bool(bad_count),
        "fires_on_bad_schedule": bool(bad_sched),
        "fires_on_bad_conflict": bool(bad_conf),
    }
