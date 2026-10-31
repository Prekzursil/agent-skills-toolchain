"""Lane-2 preset builders, batch A: design indices 17-22 (C-S17 .. C-S22)."""

from __future__ import annotations

from typing import Any, Dict

from _lane2_common import (
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
    audit,
    injection_defense,
    notes,
    outcomes,
)

FULL_OUTCOMES = [
    "CONSENSUS",
    "MAJORITY_WITH_DISSENT",
    "IRREDUCIBLE_DISAGREEMENT",
    "INSUFFICIENT_EVIDENCE",
    "CONDITIONAL_DECISION",
    "DEFER",
    "PROOF_OF_IMPOSSIBILITY",
]
NO_IMPOSSIBILITY = [
    "CONSENSUS",
    "MAJORITY_WITH_DISSENT",
    "INSUFFICIENT_EVIDENCE",
    "CONDITIONAL_DECISION",
    "DEFER",
]
# A preset whose consensus.minority_report == "required" must also ALLOW the
# minority_report outcome (SEM-009). These two lists carry that addition.
FULL_OUTCOMES_MR = FULL_OUTCOMES + ["MINORITY_REPORT"]
NO_IMPOSSIBILITY_MR = NO_IMPOSSIBILITY + ["MINORITY_REPORT"]


def p17_red_blue_4() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s17-red-blue-4",
        "preset": "security_red_blue_council",
        "participation": "agent_only",
        "objective": {
            "statement": "Harden a named artifact by attacking it until at least one attack is "
            "reproduced by an independent white cell.",
            "charter": "Red/blue hardening council. Red attacks, blue defends, the white cell "
            "decides which attacks LANDED. Opinions do not score; reproductions do.",
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "at least one attack reproduced by the white cell, with the reproduction path recorded",
                "every landed attack carries an executable receipt, not a description",
                "every attack that did NOT reproduce is recorded as not-landed, not deleted",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "command_output",
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
                {
                    "participant_id": "red-1",
                    "display_name": "Red 1 (attack surface)",
                    "kind": "agent",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["threat modeling", "input boundaries"],
                    "role": "red_team",
                    "authority": "contributor",
                    "effort": "high",
                    "source_access": ["repo", "transcripts"],
                    "rights": {
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                    "independence": {
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                },
                {
                    "participant_id": "red-2",
                    "display_name": "Red 2 (cross-vendor attacker)",
                    "kind": "agent",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["exploit reproduction", "sandbox escape"],
                    "role": "red_team",
                    "authority": "contributor",
                    "effort": "high",
                    "source_access": ["repo"],
                    "rights": {
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                    "independence": {
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                },
                {
                    "participant_id": "blue-1",
                    "display_name": "Blue 1 (owner of the artifact)",
                    "kind": "agent",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["the artifact under attack", "mitigation design"],
                    "role": "blue_team",
                    "authority": "contributor",
                    "effort": "high",
                    "source_access": ["repo", "internal_docs"],
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "blue-2",
                    "display_name": "Blue 2 (defence review)",
                    "kind": "agent",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["defensive engineering", "regression risk"],
                    "role": "blue_team",
                    "authority": "contributor",
                    "effort": "high",
                    "source_access": ["repo"],
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "white-cell",
                    "display_name": "White cell (adjudicates what landed)",
                    "kind": "agent",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["reproduction", "both-states control"],
                    "role": "verifier",
                    "authority": "judge",
                    "effort": "xhigh",
                    "source_access": ["repo", "transcripts"],
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                    "independence": {"fresh_context": True},
                },
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["vendor", "position_similarity"],
                "max_similarity": 0.85,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "risk_list"],
        },
        "topology": {
            "kind": "red_blue",
            "caucuses": [
                {
                    "caucus_id": "red",
                    "members": ["red-1", "red-2"],
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "blue",
                    "members": ["blue-1", "blue-2"],
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "attack-plan",
                    "independent": True,
                    "participants": ["red-1", "red-2"],
                    "quotas": {"objections_per_participant": 4},
                },
                {"kind": "war_game", "stage_id": "attack-run", "rounds": 3},
                {
                    "kind": "custom",
                    "stage_id": "adjudicate",
                    "custom_name": "white-cell reproduction adjudication",
                    "participants": ["white-cell"],
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "experiments_passed",
                                "op": ">=",
                                "value": 1,
                                "note": "a reproduction the white cell RAN, not an attack description",
                            },
                            {
                                "metric": "executable_test_settled",
                                "op": "==",
                                "value": True,
                                "note": "the reproduction was proven against the known-good state too",
                            },
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "hardening-plan"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_cite_evidence": True,
                "cross_examination": True,
                "declare_confidence": True,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {
                "allowed": True,
                "max_experiments": 12,
                "required_before_decision": True,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 45,
            "tool_calls": 200,
            "sources": 20,
            "turns": 30,
            "experiments": 12,
            "rebuttal_depth": 2,
        },
        "targets": {"counterexamples": 6, "objections": 8, "evidence_items": 12},
        "voting": {
            "method": "judge",
            "quorum": {"min_voters": 1, "on_failure": "escalate_to_owner"},
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": False,
        },
        "stopping": {
            "source_expression": "experiments_passed >= 1 AND executable_test_settled == true",
            "expression": {
                "all_of": [
                    {"metric": "experiments_passed", "op": ">=", "value": 1},
                    {"metric": "executable_test_settled", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_evidence_items": 6,
                "min_objections_addressed": 4,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 45,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(
            FULL_OUTCOMES,
            ["every landed attack has a named mitigation owner"],
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "run_experiment",
                "strongest_counterexample",
                "judge_ruling",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {"allowed": True, "must_be_logged": True},
        },
        "anti_failure": {
            "controls": [
                "evidence_free_majority",
                "consensus_failing_executable_tests",
                "role_collapse",
                "prompt_injection",
                "hallucinated_expertise",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "evidence_map",
                "experiments",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(owner_approval_for=["merge"], forbid_irreversible=True),
        "metadata": {
            "title": "Red/blue hardening council (4+1)",
            "owner": "Prekzursil",
            "lineage": ["C-S17 red-blue-4", "P08 red-blue-team"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1387-1400"],
            "notes": notes(
                card="C-S17 red-blue-4",
                seats_declared=4,
                roles_line="blue_x2,red_x2,white_cell",
                preset_label_rationale="security_red_blue_council - exact archetype match.",
                dials={
                    "$.budgets.experiments / $.protocol.experiments.max_experiments": "attack_budget dial from the card",
                    "$.stopping.expression": "reproduction_requirement dial; raise experiments_passed to demand N landed attacks",
                    "$.participants.count + roster": "seat count; add red seats to widen the attack surface",
                    "$.protocol.experiments.runner": "sandbox|local|ci|owner - where a reproduction is allowed to run",
                },
                outcome_lineage=FULL_OUTCOMES,
                extra="SEAT DISCREPANCY (measured): the card says seats:4 but its roles line enumerates 5. "
                "This instance seats 5 and treats the white cell as the 5th, judging seat - the most "
                "likely reading, since the card's voting rule requires an adjudicator the four "
                "combatants cannot supply. Change $.participants.count.exact_n to 4 and drop a seat "
                "if the owner reads it the other way.",
            ),
        },
    }


def p18_oxford_4_plus_judge() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s18-oxford-4-plus-judge",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Resolve a single binary motion by formal debate with a judge scoring the "
            "pre/post position delta.",
            "charter": "Oxford-style debate. Two seats for the proposition, two against, one judge. "
            "Token budget is equal by construction so neither side wins on volume.",
            "risk_tier": "moderate",
            "desired_output": "decision",
            "success_criteria": [
                "all four debate phases ran: opening, cross-examination, rebuttal, closing",
                "both sides consumed within 10% of the same token budget",
                "the judge scored the delta between pre-debate and post-debate positions",
            ],
            "consensus_intent": "adjudicate",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2},
            "roster": [
                {
                    "participant_id": "prop-1",
                    "display_name": "Proposition 1 (lead)",
                    "kind": "agent",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "role": "proposer",
                    "authority": "contributor",
                    "effort": "high",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                },
                {
                    "participant_id": "prop-2",
                    "display_name": "Proposition 2 (second)",
                    "kind": "agent",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "role": "steelman",
                    "authority": "contributor",
                    "effort": "high",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "opp-1",
                    "display_name": "Opposition 1 (lead)",
                    "kind": "agent",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "role": "critic",
                    "authority": "contributor",
                    "effort": "high",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                },
                {
                    "participant_id": "opp-2",
                    "display_name": "Opposition 2 (second)",
                    "kind": "agent",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "role": "devils_advocate",
                    "authority": "contributor",
                    "effort": "high",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "judge",
                    "display_name": "Judge (scores the delta)",
                    "kind": "agent",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "role": "judge",
                    "authority": "judge",
                    "effort": "xhigh",
                    "rights": {"may_speak": True, "may_vote": True},
                    "independence": {"fresh_context": True},
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
        },
        "topology": {"kind": "proposer_critic_judge"},
        "protocol": {
            "sequence": [
                {"kind": "oxford", "stage_id": "opening", "independent": True},
                {"kind": "cross_examination", "stage_id": "crossexam", "rounds": 1},
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "rebuttal",
                    "rounds": 1,
                },
                {"kind": "jury", "stage_id": "closing", "participants": ["judge"]},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 4, "max": 4},
            "turn": {"max_words": 500, "max_tokens": 3000},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
            },
            "critique_intensity": "adversarial",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 35,
            "turns": 20,
            "speaking_quota_per_participant": 4,
            "rebuttal_depth": 2,
        },
        "targets": {"objections": 6, "counterexamples": 2},
        "voting": {
            "method": "judge",
            "quorum": {"min_voters": 1, "on_failure": "escalate_to_owner"},
            "belief_aggregation": {
                "method": "none",
                "require_confidence_per_vote": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
            "fast_unanimity_is_suspicious": False,
        },
        "stopping": {
            "source_expression": "rounds_elapsed >= 4 AND all_participants_spoke == true",
            "expression": {
                "all_of": [
                    {"metric": "rounds_elapsed", "op": ">=", "value": 4},
                    {"metric": "all_participants_spoke", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 4,
                "every_participant_spoke": True,
                "min_independent_positions": 2,
            },
            "hard_caps": {
                "max_rounds": 4,
                "max_minutes": 35,
                "on_cap": "conditional_decision",
            },
        },
        "outcomes": outcomes(NO_IMPOSSIBILITY),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": ["judge_ruling", "narrow_scope", "escalate_to_owner"],
            "escalation": {"after_attempts": 1, "to": "judge"},
        },
        "anti_failure": {
            "controls": [
                "circular_debate",
                "participant_dominance",
                "strategic_voting",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_ledger",
                "confidence_trajectory",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=60, owner_approval_for=["merge"], forbid_irreversible=True
        ),
        "metadata": {
            "title": "Oxford debate, four debaters plus a judge",
            "owner": "Prekzursil",
            "lineage": [
                "C-S18 oxford-4-plus-judge",
                "P07 oxford-debate",
                "P14 judge-and-jury",
            ],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1401-1414"],
            "notes": notes(
                card="C-S18 oxford-4-plus-judge",
                seats_declared=5,
                roles_line="proposition_x2,opposition_x2,judge",
                preset_label_rationale="custom - the 24 required archetypes have no formal-debate "
                "entry; the nearest, code_review_tribunal, is a different decision type.",
                dials={
                    "$.objective.statement": "the motion dial - a debate needs ONE binary motion",
                    "$.protocol.rounds + $.stopping.hard_caps.max_rounds": "rounds dial (keep them equal)",
                    "$.protocol.turn.max_tokens + $.budgets.speaking_quota_per_participant": "token_parity dial",
                },
                outcome_lineage=NO_IMPOSSIBILITY,
                extra="Anti-sycophancy is deliberately NOT armed: the card records "
                "fast_unanimity as n/a because the protocol is adversarial by construction. "
                "$.consensus.fast_unanimity_is_suspicious is therefore false here, unlike most presets.",
            ),
        },
    }
