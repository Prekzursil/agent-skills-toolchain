"""Emit council protocol blueprints P01-P12 as executable CouncilSpec instances.

Phase 2C, protocols 1-12 of 48. The DESIGNS already exist as prose option cards in
`12-COUNCIL-PROTOCOLS-AND-PRESETS.md` (P01-P06 DELIBERATIVE, P07-P12 ADVERSARIAL). This
module turns each card into a JSON instance of `platform/schema/councilspec.schema.json`.

Why a generator instead of 12 hand-typed JSON files: semantic rule SEM-001 requires
`stopping.source_expression` to parse to EXACTLY the tree in `stopping.expression`. Typing
both by hand is a defect waiting to happen, so the string is derived from the tree with
`councilspec.expression.unparse` and the round-trip is asserted here, before the file is
written. Three further contract obligations from the unit brief are also asserted
mechanically rather than trusted: >= 3 declared anti-failure controls, every control
mapped to the field that implements it, and a non-empty fast-unanimity response.

Run:  python platform/council/_build_p01_p12.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Mapping

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(HERE, "protocols")

sys.path.insert(0, os.path.join(REPO, "platform", "lib"))

from councilspec.expression import parse, unparse  # noqa: E402
from councilspec.semantics import check, errors  # noqa: E402
from councilspec.validate import schema_errors  # noqa: E402

DOC = "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
RECEIPT = "platform/schema/receipt.schema.json"


# --------------------------------------------------------------------- shared blocks


def audit_block(
    retain_days: int = 90, approvals: List[str] | None = None
) -> Dict[str, Any]:
    return {
        "transcript": True,
        "replay": True,
        "resume": True,
        "determinism": "deterministic_where_possible",
        "privacy": {
            "redact_secrets": True,
            "redaction_policy": "deny_by_default",
            "retain_days": retain_days,
            "pii_policy": "redact",
        },
        "safety": {
            "forbid_irreversible_actions": True,
            "owner_approval_for": approvals or ["merge", "release"],
        },
        "persistence": {"store": "both", "checkpoint_every_round": True},
        "calibration": {"post_run": True, "score": "brier"},
    }


def injection_defense() -> Dict[str, Any]:
    return {
        "treat_artifacts_as_data": True,
        "strip_instructions_from_participant_output": True,
        "quarantine_untrusted_sources": True,
    }


def evidence_reqs(
    min_sources: int = 2, anchor: str = "file_line", outranks: bool = True
) -> Dict[str, Any]:
    return {
        "citation_required": True,
        "anchor_style": anchor,
        "min_independent_sources": min_sources,
        "evidence_outranks_votes": outranks,
    }


def dedup_target(max_similarity: float = 0.82) -> Dict[str, Any]:
    return {
        "enabled": True,
        "max_similarity": max_similarity,
        "trivial_variant_policy": "reject",
    }


def dissent_policy(min_block: int | None = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "preserve_verbatim": True,
        "attributed": True,
        "suppression_check": True,
    }
    if min_block is not None:
        out["min_dissenters_to_block"] = min_block
    return out


def notes(mechanism: str, defenses: Mapping[str, str]) -> str:
    lines = [
        mechanism,
        "",
        "anti-failure controls, each mapped to the field implementing it:",
    ]
    lines += [f"  {k} -> {v}" for k, v in defenses.items()]
    return "\n".join(lines)


# ------------------------------------------------------------------------- protocols


def p01() -> Dict[str, Any]:
    defenses = {
        "moderator_capture": (
            "protocol.sequence[0] is a blind_independent_first_pass so every seat commits a "
            "position before the chair frames anything; deadlock.resolution includes rotate_roles"
        ),
        "participant_dominance": (
            "budgets.speaking_quota_per_participant caps any one seat; "
            "stopping.minimum_deliberation.every_participant_spoke blocks a close while a seat "
            "is silent"
        ),
        "instant_unanimity": (
            "stopping.minimum_deliberation.min_rounds=2 makes a round-1 close impossible; "
            "anti_failure.fast_unanimity_response fires blind_re_evaluation + forced_dissent"
        ),
        "premature_convergence": (
            "protocol.rounds.divergence_before_convergence + the "
            "no_new_objection_rounds >= 2 conjunct in stopping.expression"
        ),
        "sycophancy": (
            "protocol.obligations.forced_dissent + critique_intensity=adversarial + "
            "consensus.dissent_policy.suppression_check"
        ),
        "weak_synthesis": (
            "outputs.required includes argument_graph and "
            "claim_evidence_contradiction_graph, so the synthesis must be reconstructable"
        ),
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p01-free-form-moderated-panel",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Surface the tradeoffs of an ambiguous decision that has no obvious winner and "
                "return a recommendation with its dissent."
            ),
            "charter": (
                "Free-form moderated panel. No fixed speaking order and no assigned opposition; "
                "the chair moderates and a synthesis secretary drafts."
            ),
            "risk_tier": "moderate",
            "desired_output": "recommendation",
            "success_criteria": [
                "every seat filed an independent opening position before any peer output was visible",
                "the panel did not converge before round 2",
                "each tradeoff names the evidence that establishes it",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.75,
            "evidence_requirements": evidence_reqs(min_sources=2, anchor="any"),
            "owner_constraints": {"approval_required": False, "deadline_minutes": 90},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                {
                    "participant_id": "chair-facilitator",
                    "display_name": "Chair / facilitator",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["facilitation", "decision framing"],
                    "role": "chair",
                    "authority": "chair",
                    "vote_weight": 1.0,
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_recruit": True,
                    },
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "pragmatist",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["delivery risk", "operational cost"],
                    "role": "domain_expert",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "skeptic",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["falsification", "counterexample construction"],
                    "role": "critic",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "user-advocate",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["owner intent", "usability"],
                    "role": "user_advocate",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "synthesis-secretary",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["technical writing", "argument mapping"],
                    "role": "synthesizer",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "dominance", "role_collapse"],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["position_memo", "risk_list"],
        },
        "topology": {"kind": "chair_led", "chair": "chair-facilitator"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "independent-openings",
                    "independent": True,
                    "quotas": {"objections_per_participant": 1},
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "open-floor",
                    "rounds": 2,
                    "quotas": {
                        "ideas_per_participant": 2,
                        "novel_ideas_per_round": 1,
                        "objections_per_participant": 2,
                    },
                },
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "steelman",
                    "rounds": 1,
                    "quotas": {"counterexamples_per_round": 1},
                },
                {
                    "kind": "synthesis",
                    "stage_id": "synthesis",
                    "participants": ["synthesis-secretary"],
                },
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "forced_dissent": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 2, "runner": "sandbox"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 90,
            "tool_calls": 120,
            "sources": 20,
            "turns": 30,
            "speaking_quota_per_participant": 6,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 12,
            "novelty_ratio": 0.5,
            "diversity_index": 0.6,
            "objections": 6,
            "counterexamples": 2,
            "evidence_items": 10,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "majority",
            "quorum": {"min_voters": 3, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "calibration_weighted",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.75,
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": dissent_policy(),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "any_of": [
                    {
                        "all_of": [
                            {"metric": "consensus", "op": ">=", "value": 0.75},
                            {
                                "metric": "no_new_objection_rounds",
                                "op": ">=",
                                "value": 2,
                            },
                            {
                                "metric": "all_participants_spoke",
                                "op": "==",
                                "value": True,
                            },
                        ]
                    },
                    {
                        "all_of": [
                            {"metric": "rounds_elapsed", "op": ">=", "value": 6},
                            {"metric": "max_rounds", "op": "==", "value": 6},
                        ]
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 90,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the named tradeoff is re-measured after the first release"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "circular_citation_check": True,
            },
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "rotate_roles",
                "chair_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "strongest_counterexample",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_graph",
                "claim_evidence_contradiction_graph",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P01 free-form moderated panel",
            "spec_citations": [f"{DOC}:118", f"{DOC}:132"],
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P01",
                "skills/council 4-voice panel",
            ],
            "notes": notes(
                "DELIBERATIVE. Chair states the question; seats speak in any order for R rounds; "
                "chair summarises each round; the synthesis secretary drafts; the chair calls the "
                "vote. The distinguishing property is that speaking_order is NOT fixed and no seat "
                "holds assigned opposition - encoded as speaking_order=simultaneous.",
                defenses,
            ),
        },
    }


def p02() -> Dict[str, Any]:
    defenses = {
        "participant_dominance": (
            "protocol.speaking_order=round_robin plus "
            "budgets.speaking_quota_per_participant=6 (one turn per seat per round) makes equal "
            "airtime structural, not a request"
        ),
        "silence": (
            "budgets.min_engagement_turns=6 and max_inactivity_rounds=1; "
            "participants.replacement.triggers includes inactivity"
        ),
        "echo_chamber": (
            "the custom:rotation_reseeded_per_round conjunct in stopping.expression - a fixed "
            "rotation lets seat 1 frame every round, so the order must be re-randomised and the "
            "reseed is a closing precondition"
        ),
        "premature_convergence": (
            "stopping.minimum_deliberation.min_rounds=3 and the "
            "no_new_objection_rounds >= 2 conjunct"
        ),
        "lost_dissent": "consensus.minority_report=required + outcomes.allowed includes minority_report",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p02-round-robin",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Reach a scored recommendation with measurably equal airtime across all seats, so "
                "the verdict is not an artefact of who spoke first or longest."
            ),
            "charter": (
                "Round-robin panel. Fixed rotation, one contribution per seat per round, capped "
                "length, no seat may speak twice until all have spoken."
            ),
            "risk_tier": "moderate",
            "desired_output": "ranked_options",
            "success_criteria": [
                "contribution-length variance across seats is lower than a free-form control",
                "the rotation was re-randomised at the start of every round",
                "every seat scored every option",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.75,
            "evidence_requirements": evidence_reqs(min_sources=2, anchor="any"),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "vendor_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": [
                {
                    "participant_id": "rotation-clerk",
                    "display_name": "Rotation clerk (moderator, non-voting)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["facilitation", "turn accounting"],
                    "role": "moderator",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "seat-architecture",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["system architecture"],
                    "role": "architect",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "seat-security",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["threat modeling"],
                    "role": "security_reviewer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "seat-operations",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["operations", "on-call load"],
                    "role": "risk_officer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "seat-cost",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["cost modeling"],
                    "role": "domain_expert",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "seat-user",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["user workflows"],
                    "role": "user_advocate",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "dominance"],
                "preserve_prior_positions": True,
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["model", "vendor", "position_similarity"],
                "max_similarity": 0.85,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["position_memo"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "reseed",
                    "custom_name": "rotation_reseed",
                    "participants": ["rotation-clerk"],
                },
                {
                    "kind": "round_robin",
                    "stage_id": "rotation",
                    "rounds": 3,
                    "quotas": {
                        "ideas_per_participant": 2,
                        "novel_ideas_per_round": 1,
                        "objections_per_participant": 1,
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "xexam",
                    "rounds": 1,
                    "quotas": {"counterexamples_per_round": 1},
                },
                {"kind": "synthesis", "stage_id": "synthesis"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 5, "divergence_before_convergence": True},
            "turn": {"max_words": 350},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                # Declared explicitly, including where the answer is NO: an absent key and a
                # key set to false are different claims, and the brief asks each protocol to
                # SPECIFY its cross-examination / rebuttal / steelman rule.
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": False,
                "declare_confidence": True,
            },
            "critique_intensity": "standard",
            "experiments": {"allowed": True, "max_experiments": 1, "runner": "sandbox"},
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 75,
            "tool_calls": 100,
            "sources": 18,
            "turns": 36,
            "speaking_quota_per_participant": 6,
            "min_engagement_turns": 6,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 18,
            "novelty_ratio": 0.55,
            "diversity_index": 0.7,
            "objections": 6,
            "counterexamples": 3,
            "evidence_items": 12,
            "dedup": dedup_target(0.85),
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 10},
            "quorum": {
                "min_voters": 4,
                "min_fraction": 0.6,
                "on_failure": "extend_rounds",
            },
            "abstention": {
                "allowed": False,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "trimmed_mean",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.7,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {
                        "metric": "custom:rotation_reseeded_per_round",
                        "op": "==",
                        "value": True,
                        "value_type": "boolean",
                        "producer": "rotation-clerk stage reseed",
                    },
                    {"metric": "all_participants_spoke", "op": "==", "value": True},
                    {"metric": "no_new_objection_rounds", "op": ">=", "value": 2},
                    {
                        "metric": "custom:airtime_gini",
                        "op": "<=",
                        "value": 0.25,
                        "value_type": "number",
                        "producer": "rotation-clerk turn accounting",
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 5,
                "every_participant_spoke": True,
                "min_evidence_items": 8,
            },
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 75,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ]
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "rotate_roles",
                "narrow_scope",
                "split_question",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "forced_dissent",
                "role_rotation",
                "blind_re_evaluation",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "transcript",
                "option_cards",
                "argument_ledger",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P02 round-robin",
            "spec_citations": [f"{DOC}:133", f"{DOC}:146"],
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P02"],
            "notes": notes(
                "DELIBERATIVE. Fixed rotation; each seat contributes exactly once per round at a "
                "capped length; no seat may speak twice until all have spoken. Equal airtime is "
                "enforced by construction and MEASURED - custom:airtime_gini <= 0.25 is a closing "
                "precondition, so an unequal council cannot report success.",
                defenses,
            ),
        },
    }


def p03() -> Dict[str, Any]:
    defenses = {
        "silence": (
            "the fishbowl stage cannot exit until custom:seat_swap_requests >= 1 (or 3 rounds "
            "elapse); zero swap requests means a 4-seat council wearing a 12-seat costume and the "
            "stage exit_when refuses to certify it"
        ),
        "participant_dominance": (
            "topology.caucuses caps the inner circle at 4 members and an entering observer must "
            "swap OUT an inner seat, so live transcript width is fixed"
        ),
        "lost_dissent": (
            "outer-circle seats file written notes the chair must read before the vote - "
            "stopping.expression requires custom:observer_notes_read_before_vote == true"
        ),
        "weak_synthesis": (
            "outputs.required includes argument_ledger and evidence_map; the synthesis must "
            "account for observer notes as well as the inner transcript"
        ),
        "premature_convergence": "stopping.minimum_deliberation.min_rounds=2 plus divergence_before_convergence",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p03-fishbowl",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Let a wide panel review a proposal without producing an unreadable transcript, by "
                "keeping only a small inner circle live at any moment."
            ),
            "charter": (
                "Fishbowl. k active inner seats debate; outer seats observe silently and may only "
                "enter by swapping out an inner seat with a stated reason."
            ),
            "risk_tier": "moderate",
            "desired_output": "review_verdict",
            "success_criteria": [
                "at least one swap request was filed with a stated reason",
                "the chair read every observer note into the record before the vote",
                "live transcript width never exceeded the inner-circle cap",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.7,
            "evidence_requirements": evidence_reqs(min_sources=2),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 8, "min": 8, "max": 8},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 6},
            "roster": [
                {
                    "participant_id": "fishbowl-chair",
                    "display_name": "Chair (reads observer notes into the record)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["facilitation"],
                    "role": "chair",
                    "authority": "chair",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "inner-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["system architecture"],
                    "role": "architect",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "inner-2",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["threat modeling"],
                    "role": "security_reviewer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "inner-3",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["data modeling"],
                    "role": "domain_expert",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "observer-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["performance engineering"],
                    "role": "observer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": False, "may_vote": True},
                },
                {
                    "participant_id": "observer-2",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["release engineering"],
                    "role": "observer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": False, "may_vote": True},
                },
                {
                    "participant_id": "observer-3",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["accessibility"],
                    "role": "user_advocate",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": False, "may_vote": True},
                },
                {
                    "participant_id": "swap-clerk",
                    "display_name": "Swap clerk (records swap requests and reasons)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["seat-state tracking"],
                    "role": "scribe",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {"enabled": True, "triggers": ["inactivity", "dominance"]},
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["position_memo", "risk_list"],
        },
        "topology": {
            "kind": "caucus",
            "caucuses": [
                {
                    "caucus_id": "inner-circle",
                    "members": ["inner-1", "inner-2", "inner-3", "fishbowl-chair"],
                    "private_rounds": 0,
                },
                {
                    "caucus_id": "outer-circle",
                    "members": ["observer-1", "observer-2", "observer-3"],
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "all-seats-read",
                    "independent": True,
                },
                {
                    "kind": "fishbowl",
                    "stage_id": "fishbowl",
                    "rounds": 3,
                    "quotas": {
                        "ideas_per_participant": 2,
                        "novel_ideas_per_round": 1,
                        "objections_per_participant": 1,
                    },
                    "exit_when": {
                        "any_of": [
                            {
                                "metric": "custom:seat_swap_requests",
                                "op": ">=",
                                "value": 1,
                                "value_type": "number",
                                "producer": "swap-clerk seat-state log",
                            },
                            {"metric": "rounds_elapsed", "op": ">=", "value": 3},
                        ]
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "notes-read-in",
                    "custom_name": "observer_notes_read_into_record",
                    "participants": ["fishbowl-chair"],
                },
                {"kind": "synthesis", "stage_id": "synthesis"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 450},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                # No formal cross-examination or steelman round in a fishbowl: the inner circle
                # debates and the outer circle's channel is a written note, not a rebuttal.
                "cross_examination": False,
                "rebuttal_required": True,
                "steelman_before_rebuttal": False,
                "declare_confidence": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "tool_calls": 150,
            "sources": 24,
            "turns": 40,
            "speaking_quota_per_participant": 8,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 20,
            "novelty_ratio": 0.5,
            "diversity_index": 0.7,
            "objections": 8,
            "counterexamples": 3,
            "evidence_items": 14,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "delegation",
            "delegation": {
                "allowed": True,
                "max_chain_length": 2,
                "cycles_forbidden": True,
                "map": {"observer-1": "inner-1", "observer-2": "inner-2"},
            },
            "quorum": {"min_voters": 5, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.7,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {
                        "metric": "custom:observer_notes_read_before_vote",
                        "op": "==",
                        "value": True,
                        "value_type": "boolean",
                        "producer": "fishbowl-chair notes-read-in stage",
                    },
                    {"metric": "consensus", "op": ">=", "value": 0.7},
                    {"metric": "no_new_objection_rounds", "op": ">=", "value": 1},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 6,
                "min_evidence_items": 10,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 120,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ]
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.88},
            "resolution": [
                "rotate_roles",
                "recruit_independent_critic",
                "chair_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "forced_dissent",
                "role_rotation",
                "strongest_counterexample",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "transcript",
                "argument_ledger",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P03 fishbowl",
            "spec_citations": [f"{DOC}:147", f"{DOC}:160"],
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P03"],
            "notes": notes(
                "DELIBERATIVE. The only protocol where a seat's PRIMARY act is deciding whether to "
                "speak at all. Outer seats vote (optionally by delegation to an inner seat) and "
                "file written notes; the design card's inertness tell - zero swap requests - is "
                "wired as the fishbowl stage exit_when, not left as prose.",
                defenses,
            ),
        },
    }


def p04() -> Dict[str, Any]:
    defenses = {
        "moderator_capture": (
            "participants.information_partition (staged_release) hides the question set from the "
            "expert committee until it is frozen, and stopping.expression requires "
            "custom:question_set_hash_unchanged == true, so expert capture of the framing phase is "
            "detectable after the fact"
        ),
        "hallucinated_expertise": (
            "voting.evidence_gate.votes_require_evidence + objective.evidence_requirements."
            "min_independent_sources=3; an expert answer with no anchor cannot move the verdict"
        ),
        "echo_chamber": (
            "the lay committee drafts the verdict and experts may correct facts but not "
            "conclusions - encoded as voting.method=weighted with expert weights pinned to 0"
        ),
        "evidence_free_majority": "voting.evidence_gate.reject_evidence_free_majority + evidence_outranks_majority",
        "lost_dissent": "consensus.minority_report=required with dissent_policy.preserve_verbatim",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p04-consensus-conference",
        "participation": "hybrid",
        "objective": {
            "statement": (
                "Produce a verdict that carries buy-in across incompatible interests by giving "
                "question-ownership to a lay panel and answer-ownership to experts."
            ),
            "charter": (
                "Danish consensus-conference model. Phase 1 lay panel frames the questions; "
                "phase 2 experts answer only those questions; phase 3 the lay panel drafts the "
                "verdict and experts may correct facts but not conclusions."
            ),
            "risk_tier": "moderate",
            "desired_output": "decision",
            "success_criteria": [
                "the frozen question set hash is unchanged at synthesis",
                "no expert seat saw a question before the freeze",
                "every lay verdict clause cites the expert answer it rests on",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.8,
            "evidence_requirements": evidence_reqs(min_sources=3, anchor="any"),
            "owner_constraints": {"approval_required": True, "deadline_minutes": 180},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "stakeholder_balanced"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 7, "min": 7, "max": 7},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 5},
            "roster": [
                {
                    "participant_id": "lay-chair",
                    "display_name": "Lay panel chair",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["owner intent", "plain-language framing"],
                    "role": "chair",
                    "authority": "chair",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "lay-user-advocate",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["day-to-day workflows"],
                    "role": "user_advocate",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "lay-owner",
                    "kind": "human",
                    "vendor": "human",
                    "expertise": ["owner priorities"],
                    "role": "stakeholder",
                    "authority": "owner",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True},
                },
                {
                    "participant_id": "expert-architecture",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["system architecture"],
                    "role": "domain_expert",
                    "authority": "contributor",
                    "vote_weight": 0,
                    "rights": {"may_speak": True, "may_vote": False},
                    "context": {"partition_id": "frozen-questions"},
                },
                {
                    "participant_id": "expert-security",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["threat modeling"],
                    "role": "security_reviewer",
                    "authority": "contributor",
                    "vote_weight": 0,
                    "rights": {"may_speak": True, "may_vote": False},
                    "context": {"partition_id": "frozen-questions"},
                },
                {
                    "participant_id": "expert-legal",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["licensing", "compliance"],
                    "role": "legal_ethics",
                    "authority": "contributor",
                    "vote_weight": 0,
                    "rights": {"may_speak": True, "may_vote": False},
                    "context": {"partition_id": "frozen-questions"},
                },
                {
                    "participant_id": "freeze-clerk",
                    "display_name": "Freeze clerk (hashes the question set)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["record keeping", "hashing"],
                    "role": "scribe",
                    "authority": "contributor",
                    "vote_weight": 0,
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "staged_release",
                "partitions": [
                    {
                        "partition_id": "frozen-questions",
                        "visible_to": [
                            "expert-architecture",
                            "expert-security",
                            "expert-legal",
                        ],
                        "sources": ["question-set.frozen.json"],
                    }
                ],
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "prep_time_minutes": 30,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {
            "kind": "committee",
            "committees": [
                {
                    "committee_id": "lay-panel",
                    "mandate": "owns the questions and owns the final verdict",
                    "members": ["lay-chair", "lay-user-advocate", "lay-owner"],
                },
                {
                    "committee_id": "expert-panel",
                    "mandate": "answers only the frozen questions; may correct facts, not conclusions",
                    "members": [
                        "expert-architecture",
                        "expert-security",
                        "expert-legal",
                    ],
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "nominal_group",
                    "stage_id": "frame-questions",
                    "participants": ["lay-chair", "lay-user-advocate", "lay-owner"],
                    "independent": True,
                    "quotas": {"ideas_per_participant": 5, "novel_ideas_per_round": 2},
                },
                {
                    "kind": "custom",
                    "stage_id": "freeze",
                    "custom_name": "question_set_freeze_hash",
                    "participants": ["freeze-clerk"],
                },
                {
                    "kind": "socratic",
                    "stage_id": "expert-answers",
                    "rounds": 2,
                    "participants": [
                        "expert-architecture",
                        "expert-security",
                        "expert-legal",
                    ],
                    "quotas": {"objections_per_participant": 2},
                },
                {
                    "kind": "custom",
                    "stage_id": "fact-correction",
                    "custom_name": "experts_may_correct_facts_only",
                    "rounds": 1,
                },
                {
                    "kind": "synthesis",
                    "stage_id": "lay-verdict",
                    "participants": ["lay-chair", "lay-user-advocate", "lay-owner"],
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 7, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                # The lay panel cross-examines the experts (socratic stage), but experts may
                # correct facts only - they get no rebuttal against a lay conclusion, which is
                # the whole point of the inverted authority. Declared, not implied.
                "cross_examination": True,
                "rebuttal_required": False,
                "steelman_before_rebuttal": False,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 180,
            "tool_calls": 180,
            "sources": 30,
            "turns": 40,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 24,
            "categories": 5,
            "novelty_ratio": 0.5,
            "coverage_score": 0.85,
            "objections": 6,
            "evidence_items": 18,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "weighted",
            "weights": {
                "lay-chair": 1.0,
                "lay-user-advocate": 1.0,
                "lay-owner": 1.0,
                "expert-architecture": 0,
                "expert-security": 0,
                "expert-legal": 0,
                "freeze-clerk": 0,
            },
            "quorum": {"min_voters": 3, "on_failure": "escalate_to_owner"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "owner",
        },
        "consensus": {
            "threshold": 0.9,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {
                        "metric": "custom:question_set_hash_unchanged",
                        "op": "==",
                        "value": True,
                        "value_type": "boolean",
                        "producer": "freeze-clerk freeze stage",
                    },
                    {"metric": "consent_reached", "op": "==", "value": True},
                    {"metric": "every_objection_addressed", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 3,
                "min_evidence_items": 12,
                "min_objections_addressed": 4,
            },
            "hard_caps": {
                "max_rounds": 7,
                "max_minutes": 180,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "an expert fact-correction is accepted by the lay panel without changing a conclusion"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": [
                "narrow_scope",
                "split_question",
                "recruit_independent_critic",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "recruit_independent_critic",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "idea_catalog",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(approvals=["merge", "release", "publish"]),
        "metadata": {
            "title": "P04 consensus conference",
            "spec_citations": [f"{DOC}:161", f"{DOC}:174"],
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P04"],
            "notes": notes(
                "DELIBERATIVE. Inverts authority: the non-expert seats own the verdict. The card's "
                "adoption proof - freeze-hash the question set before experts are dispatched and "
                "verify it unchanged at synthesis - is a stopping conjunct, so a council that "
                "cannot show the hash cannot close.",
                defenses,
            ),
        },
    }


def p05() -> Dict[str, Any]:
    defenses = {
        "moderator_capture": (
            "the chair rotates every round (custom stage chair_rotation) and voting.tie_break="
            "extend_rounds rather than chair, so no seat both frames the round and breaks the tie"
        ),
        "sycophancy": (
            "protocol.obligations.forced_dissent plus the outgoing chair's mandatory "
            "self-objection, counted as custom:outgoing_chair_self_objections >= 2"
        ),
        "echo_chamber": (
            "custom:framing_diff_nonempty == true is a closing precondition - a null diff between "
            "the round-1 and round-N framings means the rotation was inert and the council may not "
            "report a clean close"
        ),
        "role_collapse": (
            "the self-objection must name a specific framing choice; a generic caveat leaves "
            "custom:outgoing_chair_self_objections unincremented and the stopping rule unmet"
        ),
        "premature_convergence": "stopping.minimum_deliberation.min_rounds=3 (one full rotation) + divergence_before_convergence",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p05-rotating-chair",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Decide a contested question without letting one chair's framing bias persist "
                "across every round."
            ),
            "charter": (
                "Rotating chair. The chair rotates each round; the outgoing chair becomes an "
                "ordinary seat and must file one objection to their OWN prior framing before "
                "handing over."
            ),
            "risk_tier": "moderate",
            "desired_output": "decision",
            "success_criteria": [
                "each round had a different chair",
                "every outgoing chair filed a self-objection naming a specific framing choice",
                "the round-1 and round-N framings differ",
            ],
            "consensus_intent": "surface_disagreement",
            "confidence_target": 0.75,
            "evidence_requirements": evidence_reqs(min_sources=2),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 4, "min": 4, "max": 4},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 4},
            "roster": [
                {
                    "participant_id": "seat-a",
                    "display_name": "Seat A (round-1 chair)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["system architecture"],
                    "role": "chair",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True},
                },
                {
                    "participant_id": "seat-b",
                    "display_name": "Seat B (round-2 chair)",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["falsification"],
                    "role": "critic",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "seat-c",
                    "display_name": "Seat C (round-3 chair)",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["operations"],
                    "role": "risk_officer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "framing-scribe",
                    "display_name": "Framing scribe (diffs each round's framing)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["record keeping", "diffing"],
                    "role": "scribe",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "dominance"],
                "preserve_prior_positions": True,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
        },
        "topology": {"kind": "chair_led", "chair": "seat-a"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "openings",
                    "independent": True,
                },
                {
                    "kind": "custom",
                    "stage_id": "rotation",
                    "custom_name": "chair_rotation_with_self_objection",
                    "rounds": 3,
                    "quotas": {
                        "objections_per_participant": 1,
                        "novel_ideas_per_round": 1,
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "framing-diff",
                    "custom_name": "round1_vs_roundN_framing_diff",
                    "participants": ["framing-scribe"],
                },
                {"kind": "synthesis", "stage_id": "synthesis"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                # The adversarial pressure here is the outgoing chair's mandatory
                # self-objection, not a cross-examination or steelman round. Declared as false
                # so the absence is a stated design choice rather than an omission.
                "cross_examination": False,
                "steelman_before_rebuttal": False,
                "forced_dissent": True,
                "rebuttal_required": True,
                "declare_confidence": True,
            },
            "critique_intensity": "adversarial",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 90,
            "tool_calls": 110,
            "sources": 18,
            "turns": 28,
            "speaking_quota_per_participant": 7,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 12,
            "novelty_ratio": 0.5,
            "objections": 6,
            "counterexamples": 2,
            "evidence_items": 10,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "majority",
            "quorum": {"min_voters": 3, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.75,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {
                        "metric": "custom:outgoing_chair_self_objections",
                        "op": ">=",
                        "value": 2,
                        "value_type": "number",
                        "producer": "framing-scribe rotation log",
                    },
                    {
                        "metric": "custom:framing_diff_nonempty",
                        "op": "==",
                        "value": True,
                        "value_type": "boolean",
                        "producer": "framing-scribe framing-diff stage",
                    },
                    {"metric": "consensus", "op": ">=", "value": 0.75},
                    {"metric": "no_new_objection_rounds", "op": ">=", "value": 1},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
                "min_evidence_items": 8,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 90,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "irreducible_disagreement",
                "minority_report",
                "dissent",
            ]
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "vote_oscillation_rounds": 2},
            "resolution": [
                "rotate_roles",
                "forced_dissent",
                "run_experiment",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "role_rotation",
                "forced_dissent",
                "blind_re_evaluation",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_ledger",
                "votes_by_round",
                "dissent_minority_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P05 rotating chair",
            "spec_citations": [f"{DOC}:175", f"{DOC}:188"],
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P05"],
            "notes": notes(
                "DELIBERATIVE. Targets chair bias specifically. topology.chair names the ROUND-1 "
                "chair only; the rotation stage reassigns it each round. The card's inertness test "
                "(diff round-1 against round-N framing; a null diff means the mechanism is inert) "
                "is a stopping conjunct rather than a note.",
                defenses,
            ),
        },
    }


def p06() -> Dict[str, Any]:
    defenses = {
        "idea_count_gaming": (
            "targets.dedup.trivial_variant_policy=reject with max_similarity 0.8, and the stopping "
            "rule counts unique_ideas and novelty_ratio, not raw_ideas"
        ),
        "duplicate_novelty": (
            "participants.duplicate_detection on position_similarity + "
            "targets.novelty_ratio >= 0.6 as a closing precondition"
        ),
        "premature_convergence": (
            "generation is silent and independent (nominal_group stage, anonymous+independent) so "
            "no seat can anchor another before ideas are on the table"
        ),
        "silence": "quotas.ideas_per_participant=8 per seat in the nominal_group stage; a silent seat fails its quota",
        "echo_chamber": (
            "the clarification round is clarification-ONLY: custom:evaluative_sentences_in_"
            "clarification == 0 must hold at close, which is what stops critique leaking in early"
        ),
        "lost_dissent": "ranking is independent (voting.method=ranked_choice) and consensus.minority_report=required",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p06-nominal-group-technique",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Enumerate the option space for a decision before any evaluation happens, then rank "
                "it independently."
            ),
            "charter": (
                "Nominal Group Technique (Delbecq / Van de Ven). Silent independent generation -> "
                "round-robin one-idea-at-a-time posting with no critique -> clarification-only "
                "round -> independent ranking -> aggregate."
            ),
            "risk_tier": "low",
            "desired_output": "ranked_options",
            "success_criteria": [
                "at least 60 unique ideas survive de-duplication",
                "no evaluative sentence was uttered during the clarification round",
                "every seat submitted an independent ranking",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.7,
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "min_independent_sources": 0,
                "evidence_outranks_votes": False,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": [
                {
                    "participant_id": "ngt-facilitator",
                    "display_name": "Facilitator (rejects evaluative sentences in clarification)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["facilitation", "NGT"],
                    "role": "facilitator",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "gen-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["platform design"],
                    "role": "proposer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "anonymous": True,
                    "independence": {
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                },
                {
                    "participant_id": "gen-2",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["tooling"],
                    "role": "proposer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "anonymous": True,
                    "independence": {
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                },
                {
                    "participant_id": "gen-3",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["research methods"],
                    "role": "proposer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "anonymous": True,
                    "independence": {
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                },
                {
                    "participant_id": "gen-4",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["adjacent-domain transfer"],
                    "role": "proposer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "anonymous": True,
                    "independence": {
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                },
                {
                    "participant_id": "dedup-clerk",
                    "display_name": "De-duplication clerk",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["clustering", "similarity scoring"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 2},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["prompt", "position_similarity"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {
            "research_required": False,
            "independent_prep": True,
            "min_sources": 0,
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "nominal_group",
                    "stage_id": "silent-generation",
                    "rounds": 2,
                    "anonymous": True,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 8, "novel_ideas_per_round": 4},
                },
                {
                    "kind": "round_robin",
                    "stage_id": "posting",
                    "rounds": 2,
                    "quotas": {"ideas_per_participant": 4},
                },
                {
                    "kind": "custom",
                    "stage_id": "clarification",
                    "custom_name": "clarification_only_no_critique",
                    "rounds": 1,
                    "exit_when": {
                        "metric": "custom:evaluative_sentences_in_clarification",
                        "op": "==",
                        "value": 0,
                        "value_type": "number",
                        "producer": "ngt-facilitator clarification screen",
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "ranking",
                    "custom_name": "independent_ranking",
                    "anonymous": True,
                    "independent": True,
                },
                {"kind": "synthesis", "stage_id": "aggregate"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 250},
            "obligations": {
                # NGT's defining rule is the SUPPRESSION of critique until ranking is complete,
                # so all four adversarial obligations are declared FALSE on purpose. A reader
                # (or a gate) can tell this apart from a protocol that forgot to say.
                "must_respond_to_prior": False,
                "must_cite_evidence": False,
                "cross_examination": False,
                "rebuttal_required": False,
                "steelman_before_rebuttal": False,
                "declare_confidence": True,
            },
            "critique_intensity": "gentle",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "tool_calls": 90,
            "sources": 10,
            "turns": 48,
            "speaking_quota_per_participant": 12,
            "min_engagement_turns": 4,
            "max_inactivity_rounds": 1,
        },
        "targets": {
            "unique_ideas": 60,
            "raw_ideas": 96,
            "categories": 8,
            "novelty_ratio": 0.6,
            "diversity_index": 0.7,
            "coverage_score": 0.85,
            "dedup": dedup_target(0.8),
        },
        "voting": {
            "method": "ranked_choice",
            "quorum": {"min_voters": 4, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "pairwise_agreement",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {"metric": "unique_ideas", "op": ">=", "value": 60},
                    {"metric": "novelty_ratio", "op": ">=", "value": 0.6},
                    {"metric": "no_new_idea_rounds", "op": ">=", "value": 2},
                    {
                        "metric": "custom:evaluative_sentences_in_clarification",
                        "op": "==",
                        "value": 0,
                        "value_type": "number",
                        "producer": "ngt-facilitator clarification screen",
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 120,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ]
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.8},
            "resolution": [
                "narrow_scope",
                "split_question",
                "recruit_independent_critic",
                "declare_no_decision",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "recruit_independent_critic",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "idea_ledger",
                "idea_catalog",
                "option_cards",
                "transcript",
                "votes_by_round",
                "dissent_minority_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(retain_days=60),
        "metadata": {
            "title": "P06 nominal group technique",
            "spec_citations": [f"{DOC}:189", f"{DOC}:202"],
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P06"],
            "notes": notes(
                "DELIBERATIVE. Generation is silent AND ranking is independent - that pair is what "
                "distinguishes NGT from a loud brainstorming swarm. The card's failure mode (the "
                "clarification round leaks critique) is enforced twice: as the clarification "
                "stage's exit_when and again as a top-level stopping conjunct.",
                defenses,
            ),
        },
    }


def p07() -> Dict[str, Any]:
    defenses = {
        "evidence_free_majority": (
            "an evidence clerk seat scores every claim and voting.evidence_gate."
            "reject_evidence_free_majority is on; the card's failure mode is a rhetorical win on a "
            "factually wrong side, so a persuasion delta alone cannot close the council - "
            "custom:unsupported_claims_open == 0 is a stopping conjunct"
        ),
        "strategic_voting": (
            "audience seats vote BEFORE and AFTER (custom stages audience_pre_vote / "
            "audience_post_vote) and the signal is the delta, not the tally; "
            "voting.abstention.strategic_abstention_check is on"
        ),
        "circular_debate": (
            "deadlock.detection.repetition_similarity 0.9 with no_progress_rounds 2, and "
            "budgets.rebuttal_depth caps rebuttal recursion at 3"
        ),
        "role_collapse": (
            "proposition and opposition are caucuses with assigned sides; a side that stops arguing "
            "its brief trips participants.replacement.triggers=role_collapse"
        ),
        "premature_convergence": "stopping.minimum_deliberation.min_rounds=3 covers opening, cross-exam and closing before any close",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p07-oxford-debate",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Resolve a binary motion by hearing the strongest case for each side and measuring "
                "how much the panel MOVED, not what it believed beforehand."
            ),
            "charter": (
                "Oxford / parliamentary debate. Motion stated; proposition opening, opposition "
                "opening, cross-examination x2, rebuttals, closings in reverse order; audience "
                "seats vote before and after and the DELTA is the signal."
            ),
            "risk_tier": "high",
            "desired_output": "go_no_go",
            "success_criteria": [
                "both sides filed an opening before any cross-examination",
                "the pre-vote and post-vote were both recorded and the delta computed",
                "no claim carried into the closing without an evidence anchor",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.8,
            "evidence_requirements": evidence_reqs(min_sources=3),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 8, "min": 8, "max": 8},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": [
                {
                    "participant_id": "speaker-chair",
                    "display_name": "Speaker (procedural chair, non-voting)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["debate procedure"],
                    "role": "moderator",
                    "authority": "chair",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "prop-lead",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["the motion under debate"],
                    "role": "proposer",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "prop-second",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["implementation feasibility"],
                    "role": "proposer",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "opp-lead",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["falsification"],
                    "role": "critic",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "opp-second",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["operational risk"],
                    "role": "critic",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "audience-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["program strategy"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "audience-2",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["cost and schedule"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "evidence-clerk",
                    "display_name": "Evidence clerk (anchors every claim)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["evidence grading", "citation checking"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "policy_violation"],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {
            "kind": "caucus",
            "caucuses": [
                {
                    "caucus_id": "proposition",
                    "members": ["prop-lead", "prop-second"],
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "opposition",
                    "members": ["opp-lead", "opp-second"],
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "pre-vote",
                    "custom_name": "audience_pre_vote",
                    "participants": ["audience-1", "audience-2"],
                    "anonymous": True,
                    "independent": True,
                },
                {"kind": "oxford", "stage_id": "openings", "rounds": 1},
                {
                    "kind": "cross_examination",
                    "stage_id": "xexam",
                    "rounds": 2,
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 1,
                    },
                },
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "rebuttals",
                    "rounds": 1,
                    "quotas": {"counterexamples_per_round": 1},
                },
                {
                    "kind": "custom",
                    "stage_id": "closings",
                    "custom_name": "closings_in_reverse_order",
                },
                {
                    "kind": "custom",
                    "stage_id": "post-vote",
                    "custom_name": "audience_post_vote",
                    "participants": ["audience-1", "audience-2"],
                    "anonymous": True,
                    "independent": True,
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 700},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {"allowed": True, "max_experiments": 2, "runner": "ci"},
        },
        "budgets": {
            "effort": "xhigh",
            "time_minutes": 150,
            "tool_calls": 200,
            "sources": 30,
            "turns": 40,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 3,
        },
        "targets": {
            "unique_ideas": 10,
            "novelty_ratio": 0.4,
            "objections": 10,
            "counterexamples": 4,
            "evidence_items": 24,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "majority",
            "quorum": {"min_voters": 2, "on_failure": "recruit"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "linear_pool",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "threshold": 0.8,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {
                        "metric": "custom:pre_post_vote_delta_recorded",
                        "op": "==",
                        "value": True,
                        "value_type": "boolean",
                        "producer": "speaker-chair pre-vote and post-vote stages",
                    },
                    {
                        "metric": "custom:unsupported_claims_open",
                        "op": "==",
                        "value": 0,
                        "value_type": "number",
                        "producer": "evidence-clerk claim ledger",
                    },
                    {"metric": "every_objection_addressed", "op": "==", "value": True},
                    {"metric": "rounds_elapsed", "op": ">=", "value": 3},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 16,
                "min_objections_addressed": 6,
            },
            "hard_caps": {"max_rounds": 6, "max_minutes": 150, "on_cap": "no_decision"},
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "irreducible_disagreement",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the strongest surviving counterexample is re-tested after the motion is enacted"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "narrow_scope",
                "judge_ruling",
                "declare_no_decision",
            ],
            "escalation": {"after_attempts": 2, "to": "judge"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "strongest_counterexample",
                "recruit_independent_critic",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "transcript",
                "argument_graph",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "calibration_report",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P07 oxford debate",
            "spec_citations": [f"{DOC}:206", f"{DOC}:219"],
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P07"],
            "notes": notes(
                "ADVERSARIAL. The pre/post vote delta is unique to this protocol - it measures "
                "persuasion, not prior. Debaters do not vote (rights.may_vote=false); only the "
                "audience jurors do, twice. The card's mitigation for a rhetorical win on a wrong "
                "side (pair with an evidence clerk) is a seat plus a stopping conjunct.",
                defenses,
            ),
        },
    }


def p08() -> Dict[str, Any]:
    defenses = {
        "evidence_free_majority": (
            "the white cell scores only ATTACKS THAT LANDED - an attack with no reproduction path "
            "is discarded, so custom:reproduced_red_findings (not attack count) is what the "
            "stopping rule reads"
        ),
        "idea_count_gaming": (
            "targets.dedup.trivial_variant_policy=reject plus quotas.counterexamples_per_round; "
            "red cannot inflate a score with restated objections"
        ),
        "role_collapse": (
            "topology.kind=red_blue with assigned sides and "
            "participants.replacement.triggers=role_collapse; a red seat that stops attacking is "
            "replaced, and blue may not concede on red's behalf"
        ),
        "collusion": (
            "participants.duplicate_detection across model/vendor/position_similarity and "
            "independence.shares_context_with=[] on both sides"
        ),
        "consensus_failing_executable_tests": (
            "protocol.experiments.required_before_decision=true with runner=ci; the white cell must "
            "independently reproduce a red finding before the council can close on it"
        ),
        "endless_debate": (
            "the second branch of stopping.expression closes the council when red has spent its "
            "attack quota with nothing landing, so a genuinely clean artifact does not deadlock"
        ),
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p08-red-blue-team",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Evaluate a proposal by people who are paid to break it as well as people who want "
                "it to work, and score only the attacks that actually landed."
            ),
            "charter": (
                "Red/blue team with a white cell. Blue defends and hardens; red attacks with "
                "concrete exploit or failure constructions; the white cell scores landed attacks "
                "only and discards any attack with no reproduction path."
            ),
            "risk_tier": "critical",
            "desired_output": "review_verdict",
            "success_criteria": [
                "at least one red finding was independently reproduced by the white cell, or red "
                "spent its full attack quota with nothing landing",
                "every discarded attack names the missing reproduction path",
                "no open P0/P1 finding remains at close",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.9,
            "evidence_requirements": evidence_reqs(
                min_sources=2, anchor="command_output"
            ),
            "owner_constraints": {
                "approval_required": True,
                "forbidden_actions": ["production write", "credential rotation"],
                "deadline_minutes": 240,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial", "vendor_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 7, "min": 7, "max": 7},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 5},
            "roster": [
                {
                    "participant_id": "white-cell-judge",
                    "display_name": "White cell (reproduces findings, scores landed attacks)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["reproduction", "methodology"],
                    "role": "judge",
                    "authority": "judge",
                    "vote_weight": 1.0,
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                    "source_access": ["repo", "transcripts"],
                },
                {
                    "participant_id": "red-1",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["exploit construction"],
                    "role": "red_team",
                    "authority": "contributor",
                    "rights": {
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "red-2",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["failure-mode enumeration"],
                    "role": "red_team",
                    "authority": "contributor",
                    "rights": {
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "blue-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["hardening", "defensive design"],
                    "role": "blue_team",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "blue-2",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["mitigation cost"],
                    "role": "blue_team",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "methodologist",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["detector validation", "both-states testing"],
                    "role": "verifier",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                },
                {
                    "participant_id": "risk-officer",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["severity grading", "blast radius"],
                    "role": "risk_officer",
                    "authority": "veto_holder",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True, "may_veto": True},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "inactivity", "policy_violation"],
                "preserve_prior_positions": True,
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["model", "vendor", "position_similarity"],
                "max_similarity": 0.8,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "risk_list", "benchmark_baseline"],
        },
        "topology": {"kind": "red_blue"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "blue-harden",
                    "independent": True,
                    "participants": ["blue-1", "blue-2"],
                },
                {
                    "kind": "war_game",
                    "stage_id": "red-attack",
                    "rounds": 3,
                    "participants": ["red-1", "red-2"],
                    "quotas": {
                        "counterexamples_per_round": 2,
                        "objections_per_participant": 4,
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "white-cell-reproduction",
                    "custom_name": "white_cell_independent_reproduction",
                    "participants": ["white-cell-judge", "methodologist"],
                    "exit_when": {
                        "any_of": [
                            {
                                "metric": "custom:reproduced_red_findings",
                                "op": ">=",
                                "value": 1,
                                "value_type": "number",
                                "producer": "white-cell-judge reproduction log",
                            },
                            {
                                "metric": "custom:red_attack_attempts",
                                "op": ">=",
                                "value": 12,
                                "value_type": "number",
                                "producer": "white-cell-judge attack ledger",
                            },
                        ]
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "mitigation-review",
                    "rounds": 1,
                },
                {"kind": "synthesis", "stage_id": "verdict"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 800},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 12,
                "runner": "ci",
            },
        },
        "budgets": {
            "effort": "max",
            "time_minutes": 240,
            "tool_calls": 400,
            "sources": 40,
            "experiments": 12,
            "turns": 60,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 3,
        },
        "targets": {
            "unique_ideas": 12,
            "novelty_ratio": 0.5,
            "objections": 12,
            "counterexamples": 6,
            "evidence_items": 30,
            "dedup": dedup_target(0.8),
        },
        "voting": {
            "method": "judge",
            "quorum": {"min_voters": 2, "on_failure": "escalate_to_owner"},
            "veto": {
                "holders": ["risk-officer"],
                "scope": "safety_only",
                "must_justify": True,
                "overridable_by_owner": True,
            },
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "threshold": 0.9,
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "any_of": [
                    {
                        "all_of": [
                            {
                                "metric": "custom:reproduced_red_findings",
                                "op": ">=",
                                "value": 1,
                                "value_type": "number",
                                "producer": "white-cell-judge reproduction log",
                            },
                            {"metric": "objections_open", "op": "==", "value": 0},
                            {"metric": "experiments_passed", "op": ">=", "value": 1},
                        ]
                    },
                    {
                        "all_of": [
                            {
                                "metric": "custom:red_attack_attempts",
                                "op": ">=",
                                "value": 12,
                                "value_type": "number",
                                "producer": "white-cell-judge attack ledger",
                            },
                            {"metric": "counterexamples_found", "op": "==", "value": 0},
                            {"metric": "rounds_elapsed", "op": ">=", "value": 3},
                        ]
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "min_evidence_items": 20,
                "min_objections_addressed": 8,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 240,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "every reproduced red finding has a merged mitigation and a regression test"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.85,
                "circular_citation_check": True,
            },
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "recruit_independent_critic",
                "judge_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "strongest_counterexample",
                "recruit_independent_critic",
                "blind_re_evaluation",
                "forced_dissent",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "experiments",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "action_plan",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(
            retain_days=180, approvals=["merge", "release", "production change"]
        ),
        "metadata": {
            "title": "P08 red/blue team",
            "spec_citations": [f"{DOC}:220", f"{DOC}:233"],
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P08",
                "estate rubric-verifier adversarial lenses",
            ],
            "notes": notes(
                "ADVERSARIAL. Scores LANDED attacks, not argument quality. The card's adoption "
                "proof (at least one red finding independently reproduced before close) is the "
                "first branch of stopping.expression; the second branch exists so a genuinely "
                "clean artifact cannot deadlock the council when red finds nothing.",
                defenses,
            ),
        },
    }


def p09() -> Dict[str, Any]:
    defenses = {
        "premature_convergence": (
            "the antithesis caucus must build a counterplan from the NEGATION of each load-bearing "
            "assumption before synthesis opens; stopping requires "
            "custom:load_bearing_assumptions_negated >= 3"
        ),
        "role_collapse": (
            "the card's failure mode is a strawman counterplan, so the counterplan stage's "
            "exit_when demands custom:counterplan_feasibility_lint == PASS - the counterplan must "
            "be fundable under the same budget as the thesis"
        ),
        "echo_chamber": (
            "topology.caucuses give thesis and antithesis private rounds and "
            "independence.shares_context_with=[] keeps the two chains from merging early"
        ),
        "weak_synthesis": (
            "voting.method=synthesis_only with a dedicated synthesizer seat, and "
            "outcomes.allowed includes irreducible_disagreement so a forced reconciliation is not "
            "the only way to close"
        ),
        "sycophancy": "protocol.obligations.forced_dissent + critique_intensity=adversarial + consensus.fast_unanimity_is_suspicious",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p09-dialectical-inquiry",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Approve or reject a plan by exposing the assumptions that make it look right, and "
                "by building a rival plan out of their negations."
            ),
            "charter": (
                "Dialectical inquiry (Mason / Mitroff strategic assumption surfacing). Thesis seats "
                "state the plan plus its assumption ledger; antithesis seats build a counterplan "
                "from the negation of each load-bearing assumption; a synthesis seat reconciles or "
                "declares irreducible conflict."
            ),
            "risk_tier": "high",
            "desired_output": "plan",
            "success_criteria": [
                "every load-bearing assumption is listed with a confidence band",
                "the counterplan passes the same feasibility lint as the thesis",
                "the synthesis names what was reconciled and what was not",
            ],
            "consensus_intent": "surface_disagreement",
            "confidence_target": 0.8,
            "evidence_requirements": evidence_reqs(min_sources=3),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 5},
            "roster": [
                {
                    "participant_id": "thesis-lead",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["the plan under review"],
                    "role": "proposer",
                    "authority": "contributor",
                    "independence": {
                        "fresh_context": False,
                        "shares_context_with": ["thesis-analyst"],
                    },
                },
                {
                    "participant_id": "thesis-analyst",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["delivery sequencing"],
                    "role": "domain_expert",
                    "authority": "contributor",
                },
                {
                    "participant_id": "assumption-auditor",
                    "display_name": "Assumption auditor (builds the ledger, grades confidence)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["assumption ledgers", "confidence calibration"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "antithesis-lead",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["counterplanning"],
                    "role": "devils_advocate",
                    "authority": "contributor",
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "antithesis-analyst",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["feasibility and cost"],
                    "role": "critic",
                    "authority": "contributor",
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "synthesizer",
                    "display_name": "Synthesizer (reconciles or declares irreducible conflict)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["synthesis", "argument mapping"],
                    "role": "synthesizer",
                    "authority": "judge",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "inactivity"],
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "required_artifacts": ["position_memo", "risk_list", "prior_art_scan"],
        },
        "topology": {
            "kind": "caucus",
            "caucuses": [
                {
                    "caucus_id": "thesis",
                    "members": ["thesis-lead", "thesis-analyst"],
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "antithesis",
                    "members": ["antithesis-lead", "antithesis-analyst"],
                    "private_rounds": 2,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "assumption-ledger",
                    "custom_name": "load_bearing_assumption_ledger",
                    "participants": [
                        "thesis-lead",
                        "thesis-analyst",
                        "assumption-auditor",
                    ],
                    "quotas": {"ideas_per_participant": 4},
                },
                {
                    "kind": "custom",
                    "stage_id": "counterplan",
                    "custom_name": "counterplan_from_assumption_negations",
                    "rounds": 2,
                    "participants": ["antithesis-lead", "antithesis-analyst"],
                    "quotas": {
                        "novel_ideas_per_round": 2,
                        "counterexamples_per_round": 2,
                    },
                    "exit_when": {
                        "metric": "custom:counterplan_feasibility_lint",
                        "op": "==",
                        "value": "PASS",
                        "value_type": "string",
                        "producer": "assumption-auditor feasibility lint",
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "thesis-vs-antithesis",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 3},
                },
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "steelman",
                    "rounds": 1,
                },
                {
                    "kind": "synthesis",
                    "stage_id": "synthesis",
                    "participants": ["synthesizer"],
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 800},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "forced_dissent": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 4, "runner": "ci"},
        },
        "budgets": {
            "effort": "xhigh",
            "time_minutes": 210,
            "tool_calls": 260,
            "sources": 35,
            "experiments": 4,
            "turns": 48,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 3,
        },
        "targets": {
            "unique_ideas": 16,
            "novelty_ratio": 0.55,
            "coverage_score": 0.85,
            "objections": 10,
            "counterexamples": 5,
            "evidence_items": 24,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "synthesis_only",
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "threshold": 0.8,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "any_of": [
                    {
                        "all_of": [
                            {
                                "metric": "custom:load_bearing_assumptions_negated",
                                "op": ">=",
                                "value": 3,
                                "value_type": "number",
                                "producer": "assumption-auditor ledger",
                            },
                            {
                                "metric": "custom:counterplan_feasibility_lint",
                                "op": "==",
                                "value": "PASS",
                                "value_type": "string",
                                "producer": "assumption-auditor feasibility lint",
                            },
                            {
                                "metric": "every_objection_addressed",
                                "op": "==",
                                "value": True,
                            },
                            {"metric": "consensus", "op": ">=", "value": 0.8},
                        ]
                    },
                    {
                        "all_of": [
                            {"metric": "deadlock_detected", "op": "==", "value": True},
                            {
                                "metric": "minority_report_present",
                                "op": "==",
                                "value": True,
                            },
                        ]
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "min_evidence_items": 16,
                "min_objections_addressed": 6,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 210,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "irreducible_disagreement",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "each negated assumption that survived is re-checked before the plan's second phase"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.88,
                "circular_citation_check": True,
            },
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "split_question",
                "judge_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "forced_dissent",
                "strongest_counterexample",
                "blind_re_evaluation",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_graph",
                "claim_evidence_contradiction_graph",
                "option_cards",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "action_plan",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(retain_days=120),
        "metadata": {
            "title": "P09 dialectical inquiry",
            "spec_citations": [f"{DOC}:234", f"{DOC}:247"],
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P09",
                "AGENTS.md 1b assumption ledger",
            ],
            "notes": notes(
                "ADVERSARIAL. Attacks the assumption SET, not the conclusion - that is what "
                "separates it from a key-assumptions check, which never builds a rival plan. The "
                "counterplan cannot be a strawman: the stage will not exit until it passes the same "
                "feasibility lint as the thesis.",
                defenses,
            ),
        },
    }


def p10() -> Dict[str, Any]:
    defenses = {
        "sycophancy": (
            "one seat is institutionally required to oppose regardless of private view "
            "(role=devils_advocate) and protocol.obligations.forced_dissent is on"
        ),
        "premature_convergence": (
            "the delay-veto: stopping.expression requires "
            "custom:unanswered_advocate_objections == 0, so the council literally cannot close "
            "while the advocate has an unanswered objection"
        ),
        "instant_unanimity": (
            "consensus.fast_unanimity_is_suspicious with a three-way "
            "anti_failure.fast_unanimity_response, and minimum_deliberation.min_rounds=2"
        ),
        "strategic_voting": (
            "the advocate holds a delay-veto, not a decision veto (voting.veto.scope="
            "final_decision, overridable_by_owner) and deadlock.escalation.after_attempts=2 caps "
            "veto-gaming at two unanswered-objection rounds"
        ),
        "lost_dissent": "consensus.minority_report=required + dissent_policy.preserve_verbatim + attributed",
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p10-mandated-devils-advocate",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Prevent a panel from closing before anyone was obliged to argue the other side."
            ),
            "charter": (
                "Mandated devil's advocate. One seat must oppose regardless of private view and "
                "holds a DELAY-veto: the council may not close while that seat has an unanswered "
                "objection. Unanswered-objection rounds are capped at 2."
            ),
            "risk_tier": "high",
            "desired_output": "decision",
            "success_criteria": [
                "the advocate filed at least one substantive objection",
                "every advocate objection is either answered on the record or escalated",
                "the council did not close with an unanswered advocate objection",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.8,
            "evidence_requirements": evidence_reqs(min_sources=2),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                {
                    "participant_id": "panel-chair",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["facilitation", "decision framing"],
                    "role": "chair",
                    "authority": "chair",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "devils-advocate",
                    "display_name": "Devil's advocate (delay-veto holder)",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["falsification", "adversarial reading"],
                    "role": "devils_advocate",
                    "authority": "veto_holder",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True, "may_veto": True},
                    "independence": {
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                },
                {
                    "participant_id": "seat-domain",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["the domain under decision"],
                    "role": "domain_expert",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "seat-risk",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["risk and reversibility"],
                    "role": "risk_officer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "objection-scribe",
                    "display_name": "Objection scribe (tracks answered/unanswered)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["record keeping"],
                    "role": "scribe",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "inactivity"],
                "preserve_prior_positions": True,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["position_memo", "risk_list"],
        },
        "topology": {"kind": "chair_led", "chair": "panel-chair"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "openings",
                    "independent": True,
                },
                {
                    "kind": "custom",
                    "stage_id": "mandated-opposition",
                    "custom_name": "mandated_opposition_round",
                    "rounds": 2,
                    "participants": ["devils-advocate"],
                    "quotas": {
                        "objections_per_participant": 3,
                        "counterexamples_per_round": 1,
                    },
                },
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "answer-the-advocate",
                    "rounds": 2,
                },
                {"kind": "synthesis", "stage_id": "synthesis"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                # The panel must STEELMAN the advocate's objection before answering it; there is
                # no separate cross-examination stage, so that key is declared false.
                "cross_examination": False,
                "steelman_before_rebuttal": True,
                "forced_dissent": True,
                "rebuttal_required": True,
                "declare_confidence": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 3, "runner": "ci"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "tool_calls": 160,
            "sources": 22,
            "turns": 34,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 3,
        },
        "targets": {
            "unique_ideas": 10,
            "novelty_ratio": 0.45,
            "objections": 8,
            "counterexamples": 3,
            "evidence_items": 14,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "majority",
            "quorum": {"min_voters": 3, "on_failure": "extend_rounds"},
            "veto": {
                "holders": ["devils-advocate"],
                "scope": "final_decision",
                "must_justify": True,
                "overridable_by_owner": True,
            },
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.8,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "any_of": [
                    {
                        "all_of": [
                            {
                                "metric": "custom:unanswered_advocate_objections",
                                "op": "==",
                                "value": 0,
                                "value_type": "number",
                                "producer": "objection-scribe objection ledger",
                            },
                            {"metric": "consensus", "op": ">=", "value": 0.8},
                            {
                                "metric": "every_objection_addressed",
                                "op": "==",
                                "value": True,
                            },
                        ]
                    },
                    {
                        "all_of": [
                            {"metric": "rounds_elapsed", "op": ">=", "value": 6},
                            {"metric": "max_rounds", "op": "==", "value": 6},
                            {"metric": "owner_approved", "op": "==", "value": True},
                        ]
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 10,
                "min_objections_addressed": 3,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 120,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the advocate's strongest surviving objection is re-tested after the decision ships"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "vote_oscillation_rounds": 2,
                "circular_citation_check": True,
            },
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "chair_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "forced_dissent",
                "strongest_counterexample",
                "blind_re_evaluation",
                "recruit_independent_critic",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_ledger",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P10 mandated devil's advocate",
            "spec_citations": [f"{DOC}:248", f"{DOC}:261"],
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P10",
                "skills/council Skeptic voice",
            ],
            "notes": notes(
                "ADVERSARIAL. Opposition is a DUTY of one named seat, and the delay-veto is the "
                "distinguishing power. The card demands a both-states proof: with the role the "
                "council CANNOT close while an objection is unanswered, and without it the same "
                "council can. Both states are executable against stopping.expression - set "
                "custom:unanswered_advocate_objections to 1 and the expression is False; set it to "
                "0 and it is True.",
                defenses,
            ),
        },
    }


def _p11_subcouncil(side: str, chair: str, model: str, vendor: str) -> Dict[str, Any]:
    other = "B" if side == "a" else "A"
    return {
        "schema_version": "1.0.0",
        "council_id": f"p11-team-{side}-independent-estimate",
        "participation": "agent_only",
        "objective": {
            "statement": (
                f"Team {side.upper()}: produce an independent estimate from the pinned raw source "
                f"set, with no access to Team {other}'s product."
            ),
            "charter": (
                "Isolated analytic cell. Same question, same raw sources, byte-identical brief, "
                "zero conclusions in the brief."
            ),
            "risk_tier": "high",
            "desired_output": "forecast",
            "success_criteria": [
                "the estimate cites only the pinned source set",
                f"no Team {other} token appears anywhere in this cell's context",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.75,
            "evidence_requirements": evidence_reqs(min_sources=3),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 3, "min": 3, "max": 3},
            "roster": [
                {
                    "participant_id": chair,
                    "display_name": f"Team {side.upper()} lead",
                    "model": model,
                    "vendor": vendor,
                    "expertise": ["analytic tradecraft"],
                    "role": "chair",
                    "authority": "chair",
                    "vote_weight": 1.0,
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": f"{side}-analyst-1",
                    "model": model,
                    "vendor": vendor,
                    "expertise": ["source analysis"],
                    "role": "domain_expert",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": f"{side}-analyst-2",
                    "model": model,
                    "vendor": vendor,
                    "expertise": ["base rates", "reference classes"],
                    "role": "forecaster",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "role_scoped",
                "partitions": [
                    {
                        "partition_id": f"team-{side}-sources",
                        "visible_to": [chair, f"{side}-analyst-1", f"{side}-analyst-2"],
                        "sources": ["pinned-source-set.json"],
                    }
                ],
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {"kind": "chair_led", "chair": chair},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "read-sources",
                    "independent": True,
                },
                {"kind": "prediction_confidence", "stage_id": "estimate", "rounds": 2},
                {"kind": "synthesis", "stage_id": "cell-estimate"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 2, "max": 4},
            "turn": {"max_words": 700},
            "obligations": {
                "must_cite_evidence": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "tool_calls": 150,
            "sources": 30,
            "turns": 18,
        },
        "targets": {
            "evidence_items": 18,
            "coverage_score": 0.8,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "bayesian",
            "belief_aggregation": {
                "method": "logarithmic_pool",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.7,
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": dissent_policy(),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {"metric": "evidence_saturation", "op": "==", "value": True},
                    {"metric": "confidence", "op": ">=", "value": 0.7},
                ]
            },
            "minimum_deliberation": {"min_rounds": 2, "min_evidence_items": 12},
            "hard_caps": {
                "max_rounds": 4,
                "max_minutes": 120,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": ["decision", "no_decision", "minority_report", "dissent"]
        },
        "anti_failure": {
            "controls": [
                "echo_chamber",
                "collusion",
                "evidence_free_majority",
                "hallucinated_expertise",
            ],
            "fast_unanimity_response": ["blind_re_evaluation", "forced_dissent"],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "evidence_map",
                "confidence_trajectory",
                "dissent_minority_report",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(retain_days=180),
        "metadata": {
            "title": f"P11 Team {side.upper()} isolated cell",
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P11"],
        },
    }


def p11() -> Dict[str, Any]:
    defenses = {
        "echo_chamber": (
            "two fully independent cells (topology.subcouncils) re-derive the estimate from the "
            "same pinned raw sources; neither sees the other's product until adjudication"
        ),
        "collusion": (
            "the card's failure mode is Team B leaking Team A's framing through a shared brief, so "
            "the brief must be byte-identical and conclusion-free: "
            "custom:brief_hash_identical == true AND custom:team_a_tokens_in_team_b_brief == 0 are "
            "both closing preconditions"
        ),
        "hidden_conflict_of_interest": (
            "participants.conflicts_policy.on_conflict=recuse_from_vote with disclosure_required, "
            "applied to the adjudication panel that sees both products"
        ),
        "evidence_free_majority": (
            "voting.method=judge with evidence_gate.evidence_outranks_majority; a divergence is "
            "settled by the sources, not by which cell had more seats"
        ),
        "premature_convergence": (
            "topology.fan_in.require_all_subcouncils_complete + the "
            "subcouncils_complete >= 2 conjunct; adjudication cannot start on one cell's answer"
        ),
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p11-team-b-competitive-estimate",
        "participation": "hybrid",
        "objective": {
            "statement": (
                "Test whether a load-bearing analytic claim survives full independent "
                "re-derivation, by having a second team answer the same question from the same raw "
                "sources without ever seeing the first team's product."
            ),
            "charter": (
                "Team A / Team B competitive estimate (US IC, 1976). Two isolated cells, one pinned "
                "source set, byte-identical conclusion-free briefs; the two products are compared "
                "only after both are final and the divergences are adjudicated."
            ),
            "risk_tier": "critical",
            "desired_output": "forecast",
            "success_criteria": [
                "both briefs hash identically and contain no conclusion",
                "no Team A output token appears in Team B's brief or context",
                "every divergence between the two estimates is adjudicated on the record",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.9,
            "evidence_requirements": evidence_reqs(min_sources=3),
            "owner_constraints": {"approval_required": True, "deadline_minutes": 480},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "vendor_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                {
                    "participant_id": "adjudication-chair",
                    "display_name": "Adjudication chair (sees both products, only after both are final)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["analytic tradecraft", "divergence adjudication"],
                    "role": "judge",
                    "authority": "judge",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "brief-clerk",
                    "display_name": "Brief clerk (hashes both briefs, scans for leakage)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["hashing", "leak detection"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "divergence-analyst",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["comparative analysis"],
                    "role": "statistician",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "team-a-lead",
                    "display_name": "Team A lead (reports A's product; does not see B's)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["analytic tradecraft"],
                    "role": "proposer",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
                {
                    "participant_id": "team-b-lead",
                    "display_name": "Team B lead (reports B's product; does not see A's)",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["analytic tradecraft"],
                    "role": "proposer",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {"fresh_context": True, "shares_context_with": []},
                },
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "hidden_profile",
                "partitions": [
                    {
                        "partition_id": "team-a-product",
                        "visible_to": ["team-a-lead", "adjudication-chair"],
                        "sources": ["team-a-estimate.json"],
                    },
                    {
                        "partition_id": "team-b-product",
                        "visible_to": ["team-b-lead", "adjudication-chair"],
                        "sources": ["team-b-estimate.json"],
                    },
                ],
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["model", "vendor", "prompt", "position_similarity"],
                "max_similarity": 0.75,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "prep_time_minutes": 60,
            "required_artifacts": ["evidence_pack", "prior_art_scan", "position_memo"],
        },
        "topology": {
            "kind": "nested_subcouncil",
            "subcouncils": [
                _p11_subcouncil("a", "a-lead", "opus-5", "anthropic"),
                _p11_subcouncil("b", "b-lead", "gpt-5-codex", "openai"),
            ],
            "fan_in": {
                "reducer": "meta_jury",
                "require_all_subcouncils_complete": True,
            },
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "brief-pinning",
                    "custom_name": "pin_sources_and_hash_briefs",
                    "participants": ["brief-clerk"],
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "custom:brief_hash_identical",
                                "op": "==",
                                "value": True,
                                "value_type": "boolean",
                                "producer": "brief-clerk brief hash",
                            },
                            {
                                "metric": "custom:team_a_tokens_in_team_b_brief",
                                "op": "==",
                                "value": 0,
                                "value_type": "number",
                                "producer": "brief-clerk leakage scan",
                            },
                        ]
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "isolated-estimates",
                    "custom_name": "two_isolated_cells_run_in_parallel",
                    "participants": ["team-a-lead", "team-b-lead"],
                    "independent": True,
                },
                {
                    "kind": "custom",
                    "stage_id": "divergence-mapping",
                    "custom_name": "map_divergences_between_products",
                    "participants": ["divergence-analyst", "adjudication-chair"],
                    "quotas": {"objections_per_participant": 4},
                },
                {"kind": "jury", "stage_id": "adjudication", "rounds": 2},
                {"kind": "synthesis", "stage_id": "final-estimate"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 900},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                # Adjudication is only meaningful if each cell must first state the other cell's
                # estimate at its strongest, then answer it.
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 4, "runner": "ci"},
        },
        "budgets": {
            "effort": "max",
            "time_minutes": 480,
            "tool_calls": 600,
            "sources": 60,
            "experiments": 4,
            "turns": 70,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 3,
        },
        "targets": {
            "unique_ideas": 12,
            "novelty_ratio": 0.4,
            "coverage_score": 0.9,
            "objections": 10,
            "counterexamples": 4,
            "evidence_items": 40,
            "dedup": dedup_target(0.75),
        },
        "voting": {
            "method": "judge",
            "quorum": {"min_voters": 2, "on_failure": "escalate_to_owner"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
            },
            "belief_aggregation": {
                "method": "logarithmic_pool",
                "require_confidence_per_vote": True,
                "calibration_source": "estate run-record base rates",
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "owner",
        },
        "consensus": {
            "threshold": 0.85,
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {"metric": "subcouncils_complete", "op": ">=", "value": 2},
                    {
                        "metric": "custom:brief_hash_identical",
                        "op": "==",
                        "value": True,
                        "value_type": "boolean",
                        "producer": "brief-clerk brief hash",
                    },
                    {
                        "metric": "custom:team_a_tokens_in_team_b_brief",
                        "op": "==",
                        "value": 0,
                        "value_type": "number",
                        "producer": "brief-clerk leakage scan",
                    },
                    {
                        "metric": "custom:divergences_adjudicated_ratio",
                        "op": ">=",
                        "value": 1,
                        "value_type": "number",
                        "producer": "divergence-analyst divergence ledger",
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 2,
                "min_evidence_items": 30,
                "min_objections_addressed": 6,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 480,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "irreducible_disagreement",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "any unadjudicated divergence is re-run as a discriminating probe before the claim is cited"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": [
                "run_experiment",
                "recruit_independent_critic",
                "judge_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "strongest_counterexample",
                "recruit_independent_critic",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "evidence_map",
                "claim_evidence_contradiction_graph",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "calibration_report",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(
            retain_days=365, approvals=["merge", "release", "cite as ground truth"]
        ),
        "metadata": {
            "title": "P11 Team B competitive estimate",
            "spec_citations": [f"{DOC}:262", f"{DOC}:275"],
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P11",
                "US IC Team A / Team B 1976",
            ],
            "notes": notes(
                "ADVERSARIAL. Full independent RE-DERIVATION from raw sources, which is what "
                "separates it from a red team attacking an existing artifact. The two cells are "
                "real nested CouncilSpec instances under topology.subcouncils, each validated by "
                "the same schema and the same semantic rules; nesting is capped at one level.",
                defenses,
            ),
        },
    }


def p12() -> Dict[str, Any]:
    defenses = {
        "circular_debate": (
            "the disagreement is converted into a pre-registered discriminating probe; the "
            "pre-registration stage will not exit until custom:probe_preregistered == true, so the "
            "council cannot loop on restated positions"
        ),
        "endless_debate": (
            "stopping.expression's second branch accepts proof_of_impossibility - if no probe can "
            "be agreed, that is a valid terminal outcome rather than another round"
        ),
        "lost_dissent": (
            "the output is a JOINTLY OWNED document that must state what was settled AND what "
            "remains; consensus.minority_report=required and dissent_policy.preserve_verbatim"
        ),
        "weak_synthesis": (
            "voting.method=consent_no_objection means neither side can be overruled into a "
            "synthesis it does not own, and custom:jointly_owned_document == true is a closing "
            "precondition"
        ),
        "sycophancy": (
            "the probe is registered BEFORE either side sees a result "
            "(protocol.experiments.required_before_decision) so neither party can retrofit "
            "agreement to the outcome"
        ),
        "consensus_failing_executable_tests": (
            "experiments.runner=ci with experiments_run >= 1 in the stopping rule; the settlement "
            "is a run, not a concession"
        ),
    }
    return {
        "schema_version": "1.0.0",
        "council_id": "p12-adversarial-collaboration",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Convert an entrenched two-party disagreement into a runnable discriminating test, "
                "and record what it settled and what it did not."
            ),
            "charter": (
                "Adversarial collaboration (Kahneman / Mellers). The disagreeing seats jointly "
                "pre-register the probe whose result they both agree would settle it, run or "
                "specify it, then co-author ONE document."
            ),
            "risk_tier": "high",
            "desired_output": "specification",
            "success_criteria": [
                "the discriminating probe was written down before either side saw a result",
                "both seats signed the same document",
                "the document separates what was settled from what remains open",
            ],
            "consensus_intent": "surface_disagreement",
            "confidence_target": 0.8,
            "evidence_requirements": evidence_reqs(
                min_sources=2, anchor="command_output"
            ),
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 4, "min": 4, "max": 4},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 3},
            "roster": [
                {
                    "participant_id": "party-one",
                    "display_name": "Party 1 (holds position A)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["the contested claim"],
                    "role": "proposer",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                },
                {
                    "participant_id": "party-two",
                    "display_name": "Party 2 (holds position B)",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["the contested claim"],
                    "role": "critic",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                },
                {
                    "participant_id": "mediator",
                    "display_name": "Mediator (owns the pre-registration record)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["mediation", "pre-registration"],
                    "role": "mediator",
                    "authority": "chair",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "probe-runner",
                    "display_name": "Probe runner (executes the agreed probe)",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["experiment execution", "both-states testing"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                },
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["position_memo", "evidence_pack"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "state-positions",
                    "independent": True,
                    "participants": ["party-one", "party-two"],
                },
                {
                    "kind": "negotiation",
                    "stage_id": "preregister",
                    "rounds": 2,
                    "quotas": {"ideas_per_participant": 3, "novel_ideas_per_round": 1},
                    "exit_when": {
                        "any_of": [
                            {
                                "metric": "custom:probe_preregistered",
                                "op": "==",
                                "value": True,
                                "value_type": "boolean",
                                "producer": "mediator pre-registration record",
                            },
                            {
                                "metric": "proof_of_impossibility",
                                "op": "==",
                                "value": True,
                            },
                        ]
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "run-probe",
                    "custom_name": "run_preregistered_discriminating_probe",
                    "participants": ["probe-runner"],
                },
                {
                    "kind": "mediation",
                    "stage_id": "co-author",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 2},
                },
                {"kind": "synthesis", "stage_id": "joint-document"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 7, "divergence_before_convergence": True},
            "turn": {"max_words": 700},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                # This is collaboration, not a contest - the card lists P07/P08 as CONFLICTING
                # protocols - so there is deliberately no cross-examination stage.
                "cross_examination": False,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 5,
                "runner": "ci",
            },
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 180,
            "tool_calls": 220,
            "sources": 25,
            "experiments": 5,
            "turns": 32,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 10,
            "novelty_ratio": 0.5,
            "objections": 6,
            "counterexamples": 3,
            "evidence_items": 16,
            "dedup": dedup_target(),
        },
        "voting": {
            "method": "consent_no_objection",
            "quorum": {"min_voters": 2, "on_failure": "no_decision"},
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "threshold": 1,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": dissent_policy(1),
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "expression": {
                "any_of": [
                    {
                        "all_of": [
                            {
                                "metric": "custom:probe_preregistered",
                                "op": "==",
                                "value": True,
                                "value_type": "boolean",
                                "producer": "mediator pre-registration record",
                            },
                            {"metric": "experiments_run", "op": ">=", "value": 1},
                            {
                                "metric": "custom:jointly_owned_document",
                                "op": "==",
                                "value": True,
                                "value_type": "boolean",
                                "producer": "mediator co-authorship signature block",
                            },
                            {
                                "metric": "every_objection_addressed",
                                "op": "==",
                                "value": True,
                            },
                        ]
                    },
                    {"metric": "proof_of_impossibility", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 2,
                "every_participant_spoke": True,
                "min_evidence_items": 10,
                "min_objections_addressed": 3,
            },
            "hard_caps": {
                "max_rounds": 7,
                "max_minutes": 180,
                "on_cap": "conditional_decision",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "irreducible_disagreement",
                "proof_of_impossibility",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the pre-registered probe is executed in CI and its result is attached to the joint document"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "circular_citation_check": True,
            },
            "resolution": [
                "run_experiment",
                "narrow_scope",
                "split_question",
                "recruit_independent_critic",
                "declare_no_decision",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": list(defenses),
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "strongest_counterexample",
                "forced_dissent",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_graph",
                "evidence_map",
                "experiments",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "resumable_state",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(retain_days=180),
        "metadata": {
            "title": "P12 adversarial collaboration",
            "spec_citations": [f"{DOC}:276", f"{DOC}:289"],
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P12",
                "Kahneman / Mellers adversarial collaboration",
            ],
            "notes": notes(
                "ADVERSARIAL. The output is a JOINTLY OWNED document plus a pre-registered "
                "discriminating test - every other adversarial protocol here produces separate "
                "products and a third-party verdict. The card's stated valid failure ('no probe "
                "can be agreed') is encoded as an allowed terminal outcome, "
                "proof_of_impossibility, not swept up as a deadlock.",
                defenses,
            ),
        },
    }


BUILDERS = [p01, p02, p03, p04, p05, p06, p07, p08, p09, p10, p11, p12]


# ------------------------------------------------------------------------ finalize


def _has_producer(node: Any) -> bool:
    """True if any leaf in the stopping tree declares a producer (SEM-012 satisfied)."""
    if isinstance(node, Mapping):
        if "producer" in node:
            return True
        return any(_has_producer(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_producer(v) for v in node)
    return False


def _finalize(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Derive source_expression from the tree and assert the unit brief's own floors."""
    # SEM-001 requires parse(source_expression) == stopping.expression EXACTLY, and the
    # expression grammar has no surface syntax for a custom leaf's `producer`. Measured in
    # three states (probe: _probe_source_expression_conflict.py): producer + source_expression
    # -> SEM-001 ERROR; no producer + source_expression -> SEM-012 WARN and the "what computes
    # this metric" fact is lost; producer + no source_expression -> clean. source_expression is
    # OPTIONAL (stopping.required == ["expression"]), so it is emitted ONLY where it can be
    # proven faithful, and `producer` is never dropped to buy a decorative string.
    tree = spec["stopping"]["expression"]
    src = unparse(tree)
    if parse(src) == tree:
        spec["stopping"]["source_expression"] = src
    elif not _has_producer(tree):
        raise AssertionError(
            f"{spec['council_id']}: source_expression round trip failed for a reason other "
            f"than a custom-leaf producer: {src!r}"
        )

    controls = spec["anti_failure"]["controls"]
    if len(controls) < 3:
        raise AssertionError(
            f"{spec['council_id']}: only {len(controls)} anti-failure controls (need >= 3)"
        )
    if len(set(controls)) != len(controls):
        raise AssertionError(f"{spec['council_id']}: duplicate anti-failure control")
    mapped = [
        line.strip().split(" -> ")[0]
        for line in spec["metadata"]["notes"].splitlines()
        if " -> " in line
    ]
    if sorted(mapped) != sorted(controls):
        raise AssertionError(
            f"{spec['council_id']}: control->mechanism map {sorted(mapped)} does not cover "
            f"controls {sorted(controls)}"
        )
    if not spec["anti_failure"]["fast_unanimity_response"]:
        raise AssertionError(
            f"{spec['council_id']}: fast unanimity must trigger something concrete"
        )
    if not spec["consensus"]["fast_unanimity_is_suspicious"]:
        raise AssertionError(
            f"{spec['council_id']}: fast_unanimity_is_suspicious must be true"
        )
    return spec


def write_all(out_dir: str = OUT_DIR) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []
    for idx, builder in enumerate(BUILDERS, start=1):
        spec = _finalize(builder())
        # Filename convention matches the sibling protocol lanes already in this
        # directory (p37-pairwise-comparison.councilspec.json), so a reader can sort
        # the 48 protocols in one listing.
        assert spec["council_id"] == f"p{idx:02d}-{spec['council_id'].split('-', 1)[1]}"
        name = f"{spec['council_id']}.councilspec.json"
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(spec, fh, indent=2, ensure_ascii=True)
            fh.write("\n")
        written.append(path)
    return written


def main() -> int:
    written = write_all()
    bad = 0
    for path in written:
        with open(path, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
        serr = schema_errors(spec)
        sem = errors(check(spec)) if not serr else []
        state = "ok" if not serr and not sem else "BAD"
        if state == "BAD":
            bad += 1
            for line in serr[:6] + [str(f) for f in sem[:6]]:
                print(f"   {line}")
        print(f"{state:4s} {os.path.basename(path)}")
    print(f"wrote {len(written)} protocol specs to {OUT_DIR}")
    if bad:
        print(f"FAILED:build-p01-p12 {bad} spec(s) do not validate")
        return 1
    print("SUCCESS:build-p01-p12 12/12 written and self-validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
