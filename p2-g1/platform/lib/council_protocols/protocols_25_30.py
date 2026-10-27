"""Executable CouncilSpec blueprints P25-P30 (PHASE 2C, lane 25-36 of 48).

Source designs: 12-COUNCIL-PROTOCOLS-AND-PRESETS.md, one option card per protocol. This
module turns each card's *concrete mechanism* into a validated CouncilSpec instance; it does
not redesign the card. Where the card names a failure mode or a required proof, that becomes
a real field: a stopping-rule leaf, an anti_failure control, or a stage the run must execute.
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
    injection_defense,
    stopping,
)


# --------------------------------------------------------------------------- P25
def p25_blind_reevaluation() -> Dict[str, Any]:
    jurors = ["blind-juror-a", "blind-juror-b", "blind-juror-c"]
    roster = [
        agent(
            "blind-juror-a",
            "juror",
            expertise=["the decision domain under re-review"],
            fresh_context=True,
            sees_peers=False,
            anonymous=True,
            partition_id="anonymised-option-set",
            briefing="You have never seen this council. Decide from the anonymised option set only.",
        ),
        agent(
            "blind-juror-b",
            "juror",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["independent reproduction"],
            fresh_context=True,
            sees_peers=False,
            anonymous=True,
            partition_id="anonymised-option-set",
            briefing="You have never seen this council. Decide from the anonymised option set only.",
        ),
        agent(
            "blind-juror-c",
            "juror",
            expertise=["adversarial review"],
            fresh_context=True,
            sees_peers=False,
            anonymous=True,
            partition_id="anonymised-option-set",
            briefing="You have never seen this council. Decide from the anonymised option set only.",
        ),
        agent(
            "divergence-auditor",
            "verifier",
            authority="judge",
            expertise=["provenance leak scanning", "verdict comparison"],
            rights={"may_speak": True, "may_vote": False, "may_recruit": True},
            partition_id="sealed-original-verdict",
            briefing=(
                "Hold the sealed original verdict. Run the provenance leak scan over every "
                "anonymised option BEFORE the jurors read it, then compare verdicts."
            ),
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p25-blind-reevaluation",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Re-decide an already-settled question with fresh, attribution-blind seats and "
                "downgrade the original outcome if the blind verdict diverges from it."
            ),
            "charter": (
                "Once a panel has agreed it cannot un-see the agreement. Strip attribution, "
                "ordering and prior verdicts; re-present the options to seats that have never "
                "seen the council; a divergence downgrades the original outcome."
            ),
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "every juror produced an independent position before seeing any peer",
                "the provenance leak scan found zero seat names, model names or file paths in the option text",
                "the blind verdict was compared to the sealed original and the delta is recorded",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.9,
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
                "strategies": ["exact", "vendor_diverse", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_models": 2,
                "max_share_per_vendor": 0.75,
            },
            "roster": roster,
            "role_templates": ["juror", "verifier"],
            "anonymity": {"mode": "double_blind"},
            "information_partition": {
                "enabled": True,
                "strategy": "role_scoped",
                "partitions": [
                    {
                        "partition_id": "anonymised-option-set",
                        "visible_to": jurors,
                        "sources": [
                            "leak-scanned option cards",
                            "anonymised evidence pack",
                        ],
                    },
                    {
                        "partition_id": "sealed-original-verdict",
                        "visible_to": ["divergence-auditor"],
                        "sources": [
                            "original council transcript",
                            "original vote record",
                        ],
                    },
                ],
            },
            "replacement": {
                "enabled": True,
                "triggers": [
                    "conflict_of_interest",
                    "prompt_injection_detected",
                    "hallucinated_expertise",
                ],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt", "model"],
                "max_similarity": 0.85,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "prep_time_minutes": 10,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {"kind": "jury"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "provenance_leak_scan",
                    "stage_id": "leak-scan",
                    "rounds": 1,
                    "participants": ["divergence-auditor"],
                    "exit_when": expr("custom:provenance_leak_count <= 0"),
                },
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "blind-open",
                    "participants": jurors,
                    "independent": True,
                    "anonymous": True,
                },
                {
                    "kind": "jury",
                    "stage_id": "blind-verdict",
                    "rounds": 2,
                    "participants": jurors,
                    "anonymous": True,
                    # Novelty quota, not idea-generation for its own sake: a blind juror who
                    # only restates the pack is a rubber stamp, so each must raise at least one
                    # consideration the anonymised pack does not already contain, per round.
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 1,
                        "novel_ideas_per_round": 1,
                        "ideas_per_participant": 1,
                    },
                    "exit_when": expr(
                        "ALL[independent_positions >= 3, all_participants_spoke == true]"
                    ),
                },
                {
                    "kind": "custom",
                    "custom_name": "divergence_audit_against_sealed_original",
                    "stage_id": "divergence-audit",
                    "rounds": 1,
                    "participants": ["divergence-auditor"],
                },
                {"kind": "synthesis", "stage_id": "reconcile"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "turn": {"max_words": 700},
            "obligations": {
                # No response-to-prior in the blind stage: an obligation to answer a peer is
                # exactly the channel this protocol exists to cut.
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "cross_examination": False,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
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
            "novelty_ratio": 0.3,
            "counterexamples": 3,
            "evidence_items": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "juror",
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
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
            "threshold": 0.75,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": False,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[independent_positions >= 3, all_participants_spoke == true, "
            "custom:provenance_leak_count <= 0, custom:divergence_audit_complete == true]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
                "min_evidence_items": 4,
            },
            hard_caps={
                "max_rounds": 4,
                "max_minutes": 60,
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
                "the original outcome is downgraded to CONDITIONAL until the divergence is explained",
                "the leak scan is clean, otherwise the re-run is void rather than confirming",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "circular_citation_check": True,
            },
            "resolution": [
                "recruit_independent_critic",
                "strongest_counterexample",
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
                "sycophancy",
                "instant_unanimity",
                "echo_chamber",
                "lost_dissent",
                "minority_suppression",
                "moderator_capture",
                "hidden_conflict_of_interest",
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
                "transcript",
                "votes_by_round",
                "dissent_minority_report",
                "evidence_map",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            "p25-blind-reevaluation",
            owner_approval_for=[
                "downgrading a shipped decision",
                "voiding the original verdict",
            ],
        ),
        "metadata": {
            "title": "P25 blind re-evaluation (ANONYMOUS)",
            "owner": OWNER,
            "spec_citations": cite(503, 508, 514, 515),
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P25 blind-reevaluation"],
            "notes": (
                "ANTI-FAILURE DEFENCES (>=3 required, 7 declared): (1) sycophancy and (2) "
                "instant_unanimity are cut structurally - the jurors are fresh_context and never "
                "see the original verdict or each other's first position; (3) echo_chamber is cut "
                "by double_blind anonymity plus a role_scoped information partition; (4) "
                "lost_dissent and (5) minority_suppression are met by minority_report=required "
                "with preserve_verbatim and suppression_check, and outcomes.allowed carries "
                "minority_report; (6) moderator_capture is cut by giving the auditor no vote; (7) "
                "hidden_conflict_of_interest is met by disclosure_required + recuse_from_vote, "
                "which is how a seat that authored the original is kept out. FAST UNANIMITY: this "
                "protocol IS the estate's fast-unanimity remedy, and it still arms its own - "
                "blind_re_evaluation, strongest_counterexample, recruit_independent_critic. "
                "CARD FAILURE MODE MADE EXECUTABLE: 'anonymisation is incomplete and the option "
                "text itself reveals provenance' - custom:provenance_leak_count <= 0 is both a "
                "stage exit condition and a stopping-rule leaf, so a leaky run cannot terminate "
                "successfully. UNVERIFIED: no leak scanner exists yet on this estate, so "
                "custom:provenance_leak_count is named in the lane's PRODUCERS map (platform/lib/council_protocols/_shared.py, republished in PROTOCOL-EXPECTATIONS-25-36.json) and NOT implemented; the "
                "experiment that settles it is the card's own both-states test (inject a "
                "provenance token into an option and confirm the scanner catches it). "
                "custom:divergence_audit_complete is likewise named in the lane's PRODUCERS map (platform/lib/council_protocols/_shared.py, republished in PROTOCOL-EXPECTATIONS-25-36.json) and NOT implemented. The producer cannot live in the JSON leaf itself: SEM-001 requires parse(source_expression) == expression exactly and the parser emits no producer key, so attaching one costs 11 SEM-001 errors and 11 of 12 files (measured, command-center/_proto3_probe_sem001_vs_sem012.py)."
            ),
        },
    }


# --------------------------------------------------------------------------- P26
def p26_brainstorming_swarm() -> Dict[str, Any]:
    seeds = [
        agent(
            "lens-mechanism",
            "proposer",
            expertise=["mechanism design"],
            fresh_context=True,
            sees_peers=False,
            briefing="Lens: novel MECHANISMS only. Do not critique, do not converge.",
        ),
        agent(
            "lens-failure-mode",
            "proposer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["failure analysis"],
            fresh_context=True,
            sees_peers=False,
            briefing="Lens: FAILURE MODES that imply a new option. Do not critique peers.",
        ),
        agent(
            "lens-prior-art",
            "proposer",
            expertise=["prior art", "external literature"],
            fresh_context=True,
            sees_peers=False,
            source_access=["web", "internal_docs"],
            briefing="Lens: PRIOR ART from outside this estate. Cite the external source.",
        ),
        agent(
            "lens-constraint",
            "proposer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["operations research"],
            fresh_context=True,
            sees_peers=False,
            briefing="Lens: what becomes possible if ONE constraint is relaxed.",
        ),
        agent(
            "dedup-clerk",
            "verifier",
            authority="judge",
            expertise=["taxonomy", "mechanical deduplication"],
            rights={"may_speak": True, "may_vote": False},
            briefing=(
                "Deduplicate MECHANICALLY (normalised-text and set-overlap), never by opinion. "
                "Report pairwise idea-set Jaccard per lens pair."
            ),
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p26-brainstorming-swarm",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Produce a wide, mechanically deduplicated option space by binding every seat to "
                "a DISTINCT lens and generating independently and simultaneously."
            ),
            "charter": (
                "N seats each bound to a distinct lens generate with no critique; dedup and "
                "cluster mechanically; stop on unique-idea saturation, not on agreement."
            ),
            "risk_tier": "low",
            "desired_output": "idea_set",
            "success_criteria": [
                "200 unique ideas survive mechanical deduplication",
                "duplicate_ratio stays at or below 0.5 - above that the LENS LIST, not the seat count, is the constraint",
                "pairwise idea-set Jaccard is reported per lens pair so lens collapse is visible",
            ],
            "consensus_intent": "elicit_distribution",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "mixed",
                "strategies": [
                    "expertise_ranked",
                    "model_diverse",
                    "vendor_diverse",
                    "stratified",
                ],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {
                "mode": "elastic",
                "min": 5,
                "max": 24,
                "elastic": {
                    "scale_on": ["idea_starvation", "workload"],
                    "step": 4,
                    "cooldown_rounds": 1,
                },
            },
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_models": 2,
                "min_distinct_expertise": 4,
                "max_share_per_vendor": 0.6,
            },
            "roster": seeds,
            "role_templates": ["proposer", "verifier", "custom:lens_owner"],
            "anonymity": {"mode": "pseudonymous"},
            "recruitment": {
                "dynamic": True,
                "triggers": ["low_novelty", "missing_expertise"],
                "max_recruits": 12,
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["prompt", "expertise", "position_similarity"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 3,
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "brainstorm",
                    "stage_id": "diverge",
                    "rounds": 4,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 15, "novel_ideas_per_round": 5},
                    "exit_when": expr(
                        "ANY[unique_ideas >= 200, no_new_idea_rounds >= 2]"
                    ),
                },
                {
                    "kind": "custom",
                    "custom_name": "mechanical_dedup_and_lens_overlap_report",
                    "stage_id": "dedup",
                    "rounds": 1,
                    "participants": ["dedup-clerk"],
                    "exit_when": expr("duplicate_ratio <= 0.5"),
                },
                {"kind": "nominal_group", "stage_id": "cluster", "rounds": 2},
                {"kind": "synthesis", "stage_id": "catalogue"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 900},
            "obligations": {
                # Divergence phase: critique is BANNED, so no respond-to-prior, no rebuttal,
                # no cross-examination. Those obligations belong to the protocol that judges
                # this option space, not to the one that produces it.
                "must_respond_to_prior": False,
                "must_cite_evidence": False,
                "steelman_before_rebuttal": False,
                "rebuttal_required": False,
                "cross_examination": False,
                "declare_confidence": False,
                "declare_conflicts": True,
            },
            "critique_intensity": "gentle",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 90,
            "turns": 60,
            "speaking_quota_per_participant": 6,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "unique_ideas": 200,
            "raw_ideas": 320,
            "categories": 12,
            "novelty_ratio": 0.6,
            "diversity_index": 0.6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "synthesis_only",
            "evidence_gate": {"reject_evidence_free_majority": True},
            "tie_break": "no_decision",
        },
        "consensus": {
            "measure": "agreement_index",
            "minority_report": "optional",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": False,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[unique_ideas >= 200, duplicate_ratio <= 0.5, no_new_idea_rounds >= 2, "
            "diversity_index >= 0.6]",
            minimum_deliberation={"min_rounds": 3, "min_independent_positions": 4},
            hard_caps={
                "max_rounds": 8,
                "max_minutes": 120,
                "on_cap": "synthesize_best_effort",
            },
        ),
        "outcomes": {"allowed": ["decision", "no_decision", "dissent"]},
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.85},
            "resolution": [
                "recruit_independent_critic",
                "rotate_roles",
                "narrow_scope",
                "split_question",
            ],
            "escalation": {"after_attempts": 3, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "idea_count_gaming",
                "duplicate_novelty",
                "echo_chamber",
                "premature_convergence",
                "participant_dominance",
                "silence",
                "weak_synthesis",
            ],
            "fast_unanimity_response": [
                "forced_dissent",
                "recruit_independent_critic",
                "role_rotation",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "idea_ledger",
                "idea_catalog",
                "option_cards",
                "transcript",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p26-brainstorming-swarm"),
        "metadata": {
            "title": "P26 brainstorming swarm (GENERATIVE)",
            "owner": OWNER,
            "spec_citations": cite(522, 527, 533, 534),
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P26 brainstorming-swarm"],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) idea_count_gaming and (2) "
                "duplicate_novelty are gated by targets.dedup (trivial variants MERGE, they do "
                "not count) and by the duplicate_ratio <= 0.5 leaf in the stopping rule, so a run "
                "cannot buy termination with trivial variants; (3) echo_chamber and (4) "
                "premature_convergence are cut structurally - every seat is fresh_context, "
                "sees_peers_before_first_position is false, and critique is banned in the "
                "divergence stage; (5) participant_dominance is capped by "
                "speaking_quota_per_participant; (6) silence is caught by max_inactivity_rounds "
                "and min_engagement_turns; (7) weak_synthesis is answered by the mechanical dedup "
                "stage plus a required idea_catalog. FAST UNANIMITY in a DIVERGENCE phase means "
                "the lens list collapsed, not that the answer is right, so the response is "
                "forced_dissent + recruit_independent_critic + role_rotation. MECHANICAL, NOT "
                "LLM-JUDGED: dedup is a set/text algorithm per fan-out-contract C4 - on this "
                "estate LLM judgement on a mechanical comparison measured 86% accurate with 100% "
                "of errors pointing at data loss. UNVERIFIED: the 200-unique-idea target and the "
                "0.5 duplicate_ratio ceiling are the card's numbers, not measurements of this "
                "lens list; the settling experiment is one real run reporting unique_ideas and "
                "duplicate_ratio with per-lens-pair Jaccard."
            ),
        },
    }


# --------------------------------------------------------------------------- P27
def p27_design_charrette() -> Dict[str, Any]:
    designers = ["charrette-designer-a", "charrette-designer-b", "charrette-designer-c"]
    roster = [
        agent(
            "charrette-chair",
            "facilitator",
            authority="chair",
            expertise=["design facilitation", "timeboxing"],
            rights={"may_speak": True, "may_vote": False},
        ),
        agent("charrette-designer-a", "designer", expertise=["interaction design"]),
        agent(
            "charrette-designer-b",
            "designer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["systems architecture"],
        ),
        agent(
            "charrette-designer-c",
            "designer",
            expertise=["accessibility", "visual design"],
        ),
        agent(
            "charrette-user-advocate", "user_advocate", expertise=["end-user workflows"]
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p27-design-charrette",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Produce and compare COMPLETE competing designs in short timeboxed cycles rather "
                "than critiquing one design serially."
            ),
            "charter": (
                "Each seat ships a complete candidate every cycle; all candidates are pinned side "
                "by side; seats critique OTHERS and revise OWN; repeat for K cycles, then select."
            ),
            "risk_tier": "moderate",
            "desired_output": "ranked_options",
            "success_criteria": [
                "every seat shipped a COMPLETE candidate in every cycle - a fragment is not a candidate",
                "cycle-1 pairwise candidate distance is at or above the diversity floor",
                "convergence happens at cycle K, not cycle 1",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 4,
                "max_share_per_vendor": 0.8,
            },
            "roster": roster,
            "role_templates": ["designer", "facilitator", "user_advocate"],
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 1},
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "role_collapse", "dominance"],
                "preserve_prior_positions": True,
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity"],
                "max_similarity": 0.75,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "prep_time_minutes": 15,
            "required_artifacts": ["prior_art_scan", "position_memo"],
        },
        "topology": {"kind": "chair_led", "chair": "charrette-chair"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "complete_candidate_ship_cycle",
                    "stage_id": "cycle-ship",
                    "rounds": 3,
                    "participants": designers,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 1, "novel_ideas_per_round": 1},
                    "exit_when": expr("custom:incomplete_candidates <= 0"),
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "critique-others",
                    "rounds": 3,
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 2,
                    },
                },
                {"kind": "nominal_group", "stage_id": "rank", "rounds": 1},
                {"kind": "synthesis", "stage_id": "select"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 3, "max": 5, "divergence_before_convergence": True},
            "turn": {"max_words": 1200, "time_limit_seconds": 900},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": False,
                # You may only attack a candidate after stating its strongest form: the charrette
                # failure mode is one candidate plus tweaks, and cheap teardowns cause it.
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "turns": 45,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 9,
            "categories": 3,
            "novelty_ratio": 0.5,
            "diversity_index": 0.5,
            "objections": 12,
            "counterexamples": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.75,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 4},
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "pairwise_agreement",
            "minority_report": "optional",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[rounds_elapsed >= 3, every_objection_addressed == true, "
            "custom:cycle1_candidate_distance >= 0.25, NOT unresolved_load_bearing_counterexample >= 1]",
            minimum_deliberation={
                "min_rounds": 3,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
                "min_objections_addressed": 6,
            },
            hard_caps={
                "max_rounds": 5,
                "max_minutes": 150,
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
                "a named owner decision on any candidate feature the panel could not rank",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.85,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "rotate_roles",
                "strongest_counterexample",
                "narrow_scope",
                "chair_ruling",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "premature_convergence",
                "participant_dominance",
                "weak_synthesis",
                "echo_chamber",
                "silence",
                "moderator_capture",
                "role_collapse",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "role_rotation",
                "forced_dissent",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "option_cards",
                "argument_ledger",
                "votes_by_round",
                "transcript",
                "dissent_minority_report",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p27-design-charrette"),
        "metadata": {
            "title": "P27 design charrette (GENERATIVE)",
            "owner": OWNER,
            "spec_citations": cite(538, 543, 549, 550),
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P27 design-charrette"],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) premature_convergence is the card's own "
                "failure mode - 'cycles degrade into one candidate plus tweaks' - and it is caught "
                "by the custom:cycle1_candidate_distance >= 0.25 leaf, which fails a run that was "
                "already converged in cycle 1 even though convergence at cycle K is the intended "
                "end state; (2) participant_dominance is capped by speaking_quota_per_participant "
                "and by requiring one candidate per seat per cycle; (3) weak_synthesis is answered "
                "by score voting on a 0-4 rubric plus required option_cards; (4) echo_chamber is "
                "cut by independent candidate production and pseudonymous first cycle; (5) silence "
                "is caught by max_inactivity_rounds=1 and abstention.allowed=false; (6) "
                "moderator_capture is cut by giving the chair no vote (tie_break only); (7) "
                "role_collapse - a designer drifting into pure critique - triggers replacement. "
                "CROSS-EXAMINATION / REBUTTAL / STEELMAN: critique is of OTHERS' candidates only, "
                "revision is of your OWN, and steelman_before_rebuttal is mandatory so a cheap "
                "teardown cannot substitute for a competing design. FAST UNANIMITY: "
                "strongest_counterexample + role_rotation + forced_dissent. UNVERIFIED: the 0.25 "
                "distance floor is a placeholder with no measured distribution behind it; the "
                "settling experiment is the card's own - measure pairwise candidate distance in "
                "cycle 1 versus cycle K on one real charrette and set the floor from that."
            ),
        },
    }


# --------------------------------------------------------------------------- P28
def p28_morphological_analysis() -> Dict[str, Any]:
    roster = [
        agent(
            "morph-chair",
            "facilitator",
            authority="chair",
            expertise=["decomposition"],
            rights={"may_speak": True, "may_vote": True},
        ),
        agent("axis-owner-a", "domain_expert", expertise=["problem decomposition"]),
        agent(
            "axis-owner-b",
            "domain_expert",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["implementation constraints"],
        ),
        agent("axis-owner-c", "architect", expertise=["systems architecture"]),
        agent(
            "feasibility-critic",
            "critic",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["feasibility analysis"],
        ),
        agent(
            "orthogonality-verifier",
            "verifier",
            authority="judge",
            expertise=["set theory", "combinatorics"],
            rights={"may_speak": True, "may_vote": False},
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p28-morphological-analysis",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "Make the option space provably complete by decomposing the decision into "
                "orthogonal parameters and enumerating the cross-product, then marking cells "
                "infeasible with a reason."
            ),
            "charter": (
                "Exhaustiveness is structural, not effortful: this is the only protocol in the "
                "catalogue that can justify a COMPLETENESS claim. Survivors of the grid are the "
                "candidate set."
            ),
            "risk_tier": "moderate",
            "desired_output": "specification",
            "success_criteria": [
                "every known option appears somewhere in the grid - a known option that is missing falsifies the parameterisation",
                "no two parameters are correlated above the orthogonality ceiling",
                "every infeasible cell carries a written reason, not a shrug",
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
                "strategies": ["exact", "expertise_ranked", "vendor_diverse"],
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
                "architect",
                "critic",
                "verifier",
                "facilitator",
            ],
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
            "required_artifacts": ["prior_art_scan", "evidence_pack"],
        },
        "topology": {
            "kind": "committee",
            "committees": [
                {
                    "committee_id": "parameter-axes",
                    "mandate": "extract orthogonal parameters and enumerate values",
                    "members": ["axis-owner-a", "axis-owner-b", "axis-owner-c"],
                },
                {
                    "committee_id": "feasibility",
                    "mandate": "mark cells infeasible WITH a reason",
                    "members": ["feasibility-critic", "morph-chair"],
                },
                {
                    "committee_id": "orthogonality",
                    "mandate": "prove the axes are not double-counting",
                    "members": ["orthogonality-verifier"],
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "brainstorm",
                    "stage_id": "axis-values",
                    "rounds": 2,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 8, "novel_ideas_per_round": 3},
                },
                {
                    "kind": "custom",
                    "custom_name": "orthogonality_check_round",
                    "stage_id": "orthogonality",
                    "rounds": 1,
                    "participants": ["orthogonality-verifier"],
                    "exit_when": expr("custom:axis_pair_correlation <= 0.3"),
                },
                {
                    "kind": "custom",
                    "custom_name": "cross_product_enumeration_and_infeasibility_marking",
                    "stage_id": "grid",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 4},
                    "exit_when": expr(
                        "ALL[completeness_score >= 0.95, custom:unreasoned_infeasible_cells <= 0]"
                    ),
                },
                {"kind": "synthesis", "stage_id": "survivors"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 800},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                # A cell is killed by a REASON, so a rebuttal is mandatory and cross-examination
                # of an infeasibility claim is how a wrongly-killed cell gets resurrected.
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 90,
            "turns": 40,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 40,
            "categories": 5,
            "novelty_ratio": 0.4,
            "coverage_score": 0.95,
            "objections": 10,
            "evidence_items": 8,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "consent_no_objection",
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
            "threshold": 0.8,
            "measure": "agreement_index",
            "minority_report": "optional",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
            },
            "irreducible_disagreement_allowed": False,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ALL[completeness_score >= 0.95, custom:known_option_recall >= 1, "
            "custom:axis_pair_correlation <= 0.3, custom:unreasoned_infeasible_cells <= 0]",
            minimum_deliberation={
                "min_rounds": 2,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
            },
            hard_caps={
                "max_rounds": 6,
                "max_minutes": 120,
                "on_cap": "conditional_decision",
            },
        ),
        "outcomes": {
            "allowed": ["decision", "conditional_decision", "no_decision", "dissent"],
            "conditional_decision_requires": [
                "any axis whose orthogonality could not be shown is disclosed with the cells it may double-count",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "circular_citation_check": True,
            },
            "resolution": [
                "split_question",
                "narrow_scope",
                "recruit_independent_critic",
                "chair_ruling",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "idea_count_gaming",
                "duplicate_novelty",
                "evidence_free_majority",
                "premature_convergence",
                "weak_synthesis",
                "missing_expertise",
                "circular_debate",
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
                "idea_catalog",
                "claim_evidence_contradiction_graph",
                "unresolved_unknowns",
                "transcript",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p28-morphological-analysis"),
        "metadata": {
            "title": "P28 morphological analysis / Zwicky box (GENERATIVE)",
            "owner": OWNER,
            "spec_citations": cite(554, 559, 565, 566),
            "lineage": [
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P28 morphological-analysis"
            ],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) idea_count_gaming and (2) "
                "duplicate_novelty cannot buy completeness here because completeness is measured "
                "against the grid, not the idea count, and targets.dedup MERGES trivial variants; "
                "(3) evidence_free_majority is blocked by "
                "evidence_gate.reject_evidence_free_majority plus consent_no_objection - a cell "
                "dies to a written reason, never to a show of hands; (4) premature_convergence is "
                "blocked by the completeness_score >= 0.95 leaf; (5) weak_synthesis is answered by "
                "a required option_cards + claim_evidence_contradiction_graph; (6) "
                "missing_expertise has a dedicated axis-owner committee per parameter; (7) "
                "circular_debate is caught by circular_citation_check. THE CARD'S FAILURE MODE IS "
                "THE MAIN LEAF: 'parameters are not orthogonal so the cross-product "
                "double-counts' - custom:axis_pair_correlation <= 0.3 is enforced as a stage exit "
                "AND a stopping leaf, and custom:known_option_recall >= 1 encodes the card's "
                "falsification test that every already-known option must appear as a cell. "
                "COMPLETENESS IS A CLAIM WITH A DETECTOR: an unreasoned infeasible cell "
                "(custom:unreasoned_infeasible_cells) is treated as an unproven kill, not a "
                "survivor. UNVERIFIED: the 0.3 correlation ceiling and the 0.95 completeness "
                "score are the card's shape, not measured values; both are settled by running the "
                "grid against a decision whose option set is already known."
            ),
        },
    }


# --------------------------------------------------------------------------- P29
def p29_triz_contradiction() -> Dict[str, Any]:
    roster = [
        agent(
            "triz-chair",
            "moderator",
            authority="chair",
            expertise=["contradiction framing"],
            rights={"may_speak": True, "may_vote": False},
        ),
        agent(
            "separation-in-time",
            "proposer",
            expertise=["TRIZ separation principles"],
            briefing="Resolve by separation in TIME. A tradeoff answer is out of scope.",
        ),
        agent(
            "separation-in-space",
            "proposer",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["TRIZ separation principles"],
            briefing="Resolve by separation in SPACE. A tradeoff answer is out of scope.",
        ),
        agent(
            "separation-in-condition",
            "proposer",
            expertise=["TRIZ separation principles"],
            briefing="Resolve by separation in CONDITION or SCALE. A tradeoff answer is out of scope.",
        ),
        agent(
            "tradeoff-gatekeeper",
            "critic",
            model="gpt-5-codex",
            vendor="openai",
            authority="judge",
            expertise=["scope enforcement"],
            rights={"may_speak": True, "may_vote": True},
            briefing="Reject any answer that improves A by worsening B. That is the banned answer.",
        ),
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p29-triz-contradiction",
        "participation": "agent_only",
        "objective": {
            "statement": (
                "State the decision as a contradiction (improving A worsens B) and require "
                "resolutions that improve A WITHOUT worsening B; a compromise answer is rejected "
                "as out of scope."
            ),
            "charter": (
                "One round, then fall through. This protocol bans the compromise answer that "
                "every tradeoff protocol is trying to optimise, so it is a PRE-PASS, not a "
                "replacement for one."
            ),
            "risk_tier": "low",
            "desired_output": "recommendation",
            "success_criteria": [
                "at least one resolution improves A with no measured worsening of B",
                "every compromise answer was rejected with the axis it traded away named",
                "if no dissolving resolution exists the council returns NO_DECISION and the caller falls through to a tradeoff protocol",
            ],
            "consensus_intent": "seek_consensus",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
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
            "count": exact_count(roster),
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 2,
                "max_share_per_vendor": 0.7,
            },
            "roster": roster,
            "role_templates": ["proposer", "critic", "moderator"],
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {
            "research_required": False,
            "independent_prep": True,
            "min_sources": 1,
            "required_artifacts": ["position_memo"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "contradiction_framing",
                    "stage_id": "frame",
                    "rounds": 1,
                    "participants": ["triz-chair"],
                    "exit_when": expr("custom:contradiction_pairs_named >= 1"),
                },
                {
                    "kind": "brainstorm",
                    "stage_id": "separation-resolutions",
                    "rounds": 1,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 4, "novel_ideas_per_round": 4},
                },
                {
                    "kind": "custom",
                    "custom_name": "tradeoff_answer_rejection",
                    "stage_id": "scope-gate",
                    "rounds": 1,
                    "participants": ["tradeoff-gatekeeper"],
                    "exit_when": expr("custom:unrejected_tradeoff_answers <= 0"),
                },
                {"kind": "synthesis", "stage_id": "resolutions"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 1, "max": 2, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                # The gatekeeper must state the resolution at its strongest before rejecting it,
                # otherwise "that is really a tradeoff" becomes a way to kill any hard idea.
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "cross_examination": True,
                "declare_confidence": True,
                "declare_conflicts": False,
            },
            "critique_intensity": "adversarial",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 30,
            "turns": 15,
            "min_engagement_turns": 1,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 1,
        },
        "targets": {
            "unique_ideas": 12,
            "categories": 4,
            "novelty_ratio": 0.7,
            "objections": 4,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "consent_no_objection",
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "measure": "agreement_index",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": stopping(
            "ANY[ALL[custom:dissolving_resolutions >= 1, custom:unrejected_tradeoff_answers <= 0], "
            "max_rounds == 2]",
            minimum_deliberation={
                "min_rounds": 1,
                "min_independent_positions": 3,
                "min_evidence_items": 2,
            },
            hard_caps={"max_rounds": 2, "max_minutes": 40, "on_cap": "no_decision"},
        ),
        "outcomes": {
            "allowed": ["decision", "no_decision", "proof_of_impossibility", "dissent"],
            "conditional_decision_requires": [],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 1, "repetition_similarity": 0.9},
            "resolution": ["declare_no_decision", "narrow_scope", "split_question"],
            "escalation": {"after_attempts": 1, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "premature_convergence",
                "endless_debate",
                "weak_synthesis",
                "echo_chamber",
                "role_collapse",
                "idea_count_gaming",
            ],
            "fast_unanimity_response": ["strongest_counterexample", "forced_dissent"],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "option_cards",
                "argument_ledger",
                "unresolved_unknowns",
                "transcript",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p29-triz-contradiction", determinism="seeded"),
        "metadata": {
            "title": "P29 TRIZ contradiction (GENERATIVE)",
            "owner": OWNER,
            "spec_citations": cite(570, 575, 581, 582),
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P29 triz-contradiction"],
            "notes": (
                "ANTI-FAILURE DEFENCES (6 declared): (1) endless_debate is structurally "
                "impossible - the card caps this protocol at one round and the stopping rule's "
                "second branch fires at max_rounds == 2 with on_cap=no_decision, so the caller "
                "falls through to a tradeoff protocol instead of grinding; (2) "
                "premature_convergence is blocked because a resolution only counts if "
                "custom:dissolving_resolutions >= 1 AND every compromise answer was explicitly "
                "rejected; (3) weak_synthesis is answered by a required argument_ledger naming the "
                "separation principle used; (4) echo_chamber is cut by independent simultaneous "
                "generation with one separation axis per seat; (5) role_collapse - the "
                "gatekeeper becoming a proposer, or a proposer smuggling a tradeoff - is caught by "
                "the scope-gate stage's own exit condition; (6) idea_count_gaming is blocked by "
                "trivial_variant_policy=reject, the strictest setting in the schema, because a "
                "'resolution' that is a relabelled compromise is exactly a trivial variant. "
                "STOPPING RULE IS DELIBERATELY DISJUNCTIVE: ANY[dissolved, cap-reached] is the "
                "card's fall-through, and it is the one rule in this lane where a single-leaf "
                "flip is SUPPOSED to survive - that is OR semantics, not a decorative condition. "
                "UNVERIFIED: the card asks for a run against a known dissolved contradiction from "
                "this estate (sterile-cockpit versus coverage) and that run has not happened; "
                "until it does, confidence in this protocol stays at the card's roughly even "
                "40-60%."
            ),
        },
    }


# --------------------------------------------------------------------------- P30
def p30_six_hats_rotation() -> Dict[str, Any]:
    hats = ["hat-seat-a", "hat-seat-b", "hat-seat-c", "hat-seat-d"]
    roster = [
        agent(
            "blue-hat-chair",
            "facilitator",
            authority="chair",
            expertise=["process control", "off-hat rejection"],
            rights={"may_speak": True, "may_vote": False},
            briefing="You hold the blue hat permanently: reject any off-hat contribution on sight.",
        ),
        agent("hat-seat-a", "domain_expert", expertise=["the decision domain"]),
        agent(
            "hat-seat-b",
            "domain_expert",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["the decision domain"],
        ),
        agent("hat-seat-c", "risk_officer", expertise=["risk analysis"]),
        agent(
            "hat-seat-d",
            "user_advocate",
            model="gpt-5-codex",
            vendor="openai",
            expertise=["end-user impact"],
        ),
    ]

    def hat_stage(
        stage_id: str, quotas: Dict[str, int] | None = None
    ) -> Dict[str, Any]:
        """One synchronised hat round: every seat wears the SAME hat at the same time."""
        stage: Dict[str, Any] = {
            "kind": "six_hats",
            "stage_id": stage_id,
            "rounds": 1,
            "participants": hats,
        }
        if quotas:
            stage["quotas"] = quotas
        return stage

    return {
        "schema_version": "1.0.0",
        "council_id": "p30-six-hats-rotation",
        "participation": "hybrid",
        "objective": {
            "statement": (
                "Separate facts, intuition, risk, upside, alternatives and process by making ALL "
                "seats wear the SAME hat at the same time and rotate together, one hat per round."
            ),
            "charter": (
                "Parallel same-mode thinking. Every other role protocol assigns DIFFERENT lenses "
                "simultaneously; this one deliberately assigns the same one so each mode is done "
                "properly once instead of badly six times."
            ),
            "risk_tier": "low",
            "desired_output": "recommendation",
            "success_criteria": [
                "all six hats were worn, in order, by every seat",
                "the off-hat contribution rate is at or below 5% - the chair rejected the rest",
                "the green-hat round produced alternatives that no other round produced",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "stakeholder_balanced", "model_diverse"],
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
                "risk_officer",
                "user_advocate",
                "facilitator",
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "inactivity", "dominance"],
                "preserve_prior_positions": True,
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity"],
                "max_similarity": 0.85,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": False,
            "min_sources": 2,
            "required_artifacts": ["evidence_pack"],
        },
        "topology": {"kind": "chair_led", "chair": "blue-hat-chair"},
        "protocol": {
            "sequence": [
                hat_stage("white-facts"),
                hat_stage("red-intuition"),
                hat_stage(
                    "black-risk",
                    {"objections_per_participant": 2, "counterexamples_per_round": 2},
                ),
                hat_stage("yellow-upside"),
                hat_stage(
                    "green-alternatives",
                    {"ideas_per_participant": 3, "novel_ideas_per_round": 3},
                ),
                {
                    "kind": "custom",
                    "custom_name": "blue_hat_process_review_and_off_hat_audit",
                    "stage_id": "blue-process",
                    "rounds": 1,
                    "participants": ["blue-hat-chair"],
                    "exit_when": expr("custom:off_hat_contribution_rate <= 0.05"),
                },
                {"kind": "synthesis", "stage_id": "converge"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 6, "max": 7},
            "turn": {"max_words": 400, "time_limit_seconds": 240},
            "obligations": {
                # Same-hat parallel thinking: answering a peer inside a hat round is how hats
                # leak into each other, so respond-to-prior and rebuttal are OFF during hats.
                "must_respond_to_prior": False,
                "must_cite_evidence": False,
                "steelman_before_rebuttal": True,
                "rebuttal_required": False,
                "cross_examination": False,
                "declare_confidence": True,
                "declare_conflicts": False,
            },
            "critique_intensity": "gentle",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 60,
            "turns": 35,
            "speaking_quota_per_participant": 7,
            "min_engagement_turns": 6,
            "max_inactivity_rounds": 1,
        },
        "targets": {
            "unique_ideas": 12,
            "categories": 6,
            "novelty_ratio": 0.5,
            "objections": 8,
            "counterexamples": 8,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "synthesis_only",
            "abstention": {"allowed": False, "must_justify": True},
            "evidence_gate": {"reject_evidence_free_majority": True},
            "tie_break": "owner",
        },
        "consensus": {
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
            "ALL[rounds_elapsed >= 6, all_participants_spoke == true, "
            "custom:off_hat_contribution_rate <= 0.05, custom:hats_worn >= 6]",
            minimum_deliberation={
                "min_rounds": 6,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
            },
            hard_caps={
                "max_rounds": 7,
                "max_minutes": 75,
                "on_cap": "synthesize_best_effort",
            },
        ),
        "outcomes": {
            "allowed": ["decision", "no_decision", "minority_report", "dissent"]
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "rotate_roles",
                "narrow_scope",
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
                "role_collapse",
                "echo_chamber",
                "participant_dominance",
                "silence",
                "premature_convergence",
                "moderator_capture",
                "lost_dissent",
            ],
            "fast_unanimity_response": [
                "role_rotation",
                "forced_dissent",
                "strongest_counterexample",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "transcript",
                "idea_ledger",
                "unresolved_unknowns",
                "dissent_minority_report",
                "final_recommendation",
                "action_plan",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit("p30-six-hats-rotation", determinism="best_effort"),
        "metadata": {
            "title": "P30 six hats rotation (GENERATIVE)",
            "owner": OWNER,
            "spec_citations": cite(586, 591, 597, 598),
            "lineage": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md#P30 six-hats-rotation"],
            "notes": (
                "ANTI-FAILURE DEFENCES (7 declared): (1) role_collapse is THE failure mode of "
                "this protocol - the card's 'seats leak black-hat content into the yellow round' - "
                "and it is enforced by custom:off_hat_contribution_rate <= 0.05 as both the "
                "blue-hat stage exit and a stopping leaf, plus replacement on role_collapse; (2) "
                "echo_chamber is limited by same-hat parallel writing with respond-to-prior OFF "
                "inside a hat round; (3) participant_dominance is capped by "
                "speaking_quota_per_participant=7, one turn per hat; (4) silence is caught by "
                "min_engagement_turns=6 (a seat must speak in every hat) and abstention.allowed "
                "false; (5) premature_convergence is blocked by rounds.min=6 - no synthesis "
                "before all six hats; (6) moderator_capture is cut by giving the blue-hat chair "
                "no vote; (7) lost_dissent is met by minority_report=required with "
                "suppression_check, and outcomes.allowed carries minority_report. PARTICIPATION IS "
                "HYBRID because the card recommends this for owner-facing exploratory sessions, "
                "and tie_break=owner reflects that. UNVERIFIED: the 5% off-hat ceiling is a "
                "placeholder; the card's settling experiment is to classify contributions by hat "
                "with a KEYWORD CONTROL first - a classifier that has not been shown to fire on a "
                "known off-hat contribution measures nothing."
            ),
        },
    }


PROTOCOLS_25_30 = (
    p25_blind_reevaluation,
    p26_brainstorming_swarm,
    p27_design_charrette,
    p28_morphological_analysis,
    p29_triz_contradiction,
    p30_six_hats_rotation,
)
