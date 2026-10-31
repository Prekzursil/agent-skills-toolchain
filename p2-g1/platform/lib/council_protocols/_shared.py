"""Authoring helpers shared by the PHASE-2C council protocol blueprints (P25-P36).

The protocol modules build CouncilSpec instances as plain dicts. Every stopping rule and
every stage exit condition is authored in the HUMAN expression form and parsed with the
sibling ``councilspec.expression`` parser, so ``stopping.source_expression`` and
``stopping.expression`` cannot drift (semantics rule SEM-001 compares the two trees).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Mapping

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:  # allow `python platform/lib/council_protocols/build.py`
    sys.path.insert(0, _LIB)

from councilspec.expression import parse  # noqa: E402

SPEC_DOC = "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
OWNER = "Prekzursil"

# The receipt schema this wave actually shipped. The catalogue units name
# `command-center/schema/receipt.schema.json`, which does not exist; pointing at the real
# file is deliberate and the mismatch is reported by build.py rather than inherited.
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"


def cite(*lines: int) -> List[str]:
    """Design-card citations. Pattern in the schema forbids a colon before the line number."""
    return [f"{SPEC_DOC}:{line}" for line in lines]


def _unbuilt(mechanism: str) -> str:
    """A producer string that names the computation AND admits it does not exist yet.

    SEM-012 exists because a custom metric with no producer is a condition nothing in the run
    is obliged to compute. Naming a mechanism that has not been written is honest; naming a
    file path that does not exist would not be.
    """
    return f"{mechanism} [UNIMPLEMENTED: no runner computes this metric yet]"


# Every custom metric used by P25-P36, and what would have to compute it. Deliberately
# MECHANICAL wherever the question is one an exact algorithm can answer (set difference,
# counting, correlation, text scan) - on this estate LLM judgement on a mechanical comparison
# measured 86% accurate with 100% of the errors pointing at data loss.
PRODUCERS: Dict[str, str] = {
    # P25 blind re-evaluation
    "custom:provenance_leak_count": _unbuilt(
        "token scan of every anonymised option for seat ids, model names, vendor names and file "
        "paths; count of matches"
    ),
    "custom:divergence_audit_complete": _unbuilt(
        "comparison of the blind verdict against the sealed original verdict, recorded as a delta"
    ),
    # P27 design charrette
    "custom:incomplete_candidates": _unbuilt(
        "per-seat completeness check of each shipped candidate against the artifact-per-seat "
        "contract; count of candidates missing a required section"
    ),
    "custom:cycle1_candidate_distance": _unbuilt(
        "mean pairwise textual/structural distance between cycle-1 candidates"
    ),
    # P28 morphological analysis
    "custom:axis_pair_correlation": _unbuilt(
        "max pairwise correlation between parameter axes over the enumerated value sets"
    ),
    "custom:known_option_recall": _unbuilt(
        "fraction of already-known options that appear as a cell of the grid (1.0 = all recalled)"
    ),
    "custom:unreasoned_infeasible_cells": _unbuilt(
        "count of cells marked infeasible with no written reason attached"
    ),
    # P29 TRIZ
    "custom:contradiction_pairs_named": _unbuilt(
        "count of explicit (improve A, worsens B) pairs extracted from the framing"
    ),
    "custom:dissolving_resolutions": _unbuilt(
        "count of resolutions that improve A with no measured worsening of B"
    ),
    "custom:unrejected_tradeoff_answers": _unbuilt(
        "count of submitted answers classified as a compromise that the gatekeeper did not reject"
    ),
    # P30 six hats
    "custom:off_hat_contribution_rate": _unbuilt(
        "share of contributions classified as belonging to a hat other than the current one; the "
        "classifier must first be shown to FIRE on a known off-hat contribution"
    ),
    "custom:hats_worn": _unbuilt("count of distinct hat rounds actually executed"),
    # P31 constraint relaxation
    "custom:constraints_enumerated": _unbuilt(
        "count of constraints extracted from the charter"
    ),
    "custom:unrelaxable_set_marked": _unbuilt(
        "assertion that every AGENTS.md section 6/9 non-negotiable and owner-ops ban H1-H9 is "
        "flagged UNRELAXABLE before any removal is allowed"
    ),
    "custom:unrelaxable_violations": _unbuilt(
        "count of seat proposals that selected a constraint from the UNRELAXABLE set"
    ),
    "custom:binding_constraints_identified": _unbuilt(
        "count of constraints whose removal changed the decision"
    ),
    # P32 counterfactual council
    "custom:failure_only_mechanisms": _unbuilt(
        "set difference: mechanisms named by the already-failed half minus those named by the "
        "already-succeeded half"
    ),
    "custom:success_only_mechanisms": _unbuilt(
        "set difference in the other direction; both are set operations, not judgements"
    ),
    "custom:unfalsifiable_success_causes": _unbuilt(
        "count of success causes that cannot be stated as a falsifiable claim with an anchor"
    ),
    # P33 prediction tournament
    "custom:questions_registered": _unbuilt(
        "count of questions written to the resolution registry"
    ),
    "custom:unresolvable_questions": _unbuilt(
        "count of questions lacking a resolution date or a named resolution source"
    ),
    # P34 scenario planning
    "custom:driver_pair_correlation": _unbuilt(
        "correlation between the two chosen drivers across the reference cases"
    ),
    "custom:futures_stress_tested": _unbuilt(
        "count of the 2x2 quadrants that received a completed stress test"
    ),
    "custom:worst_case_named_per_option": _unbuilt(
        "assertion that every surviving option has a named worst case in at least one quadrant"
    ),
    # P35 reference-class planning poker
    "custom:reference_classes_named": _unbuilt(
        "count of distinct reference classes named before any inside-view number"
    ),
    "custom:unresolvable_reference_class_citations": _unbuilt(
        "count of cited reference classes that do not resolve to a real prior artifact (event "
        "ledger entry, PR, or workflow run record)"
    ),
    "custom:estimate_spread_ratio": _unbuilt(
        "max estimate divided by min estimate in the latest blind round"
    ),
    # P36 calibration tournament
    "custom:unbanded_verdicts": _unbuilt(
        "count of verdicts submitted without a confidence band"
    ),
    "custom:outcomes_recorded": _unbuilt(
        "count of resolved outcomes written to the score store"
    ),
    "custom:min_resolutions_per_seat": _unbuilt(
        "minimum, over seats, of that seat's resolved-outcome count n"
    ),
    "custom:judge_owner_kappa": _unbuilt(
        "Cohen kappa between seat verdicts and the owner's own corrections"
    ),
    "custom:weights_pinned_until_proven": _unbuilt(
        "assertion that every seat weight is still 1.0 because the n>=20 and kappa>0.6 gate has "
        "not been met"
    ),
}


def expr(source: str) -> Dict[str, Any]:
    """Parse an authored stopping expression into the canonical schema tree.

    NOTE - the emitted leaves deliberately carry NO ``producer`` field, and that is forced by
    the substrate, not a choice of convenience. Two rules in the shipped validator are mutually
    exclusive for any rule that uses a custom metric AND declares a human form:

    * SEM-001 requires ``parse(stopping.source_expression) == stopping.expression`` EXACTLY, and
      ``councilspec.expression.parse`` cannot emit a ``producer`` key (see its ``parse_leaf``).
    * SEM-012 WARNS when a custom leaf declares no ``producer``.

    Adding a producer therefore converts an advisory SEM-012 warning into a hard SEM-001 error.
    This lane keeps the round-trip (the machine-checkable property) and carries the producer for
    every custom metric in the ``PRODUCERS`` map below, which build.py enforces for completeness
    and publishes into the lane manifest.

    MEASURED, three states, command-center/_proto3_probe_sem001_vs_sem012.py:

    ====================================  =========  ==========  ========
    state                                 SEM-001    SEM-012     rejected
    ====================================  =========  ==========  ========
    A as shipped (source, no producers)           0          52     0/12
    B producers on the stopping rule             11          25    11/12
    C producers everywhere, source dropped        0           0     0/12
    ====================================  =========  ==========  ========

    B rejects exactly the 11 files whose stopping rule uses a custom metric; P26's does not, so
    it survives. C is a legitimate alternative that trades the round-trip proof for silence; this
    lane chose A because SEM-001 is machine-checkable and SEM-012 is advisory.
    """
    return parse(source)


def missing_producers(tree: Any, found: set | None = None) -> set:
    """Custom metrics in `tree` that have no PRODUCERS entry. Empty set = fully covered."""
    found = set() if found is None else found
    if not isinstance(tree, dict):
        return found
    metric = tree.get("metric")
    if isinstance(metric, str) and metric.startswith("custom:"):
        if metric not in PRODUCERS:
            found.add(metric)
        return found
    for key in ("all_of", "any_of"):
        for child in tree.get(key, []) or []:
            missing_producers(child, found)
    if "not" in tree:
        missing_producers(tree["not"], found)
    if "weighted" in tree:
        for clause in tree["weighted"].get("clauses", []) or []:
            missing_producers(clause.get("when"), found)
    return found


def stopping(source: str, **rest: Any) -> Dict[str, Any]:
    """stopping block whose source_expression and expression are the same object by construction."""
    block: Dict[str, Any] = {"source_expression": source, "expression": expr(source)}
    block.update(rest)
    return block


def privacy(retain_days: int = 90, pii_policy: str = "redact") -> Dict[str, Any]:
    """Deny-by-default redaction. An allowlist redactor leaked real values on this estate."""
    return {
        "redact_secrets": True,
        "redaction_policy": "deny_by_default",
        "retain_days": retain_days,
        "pii_policy": pii_policy,
    }


def injection_defense() -> Dict[str, Any]:
    """Fetched/authored artifacts are untrusted DATA, never instructions."""
    return {
        "treat_artifacts_as_data": True,
        "strip_instructions_from_participant_output": True,
        "quarantine_untrusted_sources": True,
    }


def audit(
    state_dir: str,
    *,
    determinism: str = "seeded",
    resume: bool = True,
    retain_days: int = 90,
    owner_approval_for: List[str] | None = None,
    calibration: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    block: Dict[str, Any] = {
        "transcript": True,
        "replay": True,
        "resume": resume,
        "determinism": determinism,
        "privacy": privacy(retain_days),
        "safety": {
            "forbid_irreversible_actions": True,
            "owner_approval_for": owner_approval_for
            or [
                "any action outside the council transcript",
                "any write to a shared branch",
            ],
        },
        "persistence": {
            "store": "both",
            "path": f"platform/council/state/{state_dir}",
            "checkpoint_every_round": True,
        },
    }
    if calibration is not None:
        block["calibration"] = dict(calibration)
    return block


def agent(
    pid: str,
    role: str,
    *,
    model: str = "opus-5",
    vendor: str = "anthropic",
    expertise: List[str] | None = None,
    authority: str = "voter",
    effort: str = "high",
    fresh_context: bool = False,
    sees_peers: bool = True,
    anonymous: bool = False,
    rights: Mapping[str, Any] | None = None,
    vote_weight: float | None = None,
    briefing: str | None = None,
    partition_id: str | None = None,
    source_access: List[str] | None = None,
    display_name: str | None = None,
) -> Dict[str, Any]:
    """One agent seat. Keys are emitted only when set, so the JSON stays readable."""
    seat: Dict[str, Any] = {
        "participant_id": pid,
        "kind": "agent",
        "model": model,
        "vendor": vendor,
        "role": role,
        "authority": authority,
        "effort": effort,
        "independence": {
            "sees_peers_before_first_position": sees_peers,
            "fresh_context": fresh_context,
        },
    }
    if display_name:
        seat["display_name"] = display_name
    if expertise:
        seat["expertise"] = expertise
    if vote_weight is not None:
        seat["vote_weight"] = vote_weight
    if rights:
        seat["rights"] = dict(rights)
    if source_access:
        seat["source_access"] = source_access
    if anonymous:
        seat["anonymous"] = True
    ctx: Dict[str, Any] = {}
    if briefing:
        ctx["briefing"] = briefing
    if partition_id:
        ctx["partition_id"] = partition_id
    if ctx:
        seat["context"] = ctx
    return seat


def human(
    pid: str,
    role: str,
    *,
    authority: str = "owner",
    expertise: List[str] | None = None,
    rights: Mapping[str, Any] | None = None,
    briefing: str | None = None,
) -> Dict[str, Any]:
    seat: Dict[str, Any] = {
        "participant_id": pid,
        "kind": "human",
        "vendor": "human",
        "role": role,
        "authority": authority,
    }
    if expertise:
        seat["expertise"] = expertise
    if rights:
        seat["rights"] = dict(rights)
    if briefing:
        seat["context"] = {"briefing": briefing}
    return seat


def exact_count(roster: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """count block for a pinned roster; SEM-004 requires exact_n == len(roster)."""
    return {"mode": "exact", "exact_n": len(roster)}
