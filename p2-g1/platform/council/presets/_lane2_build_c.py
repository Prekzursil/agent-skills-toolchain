"""Lane-2 preset builders, batch C: design indices 23-26 (C-S23 .. C-S26)."""

from __future__ import annotations

from typing import Any, Dict

from _lane2_build_a import FULL_OUTCOMES_MR, NO_IMPOSSIBILITY_MR
from _lane2_build_b import _agent
from _lane2_common import (
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
    audit,
    injection_defense,
    notes,
    outcomes,
)

WAR_ROOM_OUTCOMES = ["PROCEED", "MITIGATED", "DEFER"]


def p23_delphi_5_anon_3rounds() -> Dict[str, Any]:
    experts = [
        ("expert-1", "opus-5", "anthropic", "cost and effort modelling"),
        ("expert-2", "gpt-5-codex", "openai", "implementation effort"),
        ("expert-3", "gemini-3-pro", "google", "integration risk"),
        ("expert-4", "opus-5", "anthropic", "historical reference class"),
        ("expert-5", "gpt-5-codex", "openai", "operational load"),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s23-delphi-5-anon-3rounds",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Produce an estimate as a median with a reported spread, over three "
            "anonymous Delphi rounds.",
            "charter": "Anonymous Delphi. Between rounds the facilitator returns the OUTLIER "
            "RATIONALES, not just the spread - returning only the spread is what manufactures false "
            "convergence.",
            "risk_tier": "moderate",
            "desired_output": "forecast",
            "success_criteria": [
                "three rounds ran",
                "the final spread is reported alongside the median, never suppressed",
                "each round returned the outlier RATIONALES to the panel, not just the numbers",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.7,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": [
                _agent(
                    e[0],
                    f"Expert {e[0][-1]} ({e[3]})",
                    "domain_expert",
                    e[1],
                    e[2],
                    authority="voter",
                    effort="high",
                    expertise=[e[3]],
                    anonymous=True,
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                )
                for e in experts
            ]
            + [
                _agent(
                    "facilitator",
                    "Facilitator (returns outlier rationales between rounds)",
                    "facilitator",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="medium",
                    rights={"may_speak": True, "may_vote": False},
                )
            ],
            "anonymity": {"mode": "double_blind"},
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["benchmark_baseline"],
        },
        "topology": {"kind": "delphi", "chair": "facilitator"},
        "protocol": {
            "sequence": [
                {
                    "kind": "delphi_round",
                    "stage_id": "round-1",
                    "independent": True,
                    "anonymous": True,
                },
                {"kind": "delphi_round", "stage_id": "round-2", "anonymous": True},
                {"kind": "delphi_round", "stage_id": "round-3", "anonymous": True},
                {
                    "kind": "synthesis",
                    "stage_id": "median-and-spread",
                    "participants": ["facilitator"],
                },
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 3, "max": 5},
            "turn": {"max_words": 350},
            "obligations": {
                "declare_confidence": True,
                "must_cite_evidence": True,
                "forced_dissent": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 30,
            "turns": 21,
            "tool_calls": 60,
        },
        "targets": {"evidence_items": 10},
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 100},
            "quorum": {
                "min_voters": 4,
                "min_fraction": 0.6,
                "on_failure": "extend_rounds",
            },
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
                "calibration_source": "prior council calibration reports",
            },
            "abstention": {"allowed": False, "counts_toward_quorum": False},
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": False,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "source_expression": "rounds_elapsed >= 3 AND independent_positions >= 5",
            "expression": {
                "all_of": [
                    {"metric": "rounds_elapsed", "op": ">=", "value": 3},
                    {"metric": "independent_positions", "op": ">=", "value": 5},
                ]
            },
            "minimum_deliberation": {"min_rounds": 3, "min_independent_positions": 5},
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 30,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(NO_IMPOSSIBILITY_MR),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "vote_oscillation_rounds": 3},
            "resolution": [
                "forced_dissent",
                "recruit_independent_critic",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
        },
        "anti_failure": {
            "controls": [
                "premature_convergence",
                "echo_chamber",
                "lost_dissent",
                "minority_suppression",
                "strategic_voting",
                "prompt_injection",
            ],
            "fast_unanimity_response": ["forced_dissent", "blind_re_evaluation"],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "calibration_report",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=90,
            owner_approval_for=[],
            forbid_irreversible=True,
            calibration=True,
        ),
        "metadata": {
            "title": "Anonymous Delphi estimate (5 experts, 3 rounds)",
            "owner": "Prekzursil",
            "lineage": ["C-S23 delphi-5-anon-3rounds", "P20 delphi-anonymous-rounds"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1471-1484"],
            "notes": notes(
                card="C-S23 delphi-5-anon-3rounds",
                seats_declared=5,
                roles_line="domain_expert_x5,facilitator",
                preset_label_rationale="custom - forecasting_council is the adjacent required "
                "archetype but its natural card is C-D36 deep-prediction-tournament-12 (design index "
                "36, a different lane). Labelling this one forecasting_council would collide.",
                dials={
                    "$.protocol.rounds + $.stopping.expression rounds_elapsed": "rounds dial (3 is the card default)",
                    "$.participants.anonymity.mode": "anonymity_level dial: none|pseudonymous|blind_to_peers|double_blind",
                    "$.voting.belief_aggregation.method": "median (card) vs trimmed_mean vs linear_pool",
                    "$.voting.score_scale": "the estimate scale - change to the unit you are estimating in",
                },
                outcome_lineage=NO_IMPOSSIBILITY_MR,
                extra="consensus.minority_report is REQUIRED, so outcomes.allowed must contain "
                "minority_report or SEM-009 fails. It is present via MAJORITY_WITH_DISSENT->dissent "
                "plus an explicit minority_report entry appended by the builder.",
            ),
        },
    }


def p24_ach_5_hypotheses() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s24-ach-5-hypotheses",
        "preset": "root_cause_council",
        "participation": "agent_only",
        "objective": {
            "statement": "Find the root cause by Analysis of Competing Hypotheses: enumerate at least "
            "four hypotheses including one measurement-error hypothesis, then keep the one with the "
            "fewest inconsistencies.",
            "charter": "ACH root-cause council. Evidence that does not DISCRIMINATE between "
            "hypotheses is explicitly discarded as non-diagnostic. The hypothesis with the fewest "
            "inconsistencies wins - not the one with the most supporting evidence.",
            "risk_tier": "high",
            "desired_output": "root_cause",
            "success_criteria": [
                "at least four hypotheses were carried, one of which is a measurement-error hypothesis",
                "non-diagnostic evidence was explicitly discarded, not quietly counted as support",
                "the surviving hypothesis is the one with the fewest inconsistencies",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.8,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial", "vendor_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                _agent(
                    "methodologist",
                    "Methodologist (owns the ACH matrix)",
                    "custom:methodologist",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="xhigh",
                    expertise=["ACH", "diagnosticity"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
                _agent(
                    "expert-system",
                    "Domain expert (the system under investigation)",
                    "domain_expert",
                    "opus-5",
                    "anthropic",
                    expertise=["the failing system"],
                    source_access=["repo", "transcripts"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "expert-detector",
                    "Domain expert (the DETECTOR that produced the signal)",
                    "domain_expert",
                    "gpt-5-codex",
                    "openai",
                    expertise=["measurement", "detector validation"],
                    source_access=["repo", "transcripts"],
                    rights={"may_speak": True, "may_vote": True},
                    independence={"fresh_context": True},
                ),
                _agent(
                    "expert-environment",
                    "Domain expert (environment and shell)",
                    "domain_expert",
                    "gemini-3-pro",
                    "google",
                    expertise=["windows shell", "path and encoding"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "evidence-clerk",
                    "Evidence clerk (holds the diagnosticity table)",
                    "custom:evidence_clerk",
                    "opus-5",
                    "anthropic",
                    authority="voter",
                    expertise=["evidence custody"],
                    source_access=["repo", "internal_docs"],
                    rights={"may_speak": True, "may_vote": True},
                ),
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {"kind": "chair_led", "chair": "methodologist"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "hypotheses",
                    "independent": True,
                    "quotas": {"ideas_per_participant": 2},
                },
                {
                    "kind": "custom",
                    "stage_id": "diagnosticity",
                    "custom_name": "score each evidence item for diagnosticity; discard non-diagnostic",
                    "participants": ["evidence-clerk", "methodologist"],
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "inconsistency-hunt",
                    "rounds": 2,
                },
                {"kind": "synthesis", "stage_id": "surviving-hypothesis"},
            ],
            "speaking_order": "lowest_confidence_first",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "declare_confidence": True,
                "steelman_before_rebuttal": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 6, "runner": "local"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 45,
            "tool_calls": 180,
            "sources": 25,
            "turns": 30,
            "experiments": 6,
            "rebuttal_depth": 3,
        },
        "targets": {"evidence_items": 12, "counterexamples": 4, "coverage_score": 0.9},
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 10},
            "quorum": {"min_voters": 4, "on_failure": "extend_rounds"},
            "belief_aggregation": {
                "method": "calibration_weighted",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.8,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "source_expression": "independent_positions >= 4 AND evidence_items >= 12 AND coverage_score >= 0.9",
            "expression": {
                "all_of": [
                    {"metric": "independent_positions", "op": ">=", "value": 4},
                    {"metric": "evidence_items", "op": ">=", "value": 12},
                    {"metric": "coverage_score", "op": ">=", "value": 0.9},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "min_evidence_items": 12,
                "min_objections_addressed": 4,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 45,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": outcomes(
            FULL_OUTCOMES_MR,
            ["the surviving hypothesis names the probe that would refute it"],
        ),
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "circular_citation_check": True,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "blind_re_evaluation",
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
            "controls": [
                "evidence_free_majority",
                "premature_convergence",
                "instant_unanimity",
                "circular_citation",
                "lost_dissent",
                "hallucinated_expertise",
                "prompt_injection",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "strongest_counterexample",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "experiments",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=180,
            owner_approval_for=["merge"],
            forbid_irreversible=True,
            calibration=True,
        ),
        "metadata": {
            "title": "ACH root-cause council (5 seats, >=4 hypotheses)",
            "owner": "Prekzursil",
            "lineage": [
                "C-S24 ach-5-hypotheses",
                "P38 analysis-of-competing-hypotheses",
                "P40 quality-of-information-check",
            ],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1485-1499"],
            "notes": notes(
                card="C-S24 ach-5-hypotheses",
                seats_declared=5,
                roles_line="methodologist,domain_expert_x3,evidence_clerk",
                preset_label_rationale="root_cause_council - exact archetype match.",
                dials={
                    "$.stopping.expression independent_positions": "hypothesis_floor dial (card default 4)",
                    "$.stopping.expression coverage_score + $.targets.coverage_score": "diagnosticity_threshold dial",
                    "$.protocol.speaking_order": "lowest_confidence_first is deliberate - it stops the "
                    "most confident seat from anchoring the matrix",
                },
                outcome_lineage=FULL_OUTCOMES_MR,
                extra="CALIBRATION CASE from the card: this council must rank 'the machine was powered "
                "off' ABOVE 'the feed is broken' on R-01. That is why one of the three domain experts "
                "is scoped to the DETECTOR rather than the system - a measurement-error hypothesis has "
                "no advocate unless a seat owns it.",
            ),
        },
    }


def p25_war_room_5_incident() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s25-war-room-5-incident",
        "preset": "incident_war_room",
        "participation": "hybrid",
        "objective": {
            "statement": "Mitigate a live incident. Entry requires a NAMED failing detector; exit "
            "requires that detector green or an explicit commander stand-down.",
            "charter": "Incident war room. The commander decides unilaterally - this is not a "
            "deliberative body. Deliberation cost during an incident is measured in downtime.",
            "risk_tier": "critical",
            "desired_output": "decision",
            "success_criteria": [
                "entry named a specific failing detector, not a vague symptom",
                "the named detector went green, or the commander explicitly stood the room down",
                "a postmortem id was scheduled at OPEN, not at close",
            ],
            "consensus_intent": "adjudicate",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "command_output",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": False,
                "forbidden_actions": [
                    "force-push to main",
                    "credential rotation",
                    "irreversible data deletion",
                ],
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_expertise": 4},
            "roster": [
                _agent(
                    "commander",
                    "Incident commander (decides unilaterally)",
                    "custom:incident_commander",
                    "opus-5",
                    "anthropic",
                    authority="judge",
                    effort="xhigh",
                    expertise=["incident command"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                        "may_recruit": True,
                    },
                ),
                _agent(
                    "sre",
                    "SRE (mitigation and rollback)",
                    "custom:sre",
                    "opus-5",
                    "anthropic",
                    authority="contributor",
                    effort="xhigh",
                    expertise=["rollback", "observability"],
                    source_access=["repo", "transcripts"],
                    rights={
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                ),
                _agent(
                    "security",
                    "Security (blast radius and exposure)",
                    "security_reviewer",
                    "gpt-5-codex",
                    "openai",
                    authority="veto_holder",
                    effort="high",
                    expertise=["blast radius", "secret exposure"],
                    rights={"may_speak": True, "may_vote": False, "may_veto": True},
                ),
                _agent(
                    "scribe",
                    "Scribe (timeline with timestamps)",
                    "scribe",
                    "opus-5",
                    "anthropic",
                    authority="observer",
                    effort="medium",
                    rights={"may_speak": True, "may_vote": False},
                ),
                {
                    "participant_id": "comms",
                    "display_name": "Comms (owner-facing status, human)",
                    "kind": "human",
                    "vendor": "human",
                    "role": "custom:comms",
                    "authority": "observer",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "role_collapse"],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": False,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": False,
            "independent_prep": False,
            "required_artifacts": ["evidence_pack"],
        },
        "topology": {"kind": "chair_led", "chair": "commander"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "entry-gate",
                    "custom_name": "name the failing detector and schedule the postmortem id",
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "evidence_items",
                                "op": ">=",
                                "value": 1,
                                "note": "the named failing detector output - entry is refused without it",
                            },
                            {
                                "metric": "quality_gate",
                                "op": "!=",
                                "value": "NOT_CHECKED",
                                "note": "an unrun detector cannot open a war room",
                            },
                        ]
                    },
                },
                {"kind": "war_game", "stage_id": "mitigate"},
                {
                    "kind": "synthesis",
                    "stage_id": "stand-down",
                    "participants": ["commander", "scribe"],
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 1, "max": 48},
            "turn": {"max_words": 250, "time_limit_seconds": 60},
            "obligations": {"must_cite_evidence": True, "declare_confidence": True},
            "critique_intensity": "standard",
            "experiments": {"allowed": True, "max_experiments": 40, "runner": "local"},
        },
        "budgets": {
            "effort": "max",
            "tool_calls": 600,
            "turns": 200,
            "max_inactivity_rounds": 1,
            "min_engagement_turns": 1,
        },
        "targets": {"evidence_items": 6},
        "voting": {
            "method": "judge",
            "quorum": {"min_voters": 1, "on_failure": "escalate_to_owner"},
            "veto": {
                "holders": ["security"],
                "scope": "safety_only",
                "must_justify": True,
                "overridable_by_owner": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
        },
        "stopping": {
            "source_expression": "quality_gate == PASS OR owner_approved == true",
            "expression": {
                "any_of": [
                    {"metric": "quality_gate", "op": "==", "value": "PASS"},
                    {"metric": "owner_approved", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {"min_rounds": 1, "min_evidence_items": 1},
            "hard_caps": {"max_rounds": 48, "on_cap": "escalate_to_owner"},
        },
        "outcomes": outcomes(
            WAR_ROOM_OUTCOMES,
            ["the mitigation is reversible and its rollback is named"],
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 3},
            "resolution": ["run_experiment", "chair_ruling", "escalate_to_owner"],
            "escalation": {"after_attempts": 1, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "moderator_capture",
                "evidence_free_majority",
                "silence",
                "consensus_failing_executable_tests",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "transcript",
                "evidence_map",
                "experiments",
                "action_plan",
                "resumable_state",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=365,
            owner_approval_for=["release"],
            forbid_irreversible=True,
            determinism="best_effort",
        ),
        "metadata": {
            "title": "Incident war room (commander + 4)",
            "owner": "Prekzursil",
            "lineage": ["C-S25 war-room-5-incident", "P47 incident-war-room"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1500-1514"],
            "notes": notes(
                card="C-S25 war-room-5-incident",
                seats_declared=5,
                roles_line="incident_commander,sre,security,scribe,comms",
                preset_label_rationale="incident_war_room - exact archetype match.",
                dials={
                    "$.participants.roster[0]": "commander dial - who holds unilateral authority",
                    "$.protocol.turn.time_limit_seconds": "heartbeat dial (card default 60s)",
                    "$.stopping.expression": "the exit condition. quality_gate == PASS is the named "
                    "detector going green; owner_approved == true is the commander stand-down",
                    "$.protocol.rounds.max + $.stopping.hard_caps.max_rounds": "the card says wall "
                    "time is UNBOUNDED; an unbounded council cannot be expressed, so 48 heartbeat "
                    "rounds is a stand-in cap that escalates to the owner rather than deciding",
                },
                outcome_lineage=WAR_ROOM_OUTCOMES,
                extra="DEVIATION FROM CARD (disclosed): the card says rounds:0 and wall<=unbounded. "
                "The schema has no unbounded form, and stopping.hard_caps.on_cap must name a "
                "behaviour, so this instance uses 48 rounds with on_cap=escalate_to_owner. That is a "
                "cap the owner sees, not a decision the council makes. "
                "The card's 'binding' default is expressed as voting.method=judge with the commander "
                "as the sole judge - there is no unilateral method in the schema enum.",
            ),
        },
    }


def p26_postmortem_5_blameless() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s26-postmortem-5-blameless",
        "preset": "postmortem_council",
        "participation": "agent_only",
        "objective": {
            "statement": "Reconstruct a blameless causal chain for a closed incident and enumerate "
            "the full blast radius.",
            "charter": "Blameless postmortem. Every causal link must cite a TIMESTAMPED artifact. A "
            "link asserted from memory is not a link. Blast radius means every file, commit, index "
            "entry and downstream consumer the bad change touched - not just the first symptom.",
            "risk_tier": "high",
            "desired_output": "root_cause",
            "success_criteria": [
                "every causal link cites a timestamped artifact",
                "the blast radius is enumerated, not summarised",
                "no seat is named as a cause; only mechanisms are",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.8,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 3,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                _agent(
                    "methodologist",
                    "Methodologist (owns the 5-whys causal chain)",
                    "custom:methodologist",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="xhigh",
                    expertise=["causal analysis", "5-whys"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "sre",
                    "SRE (timeline and telemetry)",
                    "custom:sre",
                    "opus-5",
                    "anthropic",
                    expertise=["telemetry", "timeline reconstruction"],
                    source_access=["repo", "transcripts"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "implementer",
                    "Implementer (what the change actually did)",
                    "custom:implementer",
                    "gpt-5-codex",
                    "openai",
                    expertise=["the changed subsystem"],
                    source_access=["repo"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "security",
                    "Security (blast radius and exposure)",
                    "security_reviewer",
                    "gemini-3-pro",
                    "google",
                    expertise=["blast radius", "exposure"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "scribe",
                    "Scribe (blameless write-up)",
                    "scribe",
                    "opus-5",
                    "anthropic",
                    authority="observer",
                    effort="medium",
                    rights={"may_speak": True, "may_vote": False},
                ),
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "required_artifacts": ["evidence_pack", "risk_list"],
        },
        "topology": {"kind": "chair_led", "chair": "methodologist"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "timeline",
                    "custom_name": "timestamped timeline reconstruction",
                    "participants": ["sre", "scribe"],
                },
                {
                    "kind": "custom",
                    "stage_id": "five-whys",
                    "custom_name": "5-whys causal chain, each link artifact-backed",
                },
                {
                    "kind": "custom",
                    "stage_id": "blast-radius",
                    "custom_name": "enumerate every touched file, commit, index entry and consumer",
                    "participants": ["security", "implementer"],
                },
                {"kind": "premortem", "stage_id": "recurrence-check"},
                {"kind": "synthesis", "stage_id": "write-up"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 6},
            "turn": {"max_words": 700},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "declare_confidence": True,
            },
            "critique_intensity": "standard",
            "experiments": {"allowed": True, "max_experiments": 4, "runner": "local"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 60,
            "tool_calls": 200,
            "sources": 30,
            "turns": 30,
            "experiments": 4,
        },
        "targets": {"evidence_items": 20, "coverage_score": 0.9, "objections": 6},
        "voting": {
            "method": "consent_no_objection",
            "quorum": {"min_voters": 4, "on_failure": "extend_rounds"},
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": True,
                "must_justify": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.9,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": False,
        },
        "stopping": {
            "source_expression": "evidence_items >= 10 AND coverage_score >= 0.9 AND "
            "every_objection_addressed == true",
            "expression": {
                "all_of": [
                    {"metric": "evidence_items", "op": ">=", "value": 10},
                    {"metric": "coverage_score", "op": ">=", "value": 0.9},
                    {"metric": "every_objection_addressed", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_evidence_items": 10,
                "min_objections_addressed": 4,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 60,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(
            FULL_OUTCOMES_MR,
            ["every remediation item has a named owner and a falsifiable check"],
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": [
                "run_experiment",
                "split_question",
                "chair_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": [
                "evidence_free_majority",
                "weak_synthesis",
                "lost_dissent",
                "circular_citation",
                "premature_convergence",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "transcript",
                "dissent_minority_report",
                "unresolved_unknowns",
                "action_plan",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=365, owner_approval_for=["merge"], forbid_irreversible=True
        ),
        "metadata": {
            "title": "Blameless postmortem council (5 seats)",
            "owner": "Prekzursil",
            "lineage": ["C-S26 postmortem-5-blameless", "P44 postmortem-5whys-causal"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1515-1528"],
            "notes": notes(
                card="C-S26 postmortem-5-blameless",
                seats_declared=5,
                roles_line="methodologist,sre,implementer,security,scribe",
                preset_label_rationale="postmortem_council - exact archetype match.",
                dials={
                    "$.protocol.sequence[1]": "why_depth dial - the 5-whys stage; deepen by raising "
                    "$.protocol.rounds.min",
                    "$.protocol.sequence[2] + $.targets.coverage_score": "blast_radius_scope dial",
                    "$.stopping.expression evidence_items": "how many timestamped artifacts the "
                    "causal chain must cite before the council may close",
                },
                outcome_lineage=FULL_OUTCOMES_MR,
                extra="fast_unanimity_is_suspicious is FALSE here on purpose: the card records "
                "anti-sycophancy as off, because a postmortem reconstructing a settled fact SHOULD "
                "converge fast. Arming it would manufacture disagreement about a known timeline.",
            ),
        },
    }
