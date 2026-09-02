"""Lane-2 preset builders, batch D: design indices 27-30 (C-S27 .. C-S30)."""

from __future__ import annotations

from typing import Any, Dict

from _lane2_build_a import FULL_OUTCOMES, FULL_OUTCOMES_MR, NO_IMPOSSIBILITY
from _lane2_build_b import _agent
from _lane2_common import (
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
    audit,
    injection_defense,
    notes,
    outcomes,
)

TWO_KEY_OUTCOMES = ["AUTHORISE", "DENY"]


def p27_kill_the_company_5() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s27-kill-the-company-5",
        "preset": "risk_committee",
        "participation": "hybrid",
        "objective": {
            "statement": "Produce a ranked risk register for the harness by enumerating at least "
            "eight concrete attacks on it, each naming a real file, task or config.",
            "charter": "Kill-the-company review, quarterly cadence. An attack that does not name a "
            "concrete file, scheduled task or config key is not an attack, it is a worry. Ranking is "
            "by CHEAPNESS of the attack, not by severity - a cheap attack is the one that happens.",
            "risk_tier": "moderate",
            "desired_output": "risk_register",
            "success_criteria": [
                "at least eight attacks, each naming a concrete file, task or config key",
                "at least one attack maps to a real incident that already happened on this estate",
                "attacks are ranked by cheapness of execution, not by imagined severity",
            ],
            "consensus_intent": "surface_disagreement",
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
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 3},
            "roster": [
                _agent(
                    "red-1",
                    "Red 1 (harness config and hooks)",
                    "red_team",
                    "opus-5",
                    "anthropic",
                    authority="voter",
                    expertise=["hooks", "settings and scopes"],
                    source_access=["repo", "internal_docs"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "red-2",
                    "Red 2 (scheduled tasks and daemons)",
                    "red_team",
                    "gpt-5-codex",
                    "openai",
                    authority="voter",
                    expertise=["scheduled tasks", "daemons"],
                    source_access=["repo"],
                    rights={"may_speak": True, "may_vote": True},
                    independence={"fresh_context": True},
                ),
                _agent(
                    "red-3",
                    "Red 3 (supply chain and untrusted checkouts)",
                    "red_team",
                    "gemini-3-pro",
                    "google",
                    authority="voter",
                    expertise=["supply chain", "untrusted repo admission"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                _agent(
                    "sre",
                    "SRE (which attacks are cheap in practice)",
                    "custom:sre",
                    "opus-5",
                    "anthropic",
                    authority="voter",
                    expertise=["operations", "recovery cost"],
                    rights={"may_speak": True, "may_vote": True},
                ),
                {
                    "participant_id": "owner-rep",
                    "display_name": "Owner representative (human)",
                    "kind": "human",
                    "vendor": "human",
                    "role": "custom:owner_rep",
                    "authority": "owner",
                    "expertise": ["owner intent", "real incident history"],
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
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
            "required_artifacts": ["risk_list", "prior_art_scan"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "brainstorm",
                    "stage_id": "attack-enumeration",
                    "independent": True,
                    "quotas": {
                        "ideas_per_participant": 3,
                        "objections_per_participant": 3,
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "cheapness-ranking",
                    "custom_name": "rank each attack by cost to execute, cheapest first",
                },
                {"kind": "synthesis", "stage_id": "risk-register"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {"must_cite_evidence": True, "declare_confidence": True},
            "critique_intensity": "adversarial",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 45,
            "tool_calls": 150,
            "sources": 25,
            "turns": 24,
        },
        "targets": {
            "counterexamples": 8,
            "objections": 12,
            "unique_ideas": 12,
            "evidence_items": 12,
        },
        "voting": {
            "method": "ranked_choice",
            "quorum": {"min_voters": 3, "on_failure": "extend_rounds"},
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
            },
            "tie_break": "owner",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "pairwise_agreement",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
        },
        "stopping": {
            "expression": {
                "all_of": [
                    {
                        "metric": "counterexamples_found",
                        "op": ">=",
                        "value": 8,
                        "note": "eight ATTACKS, each naming a concrete file, task or config key",
                    },
                    {
                        "metric": "custom:attacks_mapped_to_real_incident",
                        "op": ">=",
                        "value": 1,
                        "value_type": "number",
                        "producer": "the owner representative, cross-checking the attack list against "
                        "the event ledger and basic-memory incident notes",
                        "note": "at least one attack must map to something that ALREADY happened here; "
                        "a register of hypotheticals has never predicted an incident on this estate",
                    },
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_evidence_items": 8,
                "min_independent_positions": 4,
            },
            "hard_caps": {
                "max_rounds": 4,
                "max_minutes": 45,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(NO_IMPOSSIBILITY),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.85},
            "resolution": [
                "recruit_independent_critic",
                "narrow_scope",
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
                "idea_count_gaming",
                "duplicate_novelty",
                "evidence_free_majority",
                "echo_chamber",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "idea_catalog",
                "option_cards",
                "evidence_map",
                "votes_by_round",
                "action_plan",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=365, owner_approval_for=[], forbid_irreversible=True
        ),
        "metadata": {
            "title": "Kill-the-company risk committee (5 seats, quarterly)",
            "owner": "Prekzursil",
            "lineage": ["C-S27 kill-the-company-5", "P48 kill-the-company"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1529-1543"],
            "notes": notes(
                card="C-S27 kill-the-company-5",
                seats_declared=5,
                roles_line="red_team_x3,sre,owner_rep",
                preset_label_rationale="risk_committee - the card's desired output IS a ranked risk "
                "register, which is what the risk_committee archetype produces. The kill-the-company "
                "framing is the METHOD, not a different archetype.",
                dials={
                    "$.stopping.expression counterexamples_found + $.targets.counterexamples": "attack_floor dial (card default 8)",
                    "$.stopping.expression custom:attacks_mapped_to_real_incident": "raise to demand "
                    "more attacks grounded in real history",
                    "$.protocol.sequence[0].quotas.ideas_per_participant": "attacks demanded per red seat",
                },
                outcome_lineage=NO_IMPOSSIBILITY,
                extra="NO source_expression HERE, AND THIS IS A SUBSTRATE LIMIT, NOT AN OVERSIGHT: "
                "this is the only preset in the lane that uses a custom: metric with a declared "
                "producer. councilspec.expression.parse() cannot emit a 'producer' key, so SEM-001 "
                "(source_expression must parse to the IDENTICAL tree) fails for any expression "
                "carrying one. The human form is: "
                "counterexamples_found >= 8 AND custom:attacks_mapped_to_real_incident >= 1. "
                "Dropping 'producer' would restore source_expression but trade a SEM-012 warning "
                "(nothing in the run computes the metric) for it. Measured both ways; see "
                "LANE-2-STATUS.json finding F-P2-01.",
            ),
        },
    }


def p28_stakeholder_negotiation_5() -> Dict[str, Any]:
    stakeholders = [
        (
            "stake-1",
            "Stakeholder 1 (delivery speed)",
            "opus-5",
            "anthropic",
            "delivery",
        ),
        (
            "stake-2",
            "Stakeholder 2 (reliability)",
            "gpt-5-codex",
            "openai",
            "reliability",
        ),
        (
            "stake-3",
            "Stakeholder 3 (cost and quota)",
            "gemini-3-pro",
            "google",
            "budget",
        ),
        (
            "stake-4",
            "Stakeholder 4 (the end user)",
            "opus-5",
            "anthropic",
            "user outcomes",
        ),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s28-stakeholder-negotiation-5",
        "preset": "negotiation_council",
        "participation": "hybrid",
        "objective": {
            "statement": "Allocate a contested resource across stakeholders, where every stakeholder "
            "has stated a BATNA and no proposal is admitted without a stated concession.",
            "charter": "Stakeholder negotiation. A proposal with no concession is a demand; the "
            "facilitator refuses it. A stakeholder with no stated BATNA cannot be negotiated with, so "
            "the council cannot close until every seat has stated one.",
            "risk_tier": "moderate",
            "desired_output": "decision",
            "success_criteria": [
                "every stakeholder stated a BATNA (what they do if this fails)",
                "every proposal named the concession its proposer was making",
                "the allocation is expressed as numbers, not as intent",
            ],
            "consensus_intent": "seek_consensus",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
            },
            "owner_constraints": {"approval_required": True, "deadline_minutes": 40},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "stakeholder_balanced"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 4},
            "roster": [
                _agent(
                    s[0],
                    s[1],
                    "stakeholder",
                    s[2],
                    s[3],
                    authority="voter",
                    effort="high",
                    expertise=[s[4]],
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                )
                for s in stakeholders
            ]
            + [
                _agent(
                    "facilitator",
                    "Facilitator / mediator (refuses concession-free proposals)",
                    "mediator",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="high",
                    rights={"may_speak": True, "may_vote": False},
                )
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
            "required_artifacts": ["position_memo"],
        },
        "topology": {
            "kind": "caucus",
            "chair": "facilitator",
            "caucuses": [
                {
                    "caucus_id": "build-side",
                    "members": ["stake-1", "stake-4"],
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "run-side",
                    "members": ["stake-2", "stake-3"],
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "batna-declaration",
                    "custom_name": "every stakeholder states its BATNA before any proposal",
                    "independent": True,
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "all_participants_spoke",
                                "op": "==",
                                "value": True,
                                "note": "a silent stakeholder has no BATNA on record",
                            },
                            {
                                "metric": "independent_positions",
                                "op": ">=",
                                "value": 4,
                                "note": "one BATNA per stakeholder seat",
                            },
                        ]
                    },
                },
                {"kind": "negotiation", "stage_id": "bargaining", "rounds": 2},
                {
                    "kind": "mediation",
                    "stage_id": "mediate",
                    "participants": ["facilitator"],
                },
                {"kind": "synthesis", "stage_id": "allocation"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 5},
            "turn": {"max_words": 450},
            "obligations": {
                "must_respond_to_prior": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 40,
            "turns": 30,
            "tool_calls": 60,
        },
        "targets": {"objections": 6, "evidence_items": 8},
        "voting": {
            "method": "approval",
            "quorum": {
                "min_voters": 4,
                "min_fraction": 0.8,
                "on_failure": "escalate_to_owner",
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "owner",
        },
        "consensus": {
            "threshold": 0.75,
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 2,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "source_expression": "all_participants_spoke == true AND independent_positions >= 4",
            "expression": {
                "all_of": [
                    {"metric": "all_participants_spoke", "op": "==", "value": True},
                    {"metric": "independent_positions", "op": ">=", "value": 4},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "every_participant_spoke": True,
                "min_independent_positions": 4,
            },
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 40,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": outcomes(
            FULL_OUTCOMES,
            [
                "the allocation names numbers, and each stakeholder's concession is recorded"
            ],
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "vote_oscillation_rounds": 2},
            "resolution": [
                "split_question",
                "narrow_scope",
                "forced_dissent",
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
                "strategic_voting",
                "strategic_abstention",
                "participant_dominance",
                "instant_unanimity",
                "collusion",
                "hidden_conflict_of_interest",
                "prompt_injection",
            ],
            "fast_unanimity_response": ["forced_dissent", "blind_re_evaluation"],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "votes_by_round",
                "option_cards",
                "final_recommendation",
                "action_plan",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=180,
            owner_approval_for=["merge", "release"],
            forbid_irreversible=True,
        ),
        "metadata": {
            "title": "Stakeholder negotiation council (4 stakeholders + mediator)",
            "owner": "Prekzursil",
            "lineage": ["C-S28 stakeholder-negotiation-5", "P04 consensus-conference"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1544-1557"],
            "notes": notes(
                card="C-S28 stakeholder-negotiation-5",
                seats_declared=5,
                roles_line="stakeholder_x4,facilitator",
                preset_label_rationale="negotiation_council - exact archetype match for an allocation "
                "decision reached by bargaining. NOTE: stakeholder_user_panel is a SECOND required "
                "archetype that this same card could carry (four stakeholder seats plus a user "
                "advocate). It is NOT built here - one card cannot honestly be two presets. See "
                "LANE-2-STATUS.json coverage matrix; stakeholder_user_panel is reported as an "
                "unassigned archetype.",
                dials={
                    "$.participants.roster (the four stakeholder seats)": "stakeholders dial - who is at the table",
                    "$.protocol.obligations + $.protocol.sequence[0]": "concession_rule dial; the BATNA "
                    "stage is what makes the rule enforceable",
                    "$.voting.method": "approval (card default). ranked_choice if you need a strict order",
                    "$.consensus.dissent_policy.min_dissenters_to_block": "how many stakeholders can block",
                },
                outcome_lineage=FULL_OUTCOMES,
                extra="OWNER-DECISION: YES on this card, so objective.owner_constraints."
                "approval_required is true and voting.tie_break is 'owner'.",
            ),
        },
    }


def p29_two_key_authorization() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s29-two-key-authorization",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Authorize one irreversible action only if two independent authorities, "
            "briefed separately, both authorize the IDENTICAL action hash.",
            "charter": "Two-key dual control. There is NO tie-break: a single AUTHORISE must not open "
            "the gate. The two authorities get no shared brief, so their provenance differs; if they "
            "authorize different hashes, that is a DENY, not a disagreement to resolve.",
            "risk_tier": "critical",
            "desired_output": "go_no_go",
            "success_criteria": [
                "both authorities authorized, and both named the SAME action hash",
                "neither authority saw the other's brief before authorizing",
                "the deny path was proven too: one AUTHORISE alone left the gate shut",
            ],
            "consensus_intent": "adjudicate",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "command_output",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": True,
                "deadline_minutes": 15,
                "forbidden_actions": [
                    "proceeding on a single authorization",
                    "re-briefing an authority to change its vote",
                ],
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "vendor_diverse"],
                "explain_choices": True,
                "owner_override_allowed": False,
            },
            "count": {"mode": "exact", "exact_n": 2, "min": 2, "max": 2},
            "diversity": {"min_distinct_vendors": 2, "max_share_per_vendor": 0.5},
            "roster": [
                _agent(
                    "authority-a",
                    "Authority A (Claude side)",
                    "custom:authorizer",
                    "opus-5",
                    "anthropic",
                    authority="voter",
                    effort="xhigh",
                    expertise=["the action under authorization"],
                    source_access=["repo"],
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                    context={"partition_id": "brief-a"},
                ),
                _agent(
                    "authority-b",
                    "Authority B (Codex side)",
                    "custom:authorizer",
                    "gpt-5-codex",
                    "openai",
                    authority="voter",
                    effort="xhigh",
                    expertise=["the action under authorization"],
                    source_access=["repo"],
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                    context={"partition_id": "brief-b"},
                ),
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "disjoint_evidence",
                "partitions": [
                    {
                        "partition_id": "brief-a",
                        "visible_to": ["authority-a"],
                        "sources": ["the change itself", "its rollback path"],
                    },
                    {
                        "partition_id": "brief-b",
                        "visible_to": ["authority-b"],
                        "sources": ["the change itself", "its blast radius"],
                    },
                ],
            },
            "conflicts_policy": {"disclosure_required": True, "on_conflict": "exclude"},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["model", "vendor", "prompt"],
                "max_similarity": 0.5,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["evidence_pack"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "independent-authorization",
                    "independent": True,
                    "anonymous": False,
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "participants_active",
                                "op": "==",
                                "value": 2,
                                "note": "both authorities must have answered; a missing answer is not a DENY, it is a stall",
                            },
                            {
                                "metric": "quorum_met",
                                "op": "==",
                                "value": True,
                                "note": "quorum here is literally both keys",
                            },
                        ]
                    },
                },
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 1, "max": 1},
            "turn": {"max_words": 400},
            "obligations": {
                "must_cite_evidence": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
            "experiments": {
                "allowed": True,
                "max_experiments": 2,
                "required_before_decision": True,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "xhigh",
            "time_minutes": 15,
            "turns": 4,
            "tool_calls": 40,
            "experiments": 2,
        },
        "targets": {"evidence_items": 4},
        "voting": {
            "method": "unanimity",
            "quorum": {
                "min_voters": 2,
                "min_fraction": 1.0,
                "on_failure": "no_decision",
            },
            "abstention": {"allowed": False, "counts_toward_quorum": False},
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "threshold": 1.0,
            "measure": "vote_share",
            "minority_report": "forbidden",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
            "irreducible_disagreement_allowed": False,
            "fast_unanimity_is_suspicious": False,
        },
        "stopping": {
            "source_expression": "unanimity == true AND quorum_met == true",
            "expression": {
                "all_of": [
                    {"metric": "unanimity", "op": "==", "value": True},
                    {"metric": "quorum_met", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 1,
                "min_independent_positions": 2,
                "every_participant_spoke": True,
                "min_evidence_items": 2,
            },
            "hard_caps": {"max_rounds": 1, "max_minutes": 15, "on_cap": "no_decision"},
        },
        "outcomes": outcomes(TWO_KEY_OUTCOMES),
        "deadlock": {
            "detection": {"no_progress_rounds": 1},
            "resolution": ["declare_no_decision"],
            "escalation": {"after_attempts": 1, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "collusion",
                "strategic_voting",
                "evidence_free_majority",
                "hidden_conflict_of_interest",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "votes_by_round",
                "experiments",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=365,
            owner_approval_for=["merge", "release"],
            forbid_irreversible=True,
            determinism="deterministic_where_possible",
        ),
        "metadata": {
            "title": "Two-key authorization for an irreversible action",
            "owner": "Prekzursil",
            "lineage": ["C-S29 two-key-authorization", "P18 two-key-dual-control"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1558-1572"],
            "notes": notes(
                card="C-S29 two-key-authorization",
                seats_declared=2,
                roles_line="authority_a@claude,authority_b@codex",
                preset_label_rationale="custom - authorize_irreversible is not one of the 24 required "
                "archetypes.",
                dials={
                    "$.participants.roster": "authorities dial - WHO holds the two keys. Keep the two "
                    "vendors distinct: same-vendor keys share failure modes and the control degenerates",
                    "$.participants.information_partition.partitions": "action_hash / brief dial - the "
                    "card's 'no shared brief' rule is enforced HERE, not by prose",
                    "$.voting.method + $.voting.tie_break": "logical AND. DO NOT set a tie_break other "
                    "than no_decision: a tie-break IS the single-key bypass the card forbids",
                },
                outcome_lineage=TWO_KEY_OUTCOMES,
                extra="MAPPING NOTE: the card's voting rule is logical_AND. The schema enum has no "
                "such method; unanimity with quorum.min_fraction 1.0, abstention forbidden and "
                "tie_break=no_decision is the same predicate over exactly two voters. "
                "The card also demands the DENY path be both-states tested - that belongs to the "
                "engine's test suite, not to this instance, and is recorded in "
                "objective.success_criteria so a receipt cannot claim done without it.",
            ),
        },
    }


def p30_rfc_last_call_open() -> Dict[str, Any]:
    reviewers = [
        ("reviewer-1", "opus-5", "anthropic", "rules and contracts"),
        ("reviewer-2", "gpt-5-codex", "openai", "schemas"),
        ("reviewer-3", "gemini-3-pro", "google", "harness behaviour"),
        ("reviewer-4", "opus-5", "anthropic", "security posture"),
        ("reviewer-5", "gpt-5-codex", "openai", "downstream consumers"),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s30-rfc-last-call-open",
        "preset": "custom",
        "participation": "hybrid",
        "objective": {
            "statement": "Publish a durable artifact (a rule, schema, contract or AGENTS.md edit) only "
            "after every comment raised in the last-call window has an explicit disposition.",
            "charter": "RFC last call. Every comment gets a disposition - accepted, rejected, or "
            "deferred - and every REJECTED comment gets its own distinct reason string. A reused "
            "boilerplate rejection is not a disposition.",
            "risk_tier": "moderate",
            "desired_output": "specification",
            "success_criteria": [
                "comment count equals disposition count",
                "every rejected comment has a DISTINCT reason string, not a repeated boilerplate",
                "the window closed on time rather than being extended to exhaust objections",
            ],
            "consensus_intent": "seek_consensus",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 1,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": [
                _agent(
                    "editor",
                    "Editor (owns the dispositions)",
                    "custom:editor",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="high",
                    expertise=["the artifact under review"],
                    rights={"may_speak": True, "may_vote": True},
                ),
            ]
            + [
                _agent(
                    r[0],
                    f"Reviewer {r[0][-1]} ({r[3]})",
                    "critic",
                    r[1],
                    r[2],
                    authority="voter",
                    effort="high",
                    expertise=[r[3]],
                    source_access=["repo", "internal_docs"],
                    rights={"may_speak": True, "may_vote": True},
                )
                for r in reviewers
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
            "required_artifacts": ["prior_art_scan"],
        },
        "topology": {"kind": "chair_led", "chair": "editor"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "last-call-window",
                    "custom_name": "open comment window; anyone may object",
                    "quotas": {"objections_per_participant": 3},
                },
                {
                    "kind": "custom",
                    "stage_id": "disposition",
                    "custom_name": "editor dispositions every comment with a distinct reason",
                    "participants": ["editor"],
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "objections_open",
                                "op": "==",
                                "value": 0,
                                "note": "comments == dispositions; an open comment blocks publication",
                            },
                            {
                                "metric": "every_objection_addressed",
                                "op": "==",
                                "value": True,
                                "note": "addressed means dispositioned, NOT agreed with",
                            },
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "publish"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 3},
            "turn": {"max_words": 500},
            "obligations": {"must_cite_evidence": True, "must_respond_to_prior": True},
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "turns": 24,
            "tool_calls": 100,
        },
        "targets": {"objections": 8, "evidence_items": 10, "coverage_score": 0.9},
        "voting": {
            "method": "consent_no_objection",
            "quorum": {"min_voters": 4, "on_failure": "extend_rounds"},
            "abstention": {"allowed": True, "counts_toward_quorum": True},
            "evidence_gate": {"votes_require_evidence": True},
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
        },
        "stopping": {
            "source_expression": "objections_open == 0 AND every_objection_addressed == true",
            "expression": {
                "all_of": [
                    {"metric": "objections_open", "op": "==", "value": 0},
                    {"metric": "every_objection_addressed", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_minutes": 30,
                "min_objections_addressed": 1,
                "min_evidence_items": 4,
            },
            "hard_caps": {
                "max_rounds": 3,
                "max_minutes": 120,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": outcomes(
            FULL_OUTCOMES_MR,
            ["every rejected comment carries a distinct reason string"],
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "chair_ruling",
                "narrow_scope",
                "split_question",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": [
                "endless_debate",
                "lost_dissent",
                "minority_suppression",
                "moderator_capture",
                "weak_synthesis",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "argument_ledger",
                "evidence_map",
                "transcript",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=365,
            owner_approval_for=["merge", "release"],
            forbid_irreversible=True,
        ),
        "metadata": {
            "title": "RFC last call (editor + 5 reviewers)",
            "owner": "Prekzursil",
            "lineage": ["C-S30 rfc-last-call-open", "P19 rfc-last-call"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1573-1587"],
            "notes": notes(
                card="C-S30 rfc-last-call-open",
                seats_declared=6,
                roles_line="editor,reviewer_x5",
                preset_label_rationale="custom - publish_durable_artifact is not one of the 24 "
                "required archetypes. standing_watch_council is the nearest name but means a "
                "continuously-standing council, not a bounded comment window.",
                dials={
                    "$.budgets.time_minutes + $.stopping.hard_caps.max_minutes": "window dial (the "
                    "card says wall<=window, i.e. the window IS the budget)",
                    "$.participants.roster (reviewer seats)": "comment_sources dial - who may comment",
                    "$.stopping.minimum_deliberation.min_minutes": "a floor on the window so a "
                    "last call cannot be closed the second it opens",
                },
                outcome_lineage=FULL_OUTCOMES_MR,
                extra="USE FOR: rules/, schemas, contracts, AGENTS.md edits (card note). "
                "objections_open == 0 is the card's comments==dispositions rule; note that "
                "'addressed' means DISPOSITIONED, not agreed with - a rejected comment with a "
                "distinct reason is addressed.",
            ),
        },
    }
