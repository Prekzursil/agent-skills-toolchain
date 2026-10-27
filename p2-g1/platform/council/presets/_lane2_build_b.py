"""Lane-2 preset builders, batch B: design indices 19-22 (C-S19 .. C-S22)."""

from __future__ import annotations

from typing import Any, Dict

from _lane2_build_a import NO_IMPOSSIBILITY
from _lane2_common import (
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
    audit,
    injection_defense,
    notes,
    outcomes,
)

DEFER_ONLY = ["INSUFFICIENT_EVIDENCE", "CONDITIONAL_DECISION", "DEFER"]
CONSENSUS_ONLY = ["CONSENSUS", "MAJORITY_WITH_DISSENT"]


def _agent(pid, name, role, model, vendor, *, authority="voter", effort="high", **kw):
    p = {
        "participant_id": pid,
        "display_name": name,
        "kind": "agent",
        "model": model,
        "vendor": vendor,
        "role": role,
        "authority": authority,
        "effort": effort,
    }
    p.update(kw)
    return p


def p19_socratic_chair_plus_4() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s19-socratic-chair-plus-4",
        "preset": "requirements_council",
        "participation": "agent_only",
        "objective": {
            "statement": "Examine every stated premise or requirement until each is grounded in an "
            "artifact or explicitly flagged as ungrounded.",
            "charter": "Socratic premise examination. The questioner emits ZERO declarative claims; "
            "it only asks. Nothing is decided here - the output is a grounded/flagged premise ledger.",
            "risk_tier": "moderate",
            "desired_output": "specification",
            "success_criteria": [
                "every premise is either grounded at a file:line anchor or carries an explicit ungrounded flag",
                "the questioner made no declarative claim of its own",
                "each ungrounded premise names the experiment that would settle it",
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
                "strategies": ["exact"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 3},
            "roster": [
                _agent(
                    "questioner",
                    "Questioner (asks only, never asserts)",
                    "custom:socratic_questioner",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="xhigh",
                    rights={"may_speak": True, "may_vote": False},
                ),
                _agent(
                    "respondent",
                    "Respondent (defends the premises)",
                    "custom:respondent",
                    "gpt-5-codex",
                    "openai",
                    authority="contributor",
                    rights={"may_speak": True, "may_vote": False},
                ),
                _agent(
                    "assumption-auditor",
                    "Assumption auditor (rates each premise high/medium/low)",
                    "custom:assumption_auditor",
                    "opus-5",
                    "anthropic",
                    authority="contributor",
                    rights={"may_speak": True, "may_vote": False},
                    independence={"fresh_context": True},
                ),
                _agent(
                    "evidence-clerk",
                    "Evidence clerk (holds the anchors)",
                    "custom:evidence_clerk",
                    "opus-5",
                    "anthropic",
                    authority="contributor",
                    source_access=["repo", "internal_docs"],
                    rights={"may_speak": True, "may_vote": False},
                ),
                _agent(
                    "scribe",
                    "Scribe (premise ledger)",
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
            "research_required": False,
            "independent_prep": True,
            "required_artifacts": ["position_memo"],
        },
        "topology": {"kind": "chair_led", "chair": "questioner"},
        "protocol": {
            "sequence": [
                {"kind": "socratic", "stage_id": "interrogate", "rounds": 3},
                {
                    "kind": "custom",
                    "stage_id": "assumption-ledger",
                    "custom_name": "assumption ledger with high/medium/low confidence per premise",
                    "participants": ["assumption-auditor", "evidence-clerk"],
                },
                {
                    "kind": "synthesis",
                    "stage_id": "premise-ledger",
                    "participants": ["scribe"],
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 3, "max": 5},
            "turn": {"max_words": 400},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "declare_confidence": True,
            },
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 30,
            "tool_calls": 80,
            "turns": 24,
        },
        "targets": {"evidence_items": 8, "coverage_score": 0.9},
        "voting": {"method": "synthesis_only", "tie_break": "no_decision"},
        "consensus": {
            "measure": "agreement_index",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
            "irreducible_disagreement_allowed": True,
        },
        "stopping": {
            "source_expression": "every_objection_addressed == true AND evidence_items >= 8",
            "expression": {
                "all_of": [
                    {"metric": "every_objection_addressed", "op": "==", "value": True},
                    {"metric": "evidence_items", "op": ">=", "value": 8},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_evidence_items": 8,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 30,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(
            DEFER_ONLY, ["every ungrounded premise names its settling experiment"]
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": ["split_question", "narrow_scope", "escalate_to_owner"],
            "escalation": {"after_attempts": 2, "to": "owner"},
        },
        "anti_failure": {
            "controls": [
                "circular_citation",
                "role_collapse",
                "sycophancy",
                "weak_synthesis",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "transcript",
                "unresolved_unknowns",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(retain_days=60, owner_approval_for=[], forbid_irreversible=True),
        "metadata": {
            "title": "Socratic premise examination (chair + 4)",
            "owner": "Prekzursil",
            "lineage": [
                "C-S19 socratic-chair-plus-4",
                "P49 socratic-interrogation",
                "P39 key-assumptions-check",
            ],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1415-1428"],
            "notes": notes(
                card="C-S19 socratic-chair-plus-4",
                seats_declared=5,
                roles_line="questioner,respondent,assumption_auditor,evidence_clerk,scribe",
                preset_label_rationale="requirements_council - NEAREST archetype in the schema's "
                "preset_name enum, not an exact match. The card's decision_type is "
                "premise_examination; a requirements council is the archetype that interrogates "
                "stated requirements until each is grounded. If another lane builds a closer "
                "requirements_council, this label should yield to it and become 'custom'.",
                dials={
                    "$.protocol.rounds.max + $.stopping.hard_caps.max_rounds": "depth_cap dial from the card",
                    "$.stopping.expression": "raise evidence_items to demand more anchors per premise",
                    "$.voting.method": "synthesis_only by design - this council decides NOTHING; "
                    "switching it to a voting method changes the council's kind, not just a dial",
                },
                outcome_lineage=DEFER_ONLY,
                extra="outcomes.allowed deliberately EXCLUDES 'decision': the card's outcome list is "
                "INSUFFICIENT_EVIDENCE|CONDITIONAL_DECISION|DEFER only. A premise examination that "
                "returns a decision has exceeded its charter.",
            ),
        },
    }


def p20_charrette_5_design() -> Dict[str, Any]:
    designers = [
        ("designer-1", "Designer 1", "opus-5", "anthropic"),
        ("designer-2", "Designer 2", "gpt-5-codex", "openai"),
        ("designer-3", "Designer 3", "gemini-3-pro", "google"),
        ("designer-4", "Designer 4", "opus-5", "anthropic"),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s20-charrette-5-design",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Choose a design direction by having every seat ship a COMPLETE competing "
            "candidate each cycle, then comparing candidates pairwise.",
            "charter": "Design charrette. A partial sketch is not a candidate. Candidates must stay "
            "far apart in design space - convergence before divergence is the failure mode.",
            "risk_tier": "moderate",
            "desired_output": "ranked_options",
            "success_criteria": [
                "at least two full cycles ran",
                "every seat shipped a COMPLETE candidate in every cycle",
                "candidate-to-candidate distance stayed above the diversity floor",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {"citation_required": True, "anchor_style": "any"},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5, "min": 5, "max": 5},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_models": 3},
            "roster": [
                _agent(
                    d[0],
                    d[1],
                    "designer",
                    d[2],
                    d[3],
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                )
                for d in designers
            ]
            + [
                _agent(
                    "user-advocate",
                    "User advocate (speaks for the person who has to use it)",
                    "user_advocate",
                    "opus-5",
                    "anthropic",
                    authority="voter",
                    rights={"may_speak": True, "may_vote": True},
                )
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt"],
                "max_similarity": 0.7,
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["prior_art_scan"],
        },
        "topology": {
            "kind": "pairwise_tournament",
            "tournament": {
                "pairing": "round_robin",
                "comparisons_per_pair": 1,
                "aggregation": "copeland",
            },
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "brainstorm",
                    "stage_id": "cycle-1",
                    "independent": True,
                    "quotas": {"ideas_per_participant": 1},
                },
                {
                    "kind": "brainstorm",
                    "stage_id": "cycle-2",
                    "quotas": {"ideas_per_participant": 1, "novel_ideas_per_round": 3},
                },
                {
                    "kind": "custom",
                    "stage_id": "pairwise",
                    "custom_name": "pairwise candidate comparison",
                },
                {"kind": "synthesis", "stage_id": "direction"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "turn": {"max_words": 800},
            "obligations": {"must_cite_evidence": True, "declare_confidence": True},
            "critique_intensity": "standard",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 60,
            "tool_calls": 150,
            "turns": 30,
        },
        "targets": {
            "unique_ideas": 10,
            "raw_ideas": 10,
            "diversity_index": 0.6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.7,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "condorcet",
            "quorum": {"min_voters": 4, "on_failure": "extend_rounds"},
            "abstention": {"allowed": False, "counts_toward_quorum": False},
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "pairwise_agreement",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": True},
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "source_expression": "rounds_elapsed >= 2 AND diversity_index >= 0.6",
            "expression": {
                "all_of": [
                    {"metric": "rounds_elapsed", "op": ">=", "value": 2},
                    {"metric": "diversity_index", "op": ">=", "value": 0.6},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 4,
                "max_minutes": 60,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(NO_IMPOSSIBILITY),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.85},
            "resolution": [
                "rotate_roles",
                "blind_re_evaluation",
                "narrow_scope",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
        },
        "anti_failure": {
            "controls": [
                "premature_convergence",
                "duplicate_novelty",
                "instant_unanimity",
                "sycophancy",
                "participant_dominance",
                "prompt_injection",
            ],
            "fast_unanimity_response": ["blind_re_evaluation", "forced_dissent"],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "option_cards",
                "idea_catalog",
                "votes_by_round",
                "transcript",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(retain_days=60, owner_approval_for=[], forbid_irreversible=True),
        "metadata": {
            "title": "Design charrette (4 designers + user advocate)",
            "owner": "Prekzursil",
            "lineage": ["C-S20 charrette-5-design", "P27 design-charrette"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1429-1442"],
            "notes": notes(
                card="C-S20 charrette-5-design",
                seats_declared=5,
                roles_line="designer_x4,user_advocate",
                preset_label_rationale="custom - no design-direction archetype exists among the 24 "
                "required preset names.",
                dials={
                    "$.protocol.rounds.min + $.stopping.expression rounds_elapsed": "cycles dial (keep the two aligned)",
                    "$.stopping.expression diversity_index + $.targets.diversity_index": "distance_floor dial",
                    "$.targets.dedup.max_similarity": "how close two candidates may be before one is rejected as a trivial variant",
                },
                outcome_lineage=NO_IMPOSSIBILITY,
                extra="targets.unique_ideas is set to 10 (5 seats x 2 cycles) so the idea accounting "
                "matches the protocol; the stopping rule does NOT gate on an idea count, so no "
                "SEM-007 obligation is created.",
            ),
        },
    }


def p21_six_hats_6() -> Dict[str, Any]:
    hats = [
        ("hat-white", "White hat (facts only)", "information and facts"),
        ("hat-red", "Red hat (feelings)", "intuition and emotional reaction"),
        ("hat-black", "Black hat (caution)", "risks and failure modes"),
        ("hat-yellow", "Yellow hat (benefits)", "value and upside"),
        ("hat-green", "Green hat (creativity)", "alternatives and new options"),
        ("hat-blue", "Blue hat (process)", "process control and synthesis"),
    ]
    vendors = ["anthropic", "openai", "google", "anthropic", "openai", "anthropic"]
    models = [
        "opus-5",
        "gpt-5-codex",
        "gemini-3-pro",
        "opus-5",
        "gpt-5-codex",
        "opus-5",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s21-six-hats-6",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Explore a question from all six de Bono perspectives, one hat per round, "
            "with off-hat contributions rejected.",
            "charter": "Six-hats rotation. Every seat wears the SAME hat in a given round; the value "
            "comes from synchronised perspective, so an off-hat contribution is rejected, not merged.",
            "risk_tier": "low",
            "desired_output": "recommendation",
            "success_criteria": [
                "all six hats ran, in order",
                "no off-hat contribution was accepted into the ledger",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 2},
            "roster": [
                _agent(
                    h[0],
                    h[1],
                    "domain_expert",
                    models[i],
                    vendors[i],
                    authority="contributor",
                    effort="medium",
                    expertise=[h[2]],
                    rights={"may_speak": True, "may_vote": False},
                )
                for i, h in enumerate(hats)
            ],
            "conflicts_policy": {
                "disclosure_required": False,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {"research_required": False, "independent_prep": False},
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "six_hats",
                    "stage_id": f"round-{h[0].split('-')[1]}",
                    "rounds": 1,
                }
                for h in hats
            ]
            + [{"kind": "synthesis", "stage_id": "blue-synthesis"}],
            "speaking_order": "round_robin",
            "rounds": {"min": 6, "max": 6},
            "turn": {"max_words": 300},
            "obligations": {"must_respond_to_prior": False},
            "critique_intensity": "gentle",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 30,
            "turns": 42,
            "tool_calls": 40,
        },
        "targets": {"unique_ideas": 18, "categories": 6},
        "voting": {"method": "synthesis_only", "tie_break": "chair"},
        "consensus": {
            "measure": "agreement_index",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": False},
        },
        "stopping": {
            "source_expression": "rounds_elapsed >= 6 AND all_participants_spoke == true",
            "expression": {
                "all_of": [
                    {"metric": "rounds_elapsed", "op": ">=", "value": 6},
                    {"metric": "all_participants_spoke", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {"min_rounds": 6, "every_participant_spoke": True},
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 30,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(NO_IMPOSSIBILITY),
        "deadlock": {
            "detection": {"no_progress_rounds": 3},
            "resolution": ["chair_ruling", "declare_no_decision"],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "role_collapse",
                "silence",
                "weak_synthesis",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "idea_ledger",
                "transcript",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(retain_days=30, owner_approval_for=[], forbid_irreversible=True),
        "metadata": {
            "title": "Six hats rotation (6 seats, one hat per round)",
            "owner": "Prekzursil",
            "lineage": ["C-S21 six-hats-6", "P30 six-hats-rotation"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1443-1456"],
            "notes": notes(
                card="C-S21 six-hats-6",
                seats_declared=6,
                roles_line="any_x6 (synchronised hats)",
                preset_label_rationale="custom - exploration is not one of the 24 required archetypes.",
                dials={
                    "$.protocol.sequence": "hat_order dial - reorder the six stages to change the hat order",
                    "$.protocol.turn.max_words": "how much each seat may say per hat",
                    "$.targets.unique_ideas": "expected idea yield (6 seats x 3); NOT gated by the "
                    "stopping rule, so lowering it cannot stall the council",
                },
                outcome_lineage=NO_IMPOSSIBILITY,
                extra="The card's roles line is 'any_x6', so the roster uses domain_expert for every "
                "seat and carries the hat in display_name + expertise. The hat is a STAGE property "
                "here, not a seat property - that is what 'synchronised hats' means.",
            ),
        },
    }


def p22_nominal_group_6() -> Dict[str, Any]:
    gens = [
        ("gen-1", "opus-5", "anthropic"),
        ("gen-2", "gpt-5-codex", "openai"),
        ("gen-3", "gemini-3-pro", "google"),
        ("gen-4", "opus-5", "anthropic"),
        ("gen-5", "gpt-5-codex", "openai"),
        ("gen-6", "opus-5", "anthropic"),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "c-s22-nominal-group-6",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Enumerate the option space by silent independent generation, then a "
            "clarification-only round, then independent ranking.",
            "charter": "Nominal group technique. The clarification round may contain NO evaluative "
            "sentence - evaluation there is what collapses independence and produces anchoring.",
            "risk_tier": "low",
            "desired_output": "ranked_options",
            "success_criteria": [
                "generation was silent and independent - no seat saw another before submitting",
                "the clarification round contained zero evaluative sentences",
                "ranking was independent, not discussed",
            ],
            "consensus_intent": "elicit_distribution",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 7, "min": 7, "max": 7},
            "diversity": {"min_distinct_vendors": 3},
            "roster": [
                _agent(
                    g[0],
                    f"Generalist {g[0][-1]}",
                    "domain_expert",
                    g[1],
                    g[2],
                    authority="voter",
                    effort="medium",
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                )
                for g in gens
            ]
            + [
                _agent(
                    "facilitator",
                    "Facilitator (enforces the no-evaluation rule)",
                    "facilitator",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="medium",
                    rights={"may_speak": True, "may_vote": False},
                )
            ],
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 3},
            "conflicts_policy": {
                "disclosure_required": False,
                "on_conflict": "disclose_only",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity"],
                "max_similarity": 0.8,
            },
        },
        "preparation": {"research_required": False, "independent_prep": True},
        "topology": {"kind": "chair_led", "chair": "facilitator"},
        "protocol": {
            "sequence": [
                {
                    "kind": "nominal_group",
                    "stage_id": "silent-generation",
                    "independent": True,
                    "anonymous": True,
                    "quotas": {"ideas_per_participant": 4},
                },
                {"kind": "round_robin", "stage_id": "clarification-only", "rounds": 1},
                {
                    "kind": "custom",
                    "stage_id": "independent-rank",
                    "custom_name": "independent ranking, no discussion",
                    "independent": True,
                },
                {"kind": "synthesis", "stage_id": "aggregate"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 4, "max": 4},
            "turn": {"max_words": 250},
            "obligations": {"must_respond_to_prior": False},
            "critique_intensity": "gentle",
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 25,
            "turns": 28,
            "tool_calls": 30,
        },
        "targets": {
            "unique_ideas": 24,
            "raw_ideas": 28,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "ranked_choice",
            "quorum": {"min_voters": 5, "on_failure": "extend_rounds"},
            "abstention": {"allowed": False, "counts_toward_quorum": False},
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.5,
            "measure": "pairwise_agreement",
            "minority_report": "optional",
            "dissent_policy": {"preserve_verbatim": True, "attributed": False},
        },
        "stopping": {
            "source_expression": "rounds_elapsed >= 4 AND unique_ideas >= 24 AND all_participants_spoke == true",
            "expression": {
                "all_of": [
                    {"metric": "rounds_elapsed", "op": ">=", "value": 4},
                    {"metric": "unique_ideas", "op": ">=", "value": 24},
                    {"metric": "all_participants_spoke", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 4,
                "every_participant_spoke": True,
                "min_independent_positions": 6,
            },
            "hard_caps": {
                "max_rounds": 4,
                "max_minutes": 25,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(CONSENSUS_ONLY),
        "deadlock": {
            "detection": {"no_progress_rounds": 2},
            "resolution": ["chair_ruling", "narrow_scope"],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "idea_count_gaming",
                "duplicate_novelty",
                "participant_dominance",
                "premature_convergence",
                "prompt_injection",
            ],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "idea_catalog",
                "option_cards",
                "votes_by_round",
                "transcript",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(retain_days=30, owner_approval_for=[], forbid_irreversible=True),
        "metadata": {
            "title": "Nominal group technique (6 generators + facilitator)",
            "owner": "Prekzursil",
            "lineage": ["C-S22 nominal-group-6", "P06 nominal-group-technique"],
            "spec_citations": ["12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1457-1470"],
            "notes": notes(
                card="C-S22 nominal-group-6",
                seats_declared=6,
                roles_line="generalist_x6,facilitator",
                preset_label_rationale="custom - option_enumeration is not one of the 24 required "
                "archetypes. roadmap_prioritization is adjacent but is about prioritising a roadmap, "
                "not enumerating an option space.",
                dials={
                    "$.targets.unique_ideas + $.stopping.expression unique_ideas": "idea_cap dial. "
                    "These two MUST move together: SEM-007 fails the spec if the stopping threshold "
                    "exceeds targets.unique_ideas",
                    "$.protocol.sequence[0].quotas.ideas_per_participant": "ideas demanded per seat in silent generation",
                    "$.participants.anonymity.reveal_after_round": "when pseudonyms are unmasked",
                },
                outcome_lineage=CONSENSUS_ONLY,
                extra="SEAT DISCREPANCY (measured): the card says seats:6 but its roles line "
                "enumerates 7 (generalist_x6 + facilitator). This instance seats 7 - the facilitator "
                "is non-voting, which is the likely reason the card's count excluded it.",
            ),
        },
    }
