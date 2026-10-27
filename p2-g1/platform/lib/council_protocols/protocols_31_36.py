"""Executable CouncilSpec blueprints P31-P36 (PHASE 2C, lane 25-36 of 48).

Source designs: 12-COUNCIL-PROTOCOLS-AND-PRESETS.md, one option card per protocol. P31 and
P36 are the two cards in this lane flagged OWNER-DECISION: YES, and both encode that in the
spec rather than in prose - P31 cannot terminate without owner_approved == true, and P36
ships in SHADOW with every seat weight pinned at 1.0.
"""

from __future__ import annotations

from typing import Any, Dict

from ._shared import (
    OWNER,
    RECEIPT_SCHEMA,
    agent,
    audit,
    cite,
    exact_count,
    expr,
    human,
    injection_defense,
    stopping,
)


# --------------------------------------------------------------------------- P31
def p31_constraint_relaxation() -> Dict[str, Any]:
    relaxers = ["relaxer-a", "relaxer-b", "relaxer-c", "relaxer-d"]
    roster = [
        agent(
            "constraint-clerk",
            "scribe",
            authority="contributor",
            expertise=["charter extraction"],
            rights={"may_speak": True, "may_vote": False},
            briefing=(
                "Enumerate EVERY constraint in the charter and mark the AGENTS.md section 6 and "
                "section 9 safety non-negotiables, plus owner-ops hard bans H1-H9, as "
                "UNRELAXABLE before any seat is allowed to remove one."
            ),
        ),
        agent(
            "relaxer-a",
            "proposer",
            expertise=["operations research"],
            briefing="Remove EXACTLY ONE relaxable constraint, then re-decide. Never two.",
        ),
        agent(
            "relaxer-b",
            "proposer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["systems engineering"],
            briefing="Remove EXACTLY ONE relaxable constraint, then re-decide. Never two.",
        ),
        agent(
            "relaxer-c",
            "proposer",
            expertise=["product scope"],
            briefing="Remove EXACTLY ONE relaxable constraint, then re-decide. Never two.",
        ),
        agent(
            "relaxer-d",
            "proposer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["cost and budget"],
            briefing="Remove EXACTLY ONE relaxable constraint, then re-decide. Never two.",
        ),
        agent(
            "unrelaxable-guard",
            "security_reviewer",
            authority="judge",
            expertise=["safety non-negotiables", "policy"],
            rights={"may_speak": True, "may_vote": True, "may_veto": True},
            briefing="Reject any relaxation that touches the UNRELAXABLE set. This is a hard gate.",
        ),
        human(
            "owner",
            "stakeholder",
            authority="owner",
            expertise=["owner-owned constraints"],
            rights={"may_speak": True, "may_vote": True, "may_veto": True},
            briefing="Ratify or refuse each constraint the panel found to be binding.",
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p31-constraint-relaxation",
        "participation": "hybrid",
        "objective": {
            "statement": (
                "Find out whether the decision only looks forced because an unexamined constraint "
                "is being treated as fixed: each seat removes exactly ONE constraint and "
                "re-decides, and the constraints whose removal changes the answer are the real "
                "decision drivers."
            ),
            "charter": (
                "The product is a ranked list of BINDING constraints, not an option. Nothing else "
                "in the catalogue targets the constraint set itself."
            ),
            "risk_tier": "high",
            "desired_output": "specification",
            "success_criteria": [
                "every constraint in the charter was enumerated before any was removed",
                "no seat selected a constraint from the UNRELAXABLE set",
                "each binding constraint was ratified or refused by the owner, by name",
            ],
            "consensus_intent": "surface_disagreement",
            "confidence_target": 0.85,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": True,
                "forbidden_actions": [
                    "relaxing any AGENTS.md section 6 or section 9 safety non-negotiable",
                    "relaxing any owner-ops hard ban H1-H9",
                    "relaxing a constraint the owner has marked owner-owned without ratification",
                ],
                "deadline_minutes": 60,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": [
                    "exact",
                    "expertise_ranked",
                    "vendor_diverse",
                    "stakeholder_balanced",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 5,
                "max_share_per_vendor": 0.6,
            },
            "roster": roster,
            "role_templates": [
                "proposer",
                "security_reviewer",
                "scribe",
                "stakeholder",
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "escalate_to_owner",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "risk_list"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "constraint_enumeration_and_unrelaxable_marking",
                    "stage_id": "enumerate",
                    "rounds": 1,
                    "participants": ["constraint-clerk", "unrelaxable-guard"],
                    "exit_when": expr(
                        "ALL[custom:constraints_enumerated >= 1, custom:unrelaxable_set_marked == true]"
                    ),
                },
                {
                    "kind": "custom",
                    "custom_name": "single_constraint_removal_and_redecide",
                    "stage_id": "relax-probe",
                    "rounds": 1,
                    "participants": relaxers,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 2, "novel_ideas_per_round": 1},
                    "exit_when": expr("custom:unrelaxable_violations <= 0"),
                },
                {"kind": "nominal_group", "stage_id": "rank-binding", "rounds": 1},
                {
                    "kind": "custom",
                    "custom_name": "owner_ratification_of_binding_constraints",
                    "stage_id": "owner-ratify",
                    "rounds": 1,
                    "participants": ["owner", "unrelaxable-guard"],
                    "exit_when": expr("owner_approved == true"),
                },
                {"kind": "synthesis", "stage_id": "constraint-spec"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "turn": {"max_words": 700},
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                # A relaxation claim is cross-examined: "does removing this actually change the
                # answer, or did you just re-derive the same one?"
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": False,
                "max_experiments": 3,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 60,
            "turns": 25,
            "experiments": 3,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 8,
            "categories": 3,
            "novelty_ratio": 0.4,
            "objections": 6,
            "evidence_items": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "veto",
            "veto": {
                "holders": ["unrelaxable-guard", "owner"],
                "scope": "safety_only",
                "must_justify": True,
                "overridable_by_owner": False,
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
                "strategic_abstention_check": True,
            },
            "tie_break": "owner",
        },
        "consensus": {
            "threshold": 0.7,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[custom:binding_constraints_identified >= 1, custom:unrelaxable_violations <= 0, "
            "owner_approved == true, custom:constraints_enumerated >= 1]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 4,
            },
            hard_caps={
                "max_rounds": 4,
                "max_minutes": 90,
                "on_cap": "escalate_to_owner",
            },
        ),
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "owner ratification of every constraint the panel proposes to relax",
                "an explicit note for any constraint the panel could not classify as binding or slack",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "run_experiment",
                "narrow_scope",
                "escalate_to_owner",
                "declare_no_decision",
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
                "premature_convergence",
                "evidence_free_majority",
                "participant_dominance",
                "echo_chamber",
                "strategic_voting",
                "lost_dissent",
                "prompt_injection",
            ],
            "fast_unanimity_response": [
                "forced_dissent",
                "strongest_counterexample",
                "blind_re_evaluation",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "option_cards",
                "argument_ledger",
                "unresolved_unknowns",
                "dissent_minority_report",
                "votes_by_round",
                "transcript",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            "p31-constraint-relaxation",
            owner_approval_for=[
                "relaxing any constraint at all",
                "any action that a relaxed constraint would have prevented",
            ],
        ),
        "metadata": {
            "title": "P31 constraint relaxation (GENERATIVE, OWNER-DECISION)",
            "owner": OWNER,
            "spec_citations": cite(602, 607, 613, 614),
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P31 constraint-relaxation"
            ],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) the card's own failure mode is 'relaxing "
                "a safety non-negotiable', and it is defended THREE ways that must all hold - an "
                "enumerate stage that cannot exit until custom:unrelaxable_set_marked == true, a "
                "veto held by the guard AND the owner with overridable_by_owner=false, and a "
                "custom:unrelaxable_violations <= 0 leaf in both the probe stage exit and the "
                "stopping rule; (2) evidence_free_majority is blocked by "
                "reject_evidence_free_majority plus anchor_style=file_line - a constraint claim "
                "cites the charter line it comes from; (3) participant_dominance and (4) "
                "echo_chamber are cut by independent simultaneous single-constraint probes; (5) "
                "strategic_voting is checked by strategic_abstention_check plus must_justify on "
                "abstention, because abstaining on a relaxation you want is how a guard gets "
                "bypassed quietly; (6) lost_dissent is met by minority_report=required with "
                "suppression_check and outcomes.allowed carrying minority_report; (7) "
                "prompt_injection defence is on because constraints are read out of charter TEXT, "
                "which is untrusted data. FAST UNANIMITY: forced_dissent + strongest_counterexample "
                "+ blind_re_evaluation. OWNER-DECISION: YES on the card, so owner_approved == true "
                "is a stopping-rule leaf - this council cannot self-certify a relaxation. "
                "UNVERIFIED: the card's required proof - assert the unrelaxable set is never "
                "selected by any seat, both-states, with a deliberate attempt - has not been run; "
                "custom:unrelaxable_violations is named in the lane's PRODUCERS map (platform/lib/council_protocols/_shared.py, republished in PROTOCOL-EXPECTATIONS-25-36.json) and NOT implemented, so "
                "today the guard is a prompt, not a mechanism."
            ),
        },
    }


# --------------------------------------------------------------------------- P32
def p32_counterfactual_council() -> Dict[str, Any]:
    failed_half = ["hindsight-failed-a", "hindsight-failed-b"]
    succeeded_half = ["hindsight-succeeded-a", "hindsight-succeeded-b"]
    roster = [
        agent(
            "counterfactual-chair",
            "moderator",
            authority="chair",
            expertise=["causal merge"],
            rights={"may_speak": True, "may_vote": False},
            briefing="You alone see both briefings. Merge the two causal sets; do not average them.",
        ),
        agent(
            "hindsight-failed-a",
            "critic",
            expertise=["failure analysis"],
            sees_peers=False,
            partition_id="already-failed",
            briefing="The decision ALREADY FAILED. Explain how. Do not hedge.",
        ),
        agent(
            "hindsight-failed-b",
            "critic",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["operational risk"],
            sees_peers=False,
            partition_id="already-failed",
            briefing="The decision ALREADY FAILED. Explain how. Do not hedge.",
        ),
        agent(
            "hindsight-succeeded-a",
            "proposer",
            expertise=["mechanism design"],
            sees_peers=False,
            partition_id="already-succeeded",
            briefing=(
                "The decision ALREADY SUCCEEDED. Explain why. Every cause must be FALSIFIABLE "
                "and anchored - cheerleading is rejected."
            ),
        ),
        agent(
            "hindsight-succeeded-b",
            "proposer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["adoption and incentives"],
            sees_peers=False,
            partition_id="already-succeeded",
            briefing=(
                "The decision ALREADY SUCCEEDED. Explain why. Every cause must be FALSIFIABLE "
                "and anchored - cheerleading is rejected."
            ),
        ),
        agent(
            "falsifiability-verifier",
            "verifier",
            authority="judge",
            expertise=["falsifiability", "evidence anchoring"],
            rights={"may_speak": True, "may_vote": False},
            briefing="Reject any success cause that cannot be stated as a falsifiable claim with an anchor.",
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p32-counterfactual-council",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Run both prospective-hindsight directions at once: half the seats are told the "
                "decision ALREADY FAILED and must explain how, half are told it ALREADY SUCCEEDED "
                "and must explain why, and the chair merges the two causal sets."
            ),
            "charter": (
                "A premortem runs only the failure direction. This protocol refuses to lose the "
                "success mechanisms, and it refuses to accept them without falsifiability."
            ),
            "risk_tier": "moderate",
            "desired_output": "risk_register",
            "success_criteria": [
                "each half named at least one mechanism the other half did not - otherwise the split added nothing",
                "every success cause is falsifiable and anchored",
                "the merged causal set is preserved as a register, not collapsed into a verdict",
            ],
            "consensus_intent": "surface_disagreement",
            "confidence_target": 0.8,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": [
                    "exact",
                    "adversarial",
                    "vendor_diverse",
                    "model_diverse",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 4,
                "max_share_per_vendor": 0.7,
            },
            "roster": roster,
            "role_templates": ["critic", "proposer", "verifier", "moderator"],
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 2},
            "information_partition": {
                "enabled": True,
                "strategy": "role_scoped",
                "partitions": [
                    {
                        "partition_id": "already-failed",
                        "visible_to": failed_half,
                        "sources": ["the plan", "the failure briefing"],
                    },
                    {
                        "partition_id": "already-succeeded",
                        "visible_to": succeeded_half,
                        "sources": ["the plan", "the success briefing"],
                    },
                ],
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["risk_list", "position_memo"],
        },
        "topology": {
            "kind": "caucus",
            "caucuses": [
                {
                    "caucus_id": "already-failed",
                    "members": failed_half,
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "already-succeeded",
                    "members": succeeded_half,
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "premortem",
                    "stage_id": "failure-half",
                    "rounds": 1,
                    "participants": failed_half,
                    "independent": True,
                    "quotas": {
                        "counterexamples_per_round": 3,
                        "objections_per_participant": 3,
                    },
                },
                {
                    "kind": "custom",
                    "custom_name": "prospective_hindsight_success_half",
                    "stage_id": "success-half",
                    "rounds": 1,
                    "participants": succeeded_half,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 3, "novel_ideas_per_round": 3},
                    "exit_when": expr("custom:unfalsifiable_success_causes <= 0"),
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "merge-challenge",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 2},
                    "exit_when": expr(
                        "ALL[custom:failure_only_mechanisms >= 1, custom:success_only_mechanisms >= 1]"
                    ),
                },
                {"kind": "synthesis", "stage_id": "causal-merge"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 5, "divergence_before_convergence": True},
            "turn": {"max_words": 800},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": False,
            },
            "critique_intensity": "adversarial",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 60,
            "turns": 30,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 16,
            "categories": 4,
            "novelty_ratio": 0.6,
            "objections": 10,
            "counterexamples": 8,
            "evidence_items": 8,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "majority",
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
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.6,
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
        "stopping": stopping(
            "ALL[custom:failure_only_mechanisms >= 1, custom:success_only_mechanisms >= 1, "
            "every_objection_addressed == true, custom:unfalsifiable_success_causes <= 0]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
                "min_objections_addressed": 6,
            },
            hard_caps={
                "max_rounds": 5,
                "max_minutes": 80,
                "on_cap": "synthesize_best_effort",
            },
        ),
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "any success cause that stayed unfalsifiable is listed as an assumption, not a mechanism",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.85,
                "circular_citation_check": True,
            },
            "resolution": [
                "strongest_counterexample",
                "recruit_independent_critic",
                "rotate_roles",
                "chair_ruling",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "echo_chamber",
                "sycophancy",
                "evidence_free_majority",
                "premature_convergence",
                "weak_synthesis",
                "role_collapse",
                "lost_dissent",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "forced_dissent",
                "role_rotation",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "argument_graph",
                "evidence_map",
                "unresolved_unknowns",
                "dissent_minority_report",
                "transcript",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p32-counterfactual-council"),
        "metadata": {
            "title": "P32 counterfactual council (GENERATIVE)",
            "owner": OWNER,
            "spec_citations": cite(618, 623, 629, 630),
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P32 counterfactual-council"
            ],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) sycophancy is the card's named failure "
                "mode - 'the success half produces cheerleading' - and it is answered by "
                "custom:unfalsifiable_success_causes <= 0 as the success-half stage exit AND a "
                "stopping leaf, with a dedicated falsifiability-verifier who cannot vote; (2) "
                "echo_chamber is cut by two caucuses with private_rounds=1, disjoint role-scoped "
                "briefings and sees_peers_before_first_position=false; (3) evidence_free_majority "
                "is blocked by reject_evidence_free_majority plus evidence_outranks_majority; (4) "
                "premature_convergence is blocked by the two 'only' leaves - the council cannot "
                "stop until EACH half has produced at least one mechanism the other did not, which "
                "is the card's own test that the split added something; (5) weak_synthesis is "
                "answered by a required argument_graph and a chair whose job is to MERGE rather "
                "than average; (6) role_collapse - the failure half hedging into balance, or the "
                "success half admitting failure - is what the private caucus rounds exist to "
                "prevent; (7) lost_dissent is met by minority_report=required with "
                "suppression_check. FAST UNANIMITY across two halves given OPPOSITE briefings is "
                "the strongest possible signal of briefing leakage, so the response is "
                "strongest_counterexample + forced_dissent + role_rotation. UNVERIFIED: the card's "
                "adoption proof - both halves must produce at least one mechanism the other did "
                "not name - is encoded as a stopping leaf but has never been measured on a real "
                "run; custom:failure_only_mechanisms and custom:success_only_mechanisms are "
                "set-difference counts named in the lane's PRODUCERS map (platform/lib/council_protocols/_shared.py, republished in PROTOCOL-EXPECTATIONS-25-36.json) and NOT implemented. They are "
                "MECHANICAL by construction (set difference over named mechanisms), which is the "
                "correct shape - LLM judgement on a set-membership question measured 86% accurate "
                "on this estate with every error pointing at data loss."
            ),
        },
    }


# --------------------------------------------------------------------------- P33
def p33_prediction_tournament() -> Dict[str, Any]:
    forecasters = ["forecaster-a", "forecaster-b", "forecaster-c", "forecaster-d"]
    roster = [
        agent(
            "question-clerk",
            "scribe",
            authority="contributor",
            expertise=["question decomposition", "resolution criteria"],
            rights={"may_speak": True, "may_vote": False},
            briefing=(
                "Refuse any question that lacks a resolution DATE and a NAMED source. An "
                "unresolvable question rots the scoring store."
            ),
        ),
        agent(
            "forecaster-a",
            "forecaster",
            expertise=["base rates"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "forecaster-b",
            "forecaster",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["technical delivery"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "forecaster-c",
            "forecaster",
            expertise=["adversarial forecasting"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "forecaster-d",
            "forecaster",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["operations"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "scoring-registrar",
            "statistician",
            authority="judge",
            expertise=["Brier scoring", "resolution tracking"],
            rights={"may_speak": True, "may_vote": False},
            briefing="Register each question, its resolution date and its source. Score at resolution, not before.",
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p33-prediction-tournament",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Decompose the decision into resolvable binary or numeric questions with "
                "resolution dates and named sources, collect probabilities from every seat, and "
                "register them for Brier scoring at resolution."
            ),
            "charter": (
                "The primary product is a SCORED FORECAST, not a decision. Its value is near zero "
                "immediately and high only if the questions actually resolve."
            ),
            "risk_tier": "moderate",
            "desired_output": "forecast",
            "success_criteria": [
                "every registered question has a resolution date AND a named source",
                "every seat submitted a probability independently, before seeing any peer",
                "the scoring store recorded the submissions in a form that can be scored later",
            ],
            "consensus_intent": "elicit_distribution",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "url",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": [
                    "exact",
                    "calibration_ranked",
                    "vendor_diverse",
                    "model_diverse",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 4,
                "max_share_per_vendor": 0.6,
            },
            "roster": roster,
            "role_templates": ["forecaster", "statistician", "scribe"],
            "anonymity": {"mode": "blind_to_peers", "reveal_after_round": 1},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "model"],
                "max_similarity": 0.9,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
            "required_artifacts": ["evidence_pack", "benchmark_baseline"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "question_decomposition_with_resolution_criteria",
                    "stage_id": "decompose",
                    "rounds": 1,
                    "participants": ["question-clerk", "scoring-registrar"],
                    "exit_when": expr(
                        "ALL[custom:questions_registered >= 3, custom:unresolvable_questions <= 0]"
                    ),
                },
                {
                    "kind": "prediction_confidence",
                    "stage_id": "elicit",
                    "rounds": 2,
                    "participants": forecasters,
                    "independent": True,
                    "anonymous": True,
                    "quotas": {"novel_ideas_per_round": 2},
                },
                {
                    "kind": "custom",
                    "custom_name": "resolution_registry_write_and_brier_scheduling",
                    "stage_id": "register",
                    "rounds": 1,
                    "participants": ["scoring-registrar"],
                },
                {"kind": "synthesis", "stage_id": "distribution"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                # After the reveal, an extreme forecast must be justified and may be cross-examined;
                # before the reveal there is nothing to respond to by construction.
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 45,
            "turns": 20,
            "sources": 8,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
        },
        "targets": {
            "unique_ideas": 6,
            "categories": 3,
            "novelty_ratio": 0.3,
            "evidence_items": 8,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.9,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "bayesian",
            "belief_aggregation": {
                "method": "logarithmic_pool",
                "require_confidence_per_vote": True,
                "calibration_source": "platform/council/state/p36-calibration-tournament/seat-scores.json",
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "measure": "confidence_overlap",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": False},
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[custom:unresolvable_questions <= 0, custom:questions_registered >= 3, "
            "independent_positions >= 4, all_participants_spoke == true]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
            },
            hard_caps={
                "max_rounds": 4,
                "max_minutes": 60,
                "on_cap": "conditional_decision",
            },
        ),
        "outcomes": {
            "allowed": ["decision", "conditional_decision", "no_decision", "dissent"],
            "conditional_decision_requires": [
                "the forecast is labelled UNSCORED until at least one question resolves",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "split_question",
                "narrow_scope",
                "recruit_independent_critic",
                "declare_no_decision",
            ],
            "escalation": {"after_attempts": 2, "to": "judge"},
        },
        "anti_failure": {
            "controls": [
                "strategic_voting",
                "sycophancy",
                "echo_chamber",
                "evidence_free_majority",
                "hallucinated_expertise",
                "premature_convergence",
            ],
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
                "confidence_trajectory",
                "votes_by_round",
                "calibration_report",
                "evidence_map",
                "transcript",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            "p33-prediction-tournament",
            calibration={"post_run": True, "score": "brier"},
        ),
        "metadata": {
            "title": "P33 prediction tournament (FORECASTING, OWNER-DECISION)",
            "owner": OWNER,
            "spec_citations": cite(637, 642, 648, 649),
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P33 prediction-tournament"
            ],
            "notes": (
                "ANTI-FAILURE DEFENCES (6 declared): (1) the card's failure mode is 'questions "
                "never resolve and the store rots', so custom:unresolvable_questions <= 0 is both "
                "the decompose-stage exit and a stopping leaf - a question with no resolution date "
                "and no named source cannot enter the tournament; (2) strategic_voting - shading a "
                "probability toward the expected consensus - is countered by blind_to_peers "
                "elicitation with reveal_after_round=1 and strategic_abstention_check; (3) "
                "sycophancy and (4) echo_chamber are cut by anonymous independent submission; (5) "
                "evidence_free_majority is blocked by votes_require_evidence with "
                "anchor_style=url, because a forecast with no source is an opinion; (6) "
                "hallucinated_expertise is exposed by Brier scoring at resolution rather than by "
                "argument. FAST UNANIMITY on a probability distribution means the seats are not "
                "independent, so the response is blind_re_evaluation first. HONEST LIMIT, INLINE: "
                "voting.belief_aggregation.calibration_source names "
                "platform/council/state/p36-calibration-tournament/seat-scores.json and that file "
                "DOES NOT EXIST - no resolution registry or scoring store has been built on this "
                "estate, so calibration_ranked selection degrades to expertise order and the pool "
                "is unweighted today. The card's own adoption bar is the settling experiment: at "
                "least one question must actually resolve and update a weight before the mechanism "
                "is trusted, and the owner must be willing to run it for at least eight weeks."
            ),
        },
    }


# --------------------------------------------------------------------------- P34
def p34_scenario_planning() -> Dict[str, Any]:
    quadrants = {
        "q1-high-high": "scenario-analyst-q1",
        "q2-high-low": "scenario-analyst-q2",
        "q3-low-high": "scenario-analyst-q3",
        "q4-low-low": "scenario-analyst-q4",
    }
    roster = [
        agent(
            "scenario-chair",
            "facilitator",
            authority="chair",
            expertise=["scenario method", "robustness selection"],
            rights={"may_speak": True, "may_vote": True},
        ),
        agent(
            "scenario-analyst-q1",
            "domain_expert",
            expertise=["strategy"],
            briefing="You own ONE named future. Stress-test the decision inside it only.",
        ),
        agent(
            "scenario-analyst-q2",
            "domain_expert",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["delivery risk"],
            briefing="You own ONE named future. Stress-test the decision inside it only.",
        ),
        agent(
            "scenario-analyst-q3",
            "risk_officer",
            expertise=["risk analysis"],
            briefing="You own ONE named future. Stress-test the decision inside it only.",
        ),
        agent(
            "scenario-analyst-q4",
            "domain_expert",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["cost and market"],
            briefing="You own ONE named future. Stress-test the decision inside it only.",
        ),
        agent(
            "driver-independence-verifier",
            "statistician",
            authority="judge",
            expertise=["correlation", "driver selection"],
            rights={"may_speak": True, "may_vote": False},
            briefing=(
                "Show the two drivers are independent. Four futures that are really one future "
                "make this protocol theatre."
            ),
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p34-scenario-planning",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Identify the two most uncertain high-impact drivers, build a 2x2 of four named "
                "futures, stress-test the decision in each, and select the option that is least "
                "bad across all four."
            ),
            "charter": (
                "Robustness, not expected value. This protocol deliberately REFUSES to weight the "
                "futures by probability - that is P33's job, and mixing the two hides fragility."
            ),
            "risk_tier": "high",
            "desired_output": "ranked_options",
            "success_criteria": [
                "the two drivers were shown to be independent, not two names for one driver",
                "all four futures were stress-tested by a seat that owned only that future",
                "the selected option is the least-bad ACROSS futures, with the worst case named",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.8,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": [
                    "exact",
                    "stratified",
                    "expertise_ranked",
                    "vendor_diverse",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 4,
                "max_share_per_vendor": 0.7,
            },
            "roster": roster,
            "role_templates": [
                "domain_expert",
                "risk_officer",
                "statistician",
                "facilitator",
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "role_scoped",
                "partitions": [
                    {
                        "partition_id": qid,
                        "visible_to": [pid],
                        "sources": ["the decision", f"future {qid}"],
                    }
                    for qid, pid in quadrants.items()
                ],
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
            "required_artifacts": ["evidence_pack", "risk_list"],
        },
        "topology": {
            "kind": "committee",
            "committees": [
                {
                    "committee_id": qid,
                    "mandate": f"stress-test the decision inside named future {qid}",
                    "members": [pid],
                }
                for qid, pid in quadrants.items()
            ],
            "fan_in": {
                "reducer": "weighted_merge",
                "require_all_subcouncils_complete": True,
            },
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "driver_extraction_and_independence_check",
                    "stage_id": "drivers",
                    "rounds": 1,
                    "participants": ["driver-independence-verifier", "scenario-chair"],
                    "exit_when": expr("custom:driver_pair_correlation <= 0.3"),
                },
                {
                    "kind": "scenario",
                    "stage_id": "stress-test",
                    "rounds": 2,
                    "participants": list(quadrants.values()),
                    "independent": True,
                    "quotas": {
                        "counterexamples_per_round": 2,
                        "novel_ideas_per_round": 2,
                    },
                },
                {
                    "kind": "custom",
                    "custom_name": "robustness_scoring_across_futures",
                    "stage_id": "robustness",
                    "rounds": 1,
                    # A weighted exit: the stage may close on a WEIGHT of evidence rather than a
                    # single condition. All four futures tested is worth 2; the other two signals
                    # are worth 1 each; threshold 3 means "all four futures plus one more signal",
                    # so quadrant coverage alone can never close the stage.
                    "exit_when": {
                        "weighted": {
                            "threshold": 3,
                            "clauses": [
                                {
                                    "weight": 2,
                                    "when": expr("custom:futures_stress_tested >= 4"),
                                },
                                {
                                    "weight": 1,
                                    "when": expr(
                                        "custom:worst_case_named_per_option == true"
                                    ),
                                },
                                {
                                    "weight": 1,
                                    "when": expr("every_objection_addressed == true"),
                                },
                            ],
                        }
                    },
                },
                {"kind": "synthesis", "stage_id": "select-robust"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 2, "max": 5, "divergence_before_convergence": True},
            "turn": {"max_words": 800},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                # Cross-examination is aimed at the FUTURES, not the seats: "does your future
                # actually differ from the neighbouring quadrant?"
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": False,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 90,
            "turns": 35,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 16,
            "categories": 4,
            "novelty_ratio": 0.5,
            "counterexamples": 8,
            "evidence_items": 8,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 4},
            # Explicit refusal to weight futures by probability - that is the point of the protocol.
            "belief_aggregation": {
                "method": "none",
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
            "threshold": 0.7,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[custom:futures_stress_tested >= 4, custom:driver_pair_correlation <= 0.3, "
            "every_objection_addressed == true, custom:worst_case_named_per_option == true]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
                "min_objections_addressed": 4,
            },
            hard_caps={
                "max_rounds": 5,
                "max_minutes": 120,
                "on_cap": "conditional_decision",
            },
        ),
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "if one option wins in all four quadrants, a note showing the drivers are actually discriminating",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.85,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "split_question",
                "narrow_scope",
                "run_experiment",
                "chair_ruling",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "premature_convergence",
                "echo_chamber",
                "weak_synthesis",
                "participant_dominance",
                "evidence_free_majority",
                "missing_expertise",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "recruit_independent_critic",
                "forced_dissent",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "option_cards",
                "unresolved_unknowns",
                "argument_ledger",
                "votes_by_round",
                "dissent_minority_report",
                "transcript",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p34-scenario-planning"),
        "metadata": {
            "title": "P34 scenario planning 2x2 (FORECASTING)",
            "owner": OWNER,
            "spec_citations": cite(653, 658, 664, 665),
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P34 scenario-planning"],
            "notes": (
                "ANTI-FAILURE DEFENCES (6 declared): (1) the card's failure mode is 'four futures "
                "that are really one', defended by custom:driver_pair_correlation <= 0.3 as the "
                "drivers-stage exit AND a stopping leaf, with a verifier who cannot vote; (2) "
                "premature_convergence is blocked because the rule cannot fire until all four "
                "futures were stress-tested and every option has a named worst case; (3) "
                "echo_chamber is cut by a role_scoped partition per quadrant - a seat sees only "
                "its own future; (4) weak_synthesis is answered by score voting on a 0-4 rubric "
                "with belief_aggregation.method=none, an explicit refusal to average futures into "
                "an expected value; (5) participant_dominance is bounded by one seat per quadrant; "
                "(6) missing_expertise is why the four committees are expertise-differentiated. "
                "COMPOSABILITY DEMONSTRATED: the robustness stage exits on a WEIGHTED expression "
                "(threshold 3, quadrant coverage worth 2, worst-case naming and objection closure "
                "worth 1 each) so coverage alone cannot close it; the top-level stopping rule "
                "stays conjunctive. FAST UNANIMITY: if every quadrant owner agrees immediately, "
                "the quadrants are not discriminating - strongest_counterexample + "
                "recruit_independent_critic + forced_dissent. UNVERIFIED: the 0.3 correlation "
                "ceiling is a placeholder, and the card's check - if one option wins in all four "
                "quadrants, verify the drivers discriminate before celebrating - is encoded only "
                "as a conditional_decision requirement, not as an executable detector."
            ),
        },
    }


# --------------------------------------------------------------------------- P35
def p35_reference_class_planning_poker() -> Dict[str, Any]:
    estimators = ["estimator-a", "estimator-b", "estimator-c", "estimator-d"]
    roster = [
        agent(
            "reference-class-clerk",
            "scribe",
            authority="contributor",
            expertise=["estate ledger", "base rates"],
            rights={"may_speak": True, "may_vote": False},
            source_access=["repo", "transcripts", "internal_docs"],
            briefing=(
                "Every reference class must resolve to a REAL prior artifact - an event-ledger "
                "entry, a PR, or a workflow run record. An invented class fails the anchor check."
            ),
        ),
        agent(
            "estimator-a",
            "forecaster",
            expertise=["effort estimation"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "estimator-b",
            "forecaster",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["implementation effort"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "estimator-c",
            "domain_expert",
            expertise=["the work being estimated"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "estimator-d",
            "domain_expert",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["integration and test effort"],
            sees_peers=False,
            anonymous=True,
        ),
        agent(
            "anchor-auditor",
            "verifier",
            authority="judge",
            expertise=["citation resolution"],
            rights={"may_speak": True, "may_vote": False},
            briefing="Resolve every cited reference class to a real artifact. Unresolvable means the estimate is void.",
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p35-reference-class-planning-poker",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Force an OUTSIDE view before any inside-view number: seats name a reference class "
                "of comparable past cases and its base rate, then estimate simultaneously with no "
                "anchoring, extremes justify, and everyone re-estimates."
            ),
            "charter": (
                "Inside-view estimates are systematically optimistic. No estimate is accepted "
                "until the reference class it came from resolves to a real prior artifact."
            ),
            "risk_tier": "moderate",
            "desired_output": "forecast",
            "success_criteria": [
                "every seat named a reference class BEFORE producing a number",
                "every cited reference class resolved to a real artifact - a fabricated class voids the estimate",
                "the spread between the extreme estimates closed to the declared ratio after re-estimation",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.75,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": [
                    "exact",
                    "expertise_ranked",
                    "vendor_diverse",
                    "model_diverse",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 4,
                "max_share_per_vendor": 0.6,
            },
            "roster": roster,
            "role_templates": ["forecaster", "domain_expert", "verifier", "scribe"],
            "anonymity": {"mode": "blind_to_peers", "reveal_after_round": 1},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity"],
                "max_similarity": 0.9,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["benchmark_baseline", "prior_art_scan"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "reference_class_sourcing_outside_view_first",
                    "stage_id": "outside-view",
                    "rounds": 1,
                    "independent": True,
                    # The novelty quota here is over REFERENCE CLASSES: one class each, and at
                    # least one class per round that no other seat has already named. Everyone
                    # citing the same comparable is a single anchor wearing four hats.
                    "quotas": {"ideas_per_participant": 1, "novel_ideas_per_round": 1},
                    "exit_when": expr(
                        "ALL[custom:reference_classes_named >= 1, "
                        "custom:unresolvable_reference_class_citations <= 0]"
                    ),
                },
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "estimate-1",
                    "participants": estimators,
                    "independent": True,
                    "anonymous": True,
                },
                {
                    "kind": "custom",
                    "custom_name": "extremes_justify_then_reestimate",
                    "stage_id": "extremes-justify",
                    "rounds": 1,
                    "quotas": {"objections_per_participant": 1},
                },
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "estimate-2",
                    "participants": estimators,
                    "independent": True,
                    "anonymous": True,
                    "exit_when": expr("custom:estimate_spread_ratio <= 2"),
                },
                {"kind": "synthesis", "stage_id": "estimate-final"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4},
            "turn": {"max_words": 500},
            "obligations": {
                # No respond-to-prior before the reveal: that IS the anchoring channel planning
                # poker exists to close. After the reveal the extremes MUST justify, which is why
                # rebuttal and cross-examination are on.
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": False,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 40,
            "turns": 18,
            "sources": 6,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 1,
        },
        "targets": {
            "unique_ideas": 4,
            "categories": 2,
            "novelty_ratio": 0.25,
            "evidence_items": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.9,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "score",
            # The score scale IS the estimate card deck; the median is the aggregate, so a single
            # extreme cannot drag the number.
            "score_scale": {"min": 1, "max": 21},
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {"allowed": False, "must_justify": True},
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "confidence_overlap",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": False},
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[custom:unresolvable_reference_class_citations <= 0, custom:reference_classes_named >= 1, "
            "custom:estimate_spread_ratio <= 2, rounds_elapsed >= 2]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 4,
            },
            hard_caps={
                "max_rounds": 4,
                "max_minutes": 60,
                "on_cap": "conditional_decision",
            },
        ),
        "outcomes": {
            "allowed": ["decision", "conditional_decision", "no_decision", "dissent"],
            "conditional_decision_requires": [
                "the estimate is labelled INSIDE-VIEW-ONLY if no reference class resolved",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "split_question",
                "narrow_scope",
                "recruit_independent_critic",
                "run_experiment",
            ],
            "escalation": {"after_attempts": 2, "to": "judge"},
        },
        "anti_failure": {
            "controls": [
                "sycophancy",
                "participant_dominance",
                "hallucinated_expertise",
                "evidence_free_majority",
                "premature_convergence",
                "echo_chamber",
            ],
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
                "confidence_trajectory",
                "evidence_map",
                "votes_by_round",
                "transcript",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            "p35-reference-class-planning-poker",
            calibration={"post_run": True, "score": "crps"},
        ),
        "metadata": {
            "title": "P35 reference-class planning poker (FORECASTING)",
            "owner": OWNER,
            "spec_citations": cite(669, 674, 680, 681),
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P35 reference-class-planning-poker"
            ],
            "notes": (
                "ANTI-FAILURE DEFENCES (6 declared): (1) the card's failure mode is 'reference "
                "class is invented', so custom:unresolvable_reference_class_citations <= 0 is both "
                "the outside-view stage exit and a stopping leaf, with a dedicated anchor-auditor "
                "who cannot vote - an unresolvable class voids the estimate rather than lowering "
                "confidence in it; (2) hallucinated_expertise is the same defence seen from the "
                "seat side; (3) sycophancy and (4) echo_chamber - anchoring on the first or "
                "loudest number - are cut structurally by blind_to_peers estimation with "
                "reveal_after_round=1, must_respond_to_prior=false before the reveal, and a MEDIAN "
                "aggregate so one extreme cannot drag the estimate; (5) participant_dominance is "
                "further limited by abstention.allowed=false, so no seat can sit out and then "
                "criticise; (6) premature_convergence is blocked by rounds.min=2 and the "
                "custom:estimate_spread_ratio <= 2 leaf, which requires the SECOND estimate to "
                "have actually converged. FAST UNANIMITY on a first blind estimate is the "
                "classic sign of a leaked anchor: response is blind_re_evaluation. UNVERIFIED: "
                "the spread ratio of 2 is a placeholder, and the card's claim that this estate has "
                "708 run records usable as a base-rate source is inherited from the design doc and "
                "NOT re-measured here; the settling experiment is to resolve one named reference "
                "class to a real artifact and count what the ledger actually holds."
            ),
        },
    }


# --------------------------------------------------------------------------- P36
def p36_calibration_tournament() -> Dict[str, Any]:
    graded = ["graded-seat-a", "graded-seat-b", "graded-seat-c", "graded-seat-d"]
    roster = [
        agent(
            "graded-seat-a",
            "domain_expert",
            expertise=["the decision domain"],
            vote_weight=1.0,
        ),
        agent(
            "graded-seat-b",
            "domain_expert",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["the decision domain"],
            vote_weight=1.0,
        ),
        agent(
            "graded-seat-c", "critic", expertise=["adversarial review"], vote_weight=1.0
        ),
        agent(
            "graded-seat-d",
            "forecaster",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["estimation"],
            vote_weight=1.0,
        ),
        agent(
            "calibrator",
            "calibrator",
            authority="judge",
            expertise=["kappa", "Brier scoring", "weight governance"],
            rights={"may_speak": True, "may_vote": False},
            briefing=(
                "SHADOW MODE. Record every band and outcome. Hold every weight at 1.0 until a "
                "seat has at least 20 resolutions AND kappa against the owner's own corrections "
                "exceeds 0.6. Disclose n on every report."
            ),
        ),
        agent(
            "demotion-clerk",
            "verifier",
            authority="contributor",
            expertise=["policy enforcement"],
            rights={"may_speak": True, "may_vote": False},
            briefing="A seat below the accuracy floor is demoted to advisory and cannot carry a vote.",
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p36-calibration-tournament",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Stop weighting every seat equally regardless of whether it has ever been right: "
                "every verdict carries a confidence band, outcomes are recorded, and seat weights "
                "move with realised accuracy - with seats below the floor demoted to advisory."
            ),
            "charter": (
                "The only protocol in the catalogue with MEMORY ACROSS COUNCILS. It changes the "
                "WEIGHTS over time rather than the round structure, which is exactly why it ships "
                "in SHADOW: a bad weight silently distorts every later council."
            ),
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "no verdict was accepted without a confidence band",
                "every outcome was recorded with the n it contributes to",
                "no weight left 1.0 while any seat had fewer than 20 resolutions or kappa at or below 0.6",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.85,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": [
                    "exact",
                    "calibration_ranked",
                    "vendor_diverse",
                    "model_diverse",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 3,
                "max_share_per_vendor": 0.6,
            },
            "roster": roster,
            "role_templates": [
                "domain_expert",
                "critic",
                "forecaster",
                "calibrator",
                "verifier",
            ],
            "replacement": {
                "enabled": True,
                "triggers": [
                    "hallucinated_expertise",
                    "inactivity",
                    "policy_violation",
                ],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
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
            "required_artifacts": ["evidence_pack", "benchmark_baseline"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "prediction_confidence",
                    "stage_id": "banded-verdicts",
                    "rounds": 1,
                    "participants": graded,
                    "independent": True,
                    "quotas": {"novel_ideas_per_round": 1},
                    "exit_when": expr("custom:unbanded_verdicts <= 0"),
                },
                {
                    "kind": "custom",
                    "custom_name": "outcome_resolution_recording",
                    "stage_id": "record",
                    "rounds": 1,
                    "participants": ["calibrator"],
                    "exit_when": expr("custom:outcomes_recorded >= 1"),
                },
                {
                    "kind": "custom",
                    "custom_name": "weight_promotion_gate_shadow_until_proven",
                    "stage_id": "promotion-gate",
                    "rounds": 1,
                    "participants": ["calibrator", "demotion-clerk"],
                    # The gate that keeps this protocol in SHADOW. Both conditions are the estate's
                    # existing agent-as-judge thresholds; until BOTH hold, every weight stays 1.0.
                    "exit_when": expr(
                        "ALL[custom:min_resolutions_per_seat >= 20, custom:judge_owner_kappa >= 0.6]"
                    ),
                },
                {"kind": "synthesis", "stage_id": "verdict-and-scores"},
            ],
            "speaking_order": "lowest_confidence_first",
            "rounds": {"min": 1, "max": 3},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "cross_examination": True,
                # The whole protocol collapses without this one.
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 45,
            "turns": 20,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 4,
            "categories": 2,
            "novelty_ratio": 0.25,
            "evidence_items": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "weighted",
            # SHADOW: every weight pinned at 1.0. This is not a placeholder to fill in later - it
            # is the card's shipping configuration until n >= 20 per seat and kappa > 0.6.
            "weights": {
                "graded-seat-a": 1.0,
                "graded-seat-b": 1.0,
                "graded-seat-c": 1.0,
                "graded-seat-d": 1.0,
            },
            "belief_aggregation": {
                "method": "calibration_weighted",
                "require_confidence_per_vote": True,
                "calibration_source": "platform/council/state/p36-calibration-tournament/seat-scores.json",
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
                "strategic_abstention_check": True,
            },
            "tie_break": "owner",
        },
        "consensus": {
            "threshold": 0.7,
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[custom:unbanded_verdicts <= 0, custom:outcomes_recorded >= 1, "
            "all_participants_spoke == true, custom:weights_pinned_until_proven == true]",
            minimum_deliberation={
                "min_rounds": 1,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_evidence_items": 4,
            },
            hard_caps={
                "max_rounds": 3,
                "max_minutes": 60,
                "on_cap": "conditional_decision",
            },
        ),
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "no_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the n behind every seat weight is disclosed with the verdict",
                "any weight that left 1.0 names the kappa and resolution count that authorised it",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "blind_re_evaluation",
                "recruit_independent_critic",
                "escalate_to_owner",
                "declare_no_decision",
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
                "sycophancy",
                "evidence_free_majority",
                "hallucinated_expertise",
                "lost_dissent",
                "collusion",
                "premature_convergence",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "recruit_independent_critic",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "calibration_report",
                "confidence_trajectory",
                "votes_by_round",
                "dissent_minority_report",
                "evidence_map",
                "transcript",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            "p36-calibration-tournament",
            retain_days=365,
            owner_approval_for=[
                "moving any seat weight off 1.0",
                "demoting a seat to advisory",
                "resetting the calibration store",
            ],
            calibration={"post_run": True, "score": "brier"},
        ),
        "metadata": {
            "title": "P36 calibration tournament (FORECASTING, SHADOW, OWNER-DECISION)",
            "owner": OWNER,
            "spec_citations": cite(685, 690, 696, 697),
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P36 calibration-tournament"
            ],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) the card's failure mode is 'weights "
                "learned from too few resolutions', defended by the promotion-gate stage whose "
                "exit requires BOTH custom:min_resolutions_per_seat >= 20 AND "
                "custom:judge_owner_kappa >= 0.6, and by voting.weights being pinned at 1.0 for "
                "every seat right now - SHADOW is the shipped configuration, not a TODO; (2) "
                "strategic_voting and (3) collusion matter more here than anywhere else because a "
                "vote is a durable weight update, so strategic_abstention_check is on and "
                "duplicate_detection covers model AND vendor; (4) sycophancy is answered by "
                "speaking_order=lowest_confidence_first, which puts the least confident seat "
                "first so it cannot fold to a confident peer it has not heard yet; (5) "
                "evidence_free_majority is blocked by evidence_outranks_majority - a weighted vote "
                "with no evidence is the worst possible input to a memory system; (6) "
                "hallucinated_expertise is what the scoring is FOR, and it also triggers "
                "replacement; (7) lost_dissent is met by minority_report=required with "
                "suppression_check. FAST UNANIMITY: blind_re_evaluation first, because unanimity "
                "in a council that writes weights is self-reinforcing. HONEST LIMITS, INLINE: (a) "
                "the calibration store at "
                "platform/council/state/p36-calibration-tournament/seat-scores.json DOES NOT "
                "EXIST, so belief_aggregation.method=calibration_weighted currently degrades to "
                "equal weights - which is exactly what the pinned 1.0 weights already say; (b) "
                "custom:weights_pinned_until_proven is an assertion named in the lane's PRODUCERS map (platform/lib/council_protocols/_shared.py, republished in PROTOCOL-EXPECTATIONS-25-36.json) and NOT implemented, with no "
                "implementation, so today SHADOW mode is a declaration rather than an enforced "
                "invariant, and the settling experiment is the card's own - measure kappa against "
                "the owner's own corrections and require it above 0.6 before any weight moves; (c) "
                "the card marks this OWNER-DECISION: YES and conflicts-with P06 "
                "nominal-group-technique, which is equal-weight by design."
            ),
        },
    }


PROTOCOLS_31_36 = (
    p31_constraint_relaxation,
    p32_counterfactual_council,
    p33_prediction_tournament,
    p34_scenario_planning,
    p35_reference_class_planning_poker,
    p36_calibration_tournament,
)
