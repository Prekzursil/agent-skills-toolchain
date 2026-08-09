"""Author council protocol blueprints P37-P48 as executable CouncilSpec instances.

Lane build/proto-4 of Phase 2C. The twelve designs come from
harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.md lines 701-897
(P37 pairwise-comparison .. P48 kill-the-company). This module does NOT invent new
protocol designs; it turns each design card's `concrete mechanism`, `failure modes`
and `proof needed before adoption` into typed CouncilSpec fields.

Why a generator instead of twelve hand-written JSON files
--------------------------------------------------------
Semantic rule SEM-001 requires `stopping.source_expression` to parse to EXACTLY the
same tree as `stopping.expression`. Hand-maintaining both forms is a mechanical
comparison, and mechanical comparisons must be executed, not judged: every top-level
tree here is produced by the real `councilspec.expression.parse`, so the two forms
cannot drift. Per-stage `exit_when` trees are written structurally on purpose -
they carry `producer` / `note` fields that `parse` cannot emit, and stage
expressions are not subject to SEM-001.

Output: platform/council/protocols/pNN-<slug>.councilspec.json (12 files).
Validate with the INDEPENDENT reference CLI (not this script):
    cd platform/lib && python -m councilspec ../council/protocols/*.json
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLATFORM, "lib"))

from councilspec.expression import parse, unparse  # noqa: E402

OUT = os.path.join(HERE, "protocols")
DOC = "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
RECEIPT = "platform/schema/receipt.schema.json"

# Every unit in WORK-UNIT-CATALOG.json names command-center/schema/receipt.schema.json,
# which does not exist; the file that DOES exist is platform/schema/receipt.schema.json.
# outputs.receipt_schema is a documented reference string precisely so this unresolved
# path conflict cannot hard-fail all twelve specs. Reported, not silently inherited.
RECEIPT_NOTE = (
    "receipt_schema points at platform/schema/receipt.schema.json (the file that exists). "
    "The catalog's own output_schema for these units says command-center/schema/receipt.schema.json, "
    "which does NOT exist and has no deploy mapping. UNVERIFIED which path the runtime will load; "
    "settled by whichever unit lands the deploy mapping."
)


# --------------------------------------------------------------------------- helpers


def seat(pid: str, role: str, expertise: List[str], **kw: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"participant_id": pid, "role": role, "expertise": expertise}
    out.update(kw)
    return out


def num(metric: str, op: str, value: float, **kw: Any) -> Dict[str, Any]:
    return {"metric": metric, "op": op, "value": value, **kw}


def custom(
    metric: str,
    op: str,
    value: Any,
    value_type: str,
    producer: str,
    note: str | None = None,
) -> Dict[str, Any]:
    leaf: Dict[str, Any] = {
        "metric": metric,
        "op": op,
        "value": value,
        "value_type": value_type,
        "producer": producer,
    }
    if note:
        leaf["note"] = note
    return leaf


def audit_block(
    determinism: str = "deterministic_where_possible", store: str = "both"
) -> Dict[str, Any]:
    return {
        "transcript": True,
        "replay": True,
        "resume": True,
        "determinism": determinism,
        "privacy": {
            "redact_secrets": True,
            "redaction_policy": "deny_by_default",
            "pii_policy": "redact",
        },
        "safety": {"forbid_irreversible_actions": True},
        "persistence": {"store": store, "checkpoint_every_round": True},
    }


# --------------------------------------------------------------------------- P37


def p37() -> Dict[str, Any]:
    return {
        "council_id": "p37-pairwise-comparison",
        "preset": "custom",
        "objective": {
            "statement": "Rank N candidate options by pairwise comparison and report intransitivity instead of hiding it.",
            "charter": "Judge two options at a time; aggregate to a ranking; a cycle in the results is a finding about incoherent criteria, not noise to be smoothed away.",
            "risk_tier": "moderate",
            "desired_output": "ranked_options",
            "success_criteria": [
                "a ranking over all candidate options",
                "pair coverage reported as pairs_judged/pairs_total",
                "every intransitive cycle reported with the pair that closes it",
            ],
            "consensus_intent": "elicit_distribution",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse", "vendor_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 4},
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_expertise": 3,
                "max_share_per_vendor": 0.5,
            },
            "roster": [
                seat(
                    "judge-a",
                    "juror",
                    ["decision analysis"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    rights={"may_speak": True, "may_vote": True},
                ),
                seat(
                    "judge-b",
                    "juror",
                    ["systems engineering"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                    rights={"may_speak": True, "may_vote": True},
                ),
                seat(
                    "judge-c",
                    "juror",
                    ["cost modelling"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                    rights={"may_speak": True, "may_vote": True},
                ),
                seat(
                    "cycle-auditor",
                    "verifier",
                    ["preference aggregation", "graph theory"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    rights={"may_speak": True, "may_vote": False},
                    tools=["council_eval.pairwise_aggregator"],
                ),
            ],
            "anonymity": {"mode": "pseudonymous"},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["model", "vendor", "position_similarity"],
                "max_similarity": 0.85,
            },
        },
        "topology": {
            "kind": "pairwise_tournament",
            "tournament": {
                "pairing": "swiss",
                "comparisons_per_pair": 2,
                "aggregation": "bradley_terry",
            },
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "seed",
                    "independent": True,
                    "anonymous": True,
                },
                {
                    "kind": "custom",
                    "stage_id": "pairing",
                    "custom_name": "swiss-paired-duels",
                    "rounds": 4,
                    "quotas": {
                        "objections_per_participant": 1,
                        "counterexamples_per_round": 1,
                    },
                    "exit_when": {
                        "weighted": {
                            "threshold": 0.6,
                            "clauses": [
                                {
                                    "weight": 0.6,
                                    "when": custom(
                                        "custom:pairs_judged_ratio",
                                        ">=",
                                        0.8,
                                        "number",
                                        "council_eval.pairwise_aggregator",
                                        "Swiss subsampling means full round-robin is not run; coverage must be REPORTED, not assumed.",
                                    ),
                                },
                                {
                                    "weight": 0.4,
                                    "when": custom(
                                        "custom:intransitive_cycles_reported",
                                        "==",
                                        True,
                                        "boolean",
                                        "council_eval.cycle_detector",
                                        "A cycle is a finding: the criteria are incoherent. Reporting it satisfies this clause.",
                                    ),
                                },
                            ],
                        }
                    },
                },
                {"kind": "synthesis", "stage_id": "rank"},
            ],
            "speaking_order": "random",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 250},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "declare_confidence": True,
                "rebuttal_required": True,
                "cross_examination": True,
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
            "turns": 24,
            "speaking_quota_per_participant": 6,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "coverage_score": 0.8,
            "objections": 4,
            "counterexamples": 2,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "condorcet",
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
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "pairwise_agreement",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "coverage_score >= 0.8 AND all_participants_spoke == true AND (vote_margin >= 0.15 OR deadlock_detected == true)",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 6, "on_cap": "conditional_decision"},
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
                "pair coverage raised above 0.8",
                "the reported cycle resolved or accepted",
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
                "run_experiment",
                "recruit_independent_critic",
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
                "participant_dominance",
                "premature_convergence",
                "instant_unanimity",
                "evidence_free_majority",
                "lost_dissent",
                "idea_count_gaming",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "strongest_counterexample",
                "role_rotation",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
            },
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "option_cards",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("seeded"),
        "metadata": {
            "title": "P37 pairwise-comparison",
            "spec_citations": [
                f"{DOC}:701-716",
                "_USER-PROMPTS.md:10926",
                "_USER-PROMPTS.md:10930",
            ],
            "lineage": [
                "P37 pairwise-comparison",
                "AHP",
                "Elo",
                "estate: execution-grounded-bon behavioural clustering",
            ],
            "notes": "Anti-gaming per the card's failure mode: Swiss subsampling bounds the O(n^2) blowup, so coverage_score is a STOPPING CONDITION rather than an assumption. Intransitivity terminates via deadlock_detected -> irreducible_disagreement instead of being smoothed into a ranking. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P38


def p38() -> Dict[str, Any]:
    return {
        "council_id": "p38-analysis-of-competing-hypotheses",
        "preset": "root_cause_council",
        "objective": {
            "statement": "Diagnose a cause by disconfirmation: score an evidence x hypothesis matrix and keep the hypothesis with the fewest inconsistencies.",
            "charter": "Heuer ACH. Support is not the selector - inconsistency is. Non-diagnostic evidence is discarded, not tallied.",
            "risk_tier": "high",
            "desired_output": "root_cause",
            "success_criteria": [
                "an evidence x hypothesis consistency matrix",
                "at least one hypothesis nobody believes and one measuring-it-wrong hypothesis",
                "the surviving hypothesis named with its inconsistency count",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.75,
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
                "strategies": ["exact", "expertise_ranked", "adversarial"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                seat(
                    "matrix-clerk",
                    "custom:evidence_clerk",
                    ["evidence audit"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    tools=["council_eval.ach_matrix"],
                    rights={"may_speak": True, "may_vote": False},
                ),
                seat(
                    "hyp-owner-1",
                    "domain_expert",
                    ["harness internals"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "hyp-owner-2",
                    "domain_expert",
                    ["operating environment"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
                seat(
                    "null-hypothesis-owner",
                    "devils_advocate",
                    ["measurement error", "instrumentation"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                    context={
                        "briefing": "You own the 'we are measuring it wrong' hypothesis and the hypothesis nobody believes. You may not abandon them for social reasons."
                    },
                ),
                seat(
                    "statistician",
                    "statistician",
                    ["diagnosticity", "base rates"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "disjoint_evidence",
                "partitions": [
                    {
                        "partition_id": "artifact-side",
                        "visible_to": ["hyp-owner-1", "statistician"],
                        "sources": ["repo", "event ledger"],
                    },
                    {
                        "partition_id": "environment-side",
                        "visible_to": ["hyp-owner-2", "null-hypothesis-owner"],
                        "sources": ["host telemetry", "process table"],
                    },
                ],
            },
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "hallucinated_expertise", "inactivity"],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "topology": {
            "kind": "committee",
            "committees": [
                {
                    "committee_id": "hypothesis-bench",
                    "mandate": "Own and defend one hypothesis each.",
                    "members": ["hyp-owner-1", "hyp-owner-2", "null-hypothesis-owner"],
                },
                {
                    "committee_id": "diagnosticity-bench",
                    "mandate": "Score diagnosticity and discard non-diagnostic evidence.",
                    "members": ["matrix-clerk", "statistician"],
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "nominal_group",
                    "stage_id": "enumerate",
                    "rounds": 2,
                    "independent": True,
                    "quotas": {"ideas_per_participant": 3, "novel_ideas_per_round": 2},
                },
                {
                    "kind": "custom",
                    "stage_id": "matrix",
                    "custom_name": "evidence-by-hypothesis-consistency-matrix",
                    "rounds": 2,
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:diagnostic_evidence_items",
                                ">=",
                                8,
                                "number",
                                "council_eval.ach_matrix",
                                "Only evidence that DISCRIMINATES between hypotheses counts.",
                            ),
                            custom(
                                "custom:non_diagnostic_discarded",
                                "==",
                                True,
                                "boolean",
                                "council_eval.ach_matrix",
                            ),
                            custom(
                                "custom:unattractive_hypothesis_present",
                                "==",
                                True,
                                "boolean",
                                "council_eval.ach_matrix",
                                "Card failure mode: the hypothesis list omits the true one. A hypothesis nobody believes is mandatory.",
                            ),
                        ]
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "grill",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 2},
                },
                {"kind": "synthesis", "stage_id": "verdict"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": True,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 5,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "xhigh",
            "turns": 40,
            "sources": 20,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "unique_ideas": 8,
            "categories": 3,
            "evidence_items": 12,
            "objections": 8,
            "novelty_ratio": 0.5,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": -2, "max": 2},
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "extend_rounds",
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
        "source_expression": "unique_ideas >= 6 AND evidence_items >= 12 AND every_objection_addressed == true AND confidence >= 0.75",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "min_evidence_items": 8,
                "min_objections_addressed": 4,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 8, "on_cap": "conditional_decision"},
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
                "the surviving hypothesis confirmed by one executable probe"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": [
                "run_experiment",
                "split_question",
                "recruit_independent_critic",
                "strongest_counterexample",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
        },
        "anti_failure": {
            "controls": [
                "echo_chamber",
                "premature_convergence",
                "missing_expertise",
                "evidence_free_majority",
                "circular_citation",
                "instant_unanimity",
                "sycophancy",
                "weak_synthesis",
                "hallucinated_expertise",
                # experiments.required_before_decision is true here, so a matrix the
                # whole bench agrees on that a probe then refutes is a live failure.
                "consensus_failing_executable_tests",
            ],
            "fast_unanimity_response": [
                "forced_dissent",
                "strongest_counterexample",
                "recruit_independent_critic",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
                "quarantine_untrusted_sources": True,
            },
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "idea_ledger",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "experiments",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P38 analysis-of-competing-hypotheses",
            "spec_citations": [
                f"{DOC}:720-734",
                "_USER-PROMPTS.md:10927",
                "_USER-PROMPTS.md:11198",
            ],
            "lineage": [
                "P38 analysis-of-competing-hypotheses",
                "Heuer ACH (CIA tradecraft)",
            ],
            "notes": "Disconfirmation-first: score_scale is -2..+2 (INCONSISTENT..CONSISTENT) so a cell can vote AGAINST a hypothesis, which a 0..n support scale cannot. The card's failure mode (list omits the true hypothesis) is a stage exit condition, not advice. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P39


def p39() -> Dict[str, Any]:
    return {
        "council_id": "p39-key-assumptions-check",
        "preset": "custom",
        "objective": {
            "statement": "Expose and rate every load-bearing assumption, and force an action on each LOW-confidence one.",
            "charter": "AGENTS.md 1b mechanised. Produces no decision - it produces a rated assumption ledger plus an escalation per LOW+load-bearing pair. A blank required field defaults to worst case.",
            "risk_tier": "moderate",
            "desired_output": "risk_register",
            "success_criteria": [
                "every load-bearing assumption listed",
                "every assumption rated high/medium/low",
                "every LOW+load-bearing assumption converted to a verification or a clarify question",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "min_independent_sources": 0,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 3},
            "roster": [
                seat(
                    "assumption-scribe",
                    "scribe",
                    ["assumption ledgers"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    rights={"may_speak": True, "may_vote": True},
                ),
                seat(
                    "plan-owner",
                    "proposer",
                    ["the plan under review"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "skeptic",
                    "critic",
                    ["falsification", "adverse inference"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                    independence={
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                ),
            ],
            "anonymity": {"mode": "none"},
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "list",
                    "independent": True,
                    "quotas": {"ideas_per_participant": 5},
                },
                # The skeptic must state the STRONGEST version of an assumption before rating it
                # LOW, and the plan-owner rebuts each LOW rating. Without this, a skeptic can
                # strawman an assumption into a forced escalation and the ledger fills with noise.
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "steelman-each-assumption",
                    "rounds": 1,
                    "quotas": {"objections_per_participant": 2},
                },
                {
                    "kind": "custom",
                    "stage_id": "rate",
                    "custom_name": "confidence-rating-pass",
                    "rounds": 1,
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:unrated_assumptions",
                                "==",
                                0,
                                "number",
                                "assumption_ledger.rate",
                                "An assumption listed but not rated is the card's first failure mode.",
                            ),
                            custom(
                                "custom:open_low_confidence_load_bearing",
                                "==",
                                0,
                                "number",
                                "assumption_ledger.escalate",
                                "Card failure mode: rated without consequence. A LOW+load-bearing pair MUST trigger an action, so this must reach 0 by escalation, not by re-rating.",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "ledger"},
            ],
            "speaking_order": "lowest_confidence_first",
            "rounds": {"min": 1, "max": 3, "divergence_before_convergence": True},
            "turn": {"max_words": 200},
            "obligations": {
                "must_respond_to_prior": True,
                "declare_confidence": True,
                "forced_dissent": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
            },
            "critique_intensity": "standard",
            "experiments": {
                "allowed": True,
                "required_before_decision": False,
                "max_experiments": 2,
                "runner": "local",
            },
        },
        "budgets": {
            "effort": "low",
            "time_minutes": 20,
            "turns": 9,
            "speaking_quota_per_participant": 3,
            "max_inactivity_rounds": 1,
        },
        "targets": {
            "unique_ideas": 10,
            "categories": 2,
            "objections": 3,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "consent_no_objection",
            "abstention": {"allowed": False, "must_justify": True},
            "evidence_gate": {
                "votes_require_evidence": False,
                "evidence_outranks_majority": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 1.0,
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "all_participants_spoke == true AND objections_open == 0 AND divergence_complete == true",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 1,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 3,
                "max_minutes": 20,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "each escalated LOW+load-bearing assumption verified or answered"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": ["forced_dissent", "narrow_scope", "escalate_to_owner"],
            "escalation": {"after_attempts": 2, "to": "owner"},
        },
        "anti_failure": {
            "controls": [
                "silence",
                "sycophancy",
                "premature_convergence",
                "echo_chamber",
                "lost_dissent",
                "weak_synthesis",
                "instant_unanimity",
            ],
            "fast_unanimity_response": ["forced_dissent", "blind_re_evaluation"],
            "injection_defense": {"treat_artifacts_as_data": True},
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "idea_ledger",
                "unresolved_unknowns",
                "action_plan",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("seeded", "ledger"),
        "metadata": {
            "title": "P39 key-assumptions-check",
            "spec_citations": [f"{DOC}:736-750", "_USER-PROMPTS.md:10927"],
            "lineage": [
                "P39 key-assumptions-check",
                "IC structured analytic techniques",
                "AGENTS.md 1b assumption ledger",
            ],
            "notes": "speaking_order is lowest_confidence_first so the least certain seat is not anchored by the most certain one - the direct countermeasure to the echo-chamber/sycophancy pair on a 3-seat council. Consent (not majority) because a single unresolved assumption should block. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P40


def p40() -> Dict[str, Any]:
    return {
        "council_id": "p40-quality-of-information-check",
        "preset": "evidence_adjudication_jury",
        "objective": {
            "statement": "Audit the provenance of every evidence item before any verdict may cite it.",
            "charter": "Mechanises single-signal-verification inside a council. Each item must declare a source probe AND a mechanically different verifier probe; an item failing the pairing is demoted to UNVERIFIED and cannot support CONFIRMED.",
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "every evidence item carries a non-empty source probe",
                "every verifier probe is mechanically different from its source probe",
                "every detector was controlled against a known-present and a known-broken state",
                "items failing the pairing are demoted, not silently accepted",
            ],
            "consensus_intent": "adjudicate",
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
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 4},
            "roster": [
                seat(
                    "evidence-clerk",
                    "chair",
                    ["provenance audit", "probe independence"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="chair",
                    tools=["claim_gate"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
                seat(
                    "probe-verifier",
                    "verifier",
                    ["detector control", "both-states testing"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="veto_holder",
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_veto": True,
                        "may_call_experiment": True,
                    },
                ),
                seat(
                    "staleness-auditor",
                    "calibrator",
                    ["read-at refs", "staleness"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "claim-author",
                    "proposer",
                    ["the claims under audit"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="contributor",
                    rights={"may_speak": True, "may_vote": False},
                    conflicts=[
                        {
                            "kind": "authored_artifact",
                            "detail": "authored the claims being audited",
                            "recused": True,
                        }
                    ],
                ),
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
        },
        "topology": {"kind": "chair_led", "chair": "evidence-clerk"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "qoi-audit",
                    "custom_name": "quality-of-information-audit",
                    "rounds": 2,
                    "participants": [
                        "evidence-clerk",
                        "probe-verifier",
                        "staleness-auditor",
                    ],
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:items_missing_source_probe",
                                "==",
                                0,
                                "number",
                                "claim_gate.source_probe_check",
                                "MEASURED HOLE being closed: claim_gate.py _validate() (:132-156) does not require source_probe, and at :173-185 an absent source normalises to four empty strings that any non-empty verifier trivially differs from - so same-probe-rerun cannot fire and a CONFIRMED claim with NO source probe returns ok:true. A non-empty source probe is required here BEFORE fingerprints are compared.",
                            ),
                            custom(
                                "custom:items_with_same_probe_rerun",
                                "==",
                                0,
                                "number",
                                "claim_gate.independence_check",
                                "Re-running the source probe is not a second signal.",
                            ),
                            custom(
                                "custom:uncontrolled_detectors",
                                "==",
                                0,
                                "number",
                                "claim_gate.detector_control_check",
                                "Both-states rule: a probe silent in the known-BROKEN state measures nothing.",
                            ),
                        ]
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "challenge",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 2},
                },
                {"kind": "jury", "stage_id": "adjudicate"},
                {"kind": "synthesis", "stage_id": "verdict"},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 2, "max": 6},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 6,
                "runner": "local",
            },
        },
        "budgets": {
            "effort": "high",
            "turns": 28,
            "sources": 25,
            "experiments": 6,
            "speaking_quota_per_participant": 7,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "evidence_items": 6,
            "objections": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "veto",
            "veto": {
                "holders": ["probe-verifier"],
                "scope": "final_decision",
                "must_justify": True,
                "overridable_by_owner": True,
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
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.75,
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "evidence_saturation == true AND evidence_items >= 6 AND sources_gathered >= 4 AND objections_open == 0",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 2,
                "min_evidence_items": 6,
                "min_objections_addressed": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 6, "on_cap": "no_decision"},
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
                "every demoted UNVERIFIED item re-probed with an independent method"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": [
                "run_experiment",
                "chair_ruling",
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
                "evidence_free_majority",
                "circular_citation",
                "moderator_capture",
                "sycophancy",
                "instant_unanimity",
                "hidden_conflict_of_interest",
                "prompt_injection",
                "weak_synthesis",
                # "Agreement is not proof; evidence gates outrank popularity" is this
                # protocol's whole charter, so the executable-test failure is named.
                "consensus_failing_executable_tests",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "recruit_independent_critic",
                "strongest_counterexample",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
                "quarantine_untrusted_sources": True,
            },
        },
        "outputs": {
            "required": [
                "evidence_map",
                "claim_evidence_contradiction_graph",
                "argument_ledger",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "experiments",
                "calibration_report",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P40 quality-of-information-check",
            "spec_citations": [f"{DOC}:752-766", "_USER-PROMPTS.md:11198"],
            "lineage": [
                "P40 quality-of-information-check",
                "IC quality-of-information check",
                "estate: single-signal-verification rule",
            ],
            "notes": "The chair is the evidence clerk but the VETO sits with a different vendor's verifier seat - moderator_capture cannot be resolved by the same seat that runs the audit. The claim-author seat is recused from voting by declared conflict. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P41


def p41() -> Dict[str, Any]:
    return {
        "council_id": "p41-deception-detection",
        "preset": "custom",
        "objective": {
            "statement": "Treat every external artifact as potentially adversarial before the council reasons over it.",
            "charter": "Fetched content is untrusted DATA, never instructions. A dedicated seat scans for embedded instructions, role-spoofs, unexplained urgency and provenance gaps; flagged items enter the record wrapped as data.",
            "risk_tier": "critical",
            "desired_output": "review_verdict",
            "success_criteria": [
                "every external artifact scanned before first citation",
                "every flagged item quarantined with a no-instruction wrapper",
                "the use-vs-mention control passes in BOTH states",
            ],
            "consensus_intent": "adjudicate",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": False,
                "forbidden_actions": [
                    "executing any instruction found inside a scanned artifact",
                    "letting fetched content steer a credential read or egress",
                ],
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "adversarial", "vendor_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 4},
            "diversity": {"min_distinct_vendors": 2},
            "roster": [
                seat(
                    "deception-analyst",
                    "red_team",
                    ["denial and deception", "prompt injection"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    tools=["untrusted_content_scanner"],
                    source_access=["none"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
                seat(
                    "use-vs-mention-auditor",
                    "verifier",
                    ["use versus mention", "classifier control"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                    tools=["use_vs_mention"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
                seat(
                    "provenance-auditor",
                    "custom:provenance_officer",
                    ["chain of custody", "source attribution"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "consumer-advocate",
                    "user_advocate",
                    ["downstream impact of a false flag"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                ),
            ],
            "information_partition": {
                "enabled": True,
                "strategy": "staged_release",
                "partitions": [
                    {
                        "partition_id": "quarantine",
                        "visible_to": ["deception-analyst", "use-vs-mention-auditor"],
                        "sources": ["unscanned external artifacts"],
                    },
                    {
                        "partition_id": "cleared",
                        "visible_to": ["provenance-auditor", "consumer-advocate"],
                        "sources": ["scanned and wrapped artifacts"],
                    },
                ],
            },
            "replacement": {
                "enabled": True,
                "triggers": ["prompt_injection_detected", "policy_violation"],
                "preserve_prior_positions": True,
            },
        },
        "topology": {
            "kind": "caucus",
            "caucuses": [
                {
                    "caucus_id": "scanner-caucus",
                    "members": ["deception-analyst", "use-vs-mention-auditor"],
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "reader-caucus",
                    "members": ["provenance-auditor", "consumer-advocate"],
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "scan",
                    "custom_name": "adversarial-artifact-scan",
                    "rounds": 2,
                    "participants": ["deception-analyst", "use-vs-mention-auditor"],
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:unscanned_external_artifacts",
                                "==",
                                0,
                                "number",
                                "untrusted_content_scanner",
                            ),
                            custom(
                                "custom:unquarantined_flagged_items",
                                "==",
                                0,
                                "number",
                                "untrusted_content_scanner",
                            ),
                            custom(
                                "custom:use_vs_mention_control_passed",
                                "==",
                                True,
                                "boolean",
                                "use_vs_mention.both_states_probe",
                                "Card proof gate: a document that MENTIONS a destructive command must NOT be flagged, one that INSTRUCTS the council MUST be. Classify by the VERB/field, never by payload text - the estate has shipped this false positive repeatedly, including inside its own measuring tools.",
                            ),
                        ]
                    },
                },
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "steelman-the-artifact",
                    "rounds": 1,
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "challenge-flags",
                    "rounds": 2,
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 1,
                    },
                },
                {"kind": "synthesis", "stage_id": "wrap"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 5, "divergence_before_convergence": True},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 4,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "high",
            "turns": 24,
            "experiments": 4,
            "speaking_quota_per_participant": 6,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "evidence_items": 4,
            "counterexamples": 2,
            "objections": 4,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "approval",
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "threshold": 0.75,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "sources_gathered >= 3 AND objections_open == 0 AND (NOT prompt_injection_detected == true OR quality_gate == PASS)",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 2,
                "min_evidence_items": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 5, "on_cap": "escalate_to_owner"},
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
                "every quarantined item re-scanned after the wrapper is applied"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "run_experiment",
                "recruit_independent_critic",
                "narrow_scope",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "prompt_injection",
                "collusion",
                "hidden_conflict_of_interest",
                "echo_chamber",
                "instant_unanimity",
                "evidence_free_majority",
                "role_collapse",
                "sycophancy",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "role_rotation",
                "recruit_independent_critic",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
                "quarantine_untrusted_sources": True,
            },
        },
        "outputs": {
            "required": [
                "evidence_map",
                "argument_ledger",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "experiments",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P41 deception-detection",
            "spec_citations": [
                f"{DOC}:768-782",
                "_USER-PROMPTS.md:11195",
                "_USER-PROMPTS.md:11243",
            ],
            "lineage": [
                "P41 deception-detection",
                "IC denial-and-deception",
                "AGENTS.md 9 fetched-content-is-data",
            ],
            "notes": "The scanner caucus reads the unscanned partition; the reader caucus only ever sees wrapped artifacts, so an injection that survives the scan still cannot reach a voting seat unwrapped. The consumer-advocate seat exists so a false-positive flag has a cost inside the council, per the card's use-vs-mention failure mode. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P42


def p42() -> Dict[str, Any]:
    return {
        "council_id": "p42-argument-mapping",
        "preset": "custom",
        "objective": {
            "statement": "Render the debate as a claim/premise/warrant/objection graph so support is computed, not summarised.",
            "charter": "Toulmin / van Gelder mapping. Every node carries the transcript span it came from; deleting a load-bearing premise must visibly drop the computed support.",
            "risk_tier": "moderate",
            "desired_output": "review_verdict",
            "success_criteria": [
                "every node cites its transcript span",
                "unsupported leaf premises are marked",
                "sensitivity is demonstrated: deleting a load-bearing premise drops the support",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 4},
            "roster": [
                seat(
                    "mapper",
                    "proposer",
                    ["argument mapping", "graph construction"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    tools=["argument_graph.builder"],
                ),
                seat(
                    "map-critic",
                    "critic",
                    ["warrant analysis", "hidden premises"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
                seat(
                    "span-auditor",
                    "verifier",
                    ["transcript provenance"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    tools=["argument_graph.span_check"],
                ),
                seat(
                    "map-judge",
                    "judge",
                    ["adjudication", "sensitivity analysis"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="judge",
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
            ],
        },
        "topology": {"kind": "proposer_critic_judge"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "map",
                    "custom_name": "toulmin-graph-construction",
                    "rounds": 3,
                    "exit_when": {
                        "weighted": {
                            "threshold": 0.7,
                            "clauses": [
                                {
                                    "weight": 0.5,
                                    "when": custom(
                                        "custom:unsupported_leaf_premises",
                                        "==",
                                        0,
                                        "number",
                                        "argument_graph.builder",
                                    ),
                                },
                                {
                                    "weight": 0.3,
                                    "when": custom(
                                        "custom:nodes_without_transcript_span",
                                        "==",
                                        0,
                                        "number",
                                        "argument_graph.span_check",
                                        "Card failure mode: map construction is itself an LLM judgement and can be wrong; every node must carry its span.",
                                    ),
                                },
                                {
                                    "weight": 0.4,
                                    "when": custom(
                                        "custom:premise_deletion_sensitivity_proven",
                                        "==",
                                        True,
                                        "boolean",
                                        "argument_graph.sensitivity_probe",
                                        "Card proof gate: delete a known load-bearing premise; the computed support MUST drop. A map whose support is insensitive to its premises is decoration.",
                                    ),
                                },
                            ],
                        }
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "attack-the-map",
                    "rounds": 2,
                    "quotas": {
                        "objections_per_participant": 3,
                        "counterexamples_per_round": 1,
                    },
                },
                {"kind": "synthesis", "stage_id": "verdict"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 2, "max": 8},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 4,
                "runner": "local",
            },
        },
        "budgets": {
            "effort": "high",
            "turns": 32,
            "speaking_quota_per_participant": 8,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 3,
        },
        # NOTE: `targets` has no completeness_score field (the schema's target vocabulary is
        # unique_ideas/raw_ideas/categories/novelty_ratio/diversity_index/coverage_score/
        # objections/counterexamples/evidence_items/dedup). An earlier draft declared
        # targets.completeness_score and the reference validator rejected it, so the stopping
        # metric was moved to coverage_score to keep target and stopping rule on ONE metric.
        "targets": {
            "evidence_items": 8,
            "objections": 9,
            "counterexamples": 2,
            "coverage_score": 0.85,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "weighted",
            "weights": {
                "map-critic": 1.0,
                "span-auditor": 1.0,
                "map-judge": 2.0,
                "mapper": 0.0,
            },
            "belief_aggregation": {
                "method": "calibration_weighted",
                "require_confidence_per_vote": True,
                "calibration_source": "council_eval.calibration_history",
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "threshold": 0.7,
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
        "source_expression": "(coverage_score >= 0.85 AND objections_open == 0) OR max_rounds == 8",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_objections_addressed": 4,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 8, "on_cap": "conditional_decision"},
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
                "the remaining unsupported leaf premises either supported or removed"
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.88,
                "circular_citation_check": True,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "judge_ruling",
                "split_question",
                "strongest_counterexample",
                "narrow_scope",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "judge"},
        },
        "anti_failure": {
            "controls": [
                "circular_debate",
                "endless_debate",
                "circular_citation",
                "weak_synthesis",
                "instant_unanimity",
                "evidence_free_majority",
                "premature_convergence",
                "lost_dissent",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "blind_re_evaluation",
                "forced_dissent",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
            },
        },
        "outputs": {
            "required": [
                "argument_graph",
                "argument_ledger",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block(),
        "metadata": {
            "title": "P42 argument-mapping",
            "spec_citations": [f"{DOC}:784-798", "_USER-PROMPTS.md:10931"],
            "lineage": [
                "P42 argument-mapping",
                "Toulmin",
                "van Gelder argument mapping",
            ],
            "notes": "The card is only roughly-even confidence and its recommended default is NO (use after a decision has been re-litigated twice), so the endless-debate control is a HARD stop: the OR branch fires at max_rounds == 8, which equals both protocol.rounds.max and hard_caps.max_rounds. The mapper's vote weight is 0.0 - whoever builds the map does not get to grade it. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P43


def p43() -> Dict[str, Any]:
    return {
        "council_id": "p43-premortem",
        "preset": "risk_committee",
        "objective": {
            "statement": "Assert the decision has already failed catastrophically, then convert the specific causes into tripwires with named detectors.",
            "charter": "Klein premortem. The output is a TRIPWIRE SET, not a risk register: every tripwire names the probe that would fire it and the owner who answers it.",
            "risk_tier": "high",
            "desired_output": "risk_register",
            "success_criteria": [
                "each seat writes a specific failure narrative, not a generic risk",
                "causes clustered into categories",
                "every top cause converted to a tripwire with a named detector and owner",
            ],
            "consensus_intent": "surface_disagreement",
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "min_independent_sources": 0,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "stakeholder_balanced", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                seat(
                    "narrator-a",
                    "risk_officer",
                    ["operational failure"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    anonymous=True,
                ),
                seat(
                    "narrator-b",
                    "security_reviewer",
                    ["security failure"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                    anonymous=True,
                ),
                seat(
                    "narrator-c",
                    "architect",
                    ["architectural decay"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                    anonymous=True,
                ),
                seat(
                    "narrator-d",
                    "user_advocate",
                    ["adoption failure"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    anonymous=True,
                ),
                seat(
                    "tripwire-clerk",
                    "scribe",
                    ["detector design", "tripwire registry"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    tools=["tripwire_registry"],
                    rights={
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                ),
            ],
            "anonymity": {"mode": "blind_to_peers", "reveal_after_round": 1},
            "recruitment": {
                "dynamic": True,
                "triggers": ["low_novelty", "fast_unanimity"],
                "max_recruits": 2,
            },
        },
        "topology": {"kind": "delphi"},
        "protocol": {
            "sequence": [
                {
                    "kind": "brainstorm",
                    "stage_id": "failure-narratives",
                    "rounds": 2,
                    "independent": True,
                    "anonymous": True,
                    "quotas": {"ideas_per_participant": 4, "novel_ideas_per_round": 2},
                },
                {
                    "kind": "delphi_round",
                    "stage_id": "cluster",
                    "rounds": 2,
                    "anonymous": True,
                },
                # A narrative that survives no challenge produces a decorative tripwire. Seats
                # steelman each other's narratives, then cross-examine whether the proposed
                # detector would actually fire - the card's own failure mode, made a stage.
                {
                    "kind": "steelman_before_rebuttal",
                    "stage_id": "steelman-narratives",
                    "rounds": 1,
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "challenge-detectors",
                    "rounds": 2,
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 1,
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "tripwires",
                    "custom_name": "cause-to-tripwire-conversion",
                    "rounds": 1,
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:tripwires_without_detector",
                                "==",
                                0,
                                "number",
                                "tripwire_registry",
                                "Card failure mode: a tripwire with no detector is decoration.",
                            ),
                            custom(
                                "custom:tripwires_without_owner",
                                "==",
                                0,
                                "number",
                                "tripwire_registry",
                            ),
                            custom(
                                "custom:detectors_proven_both_states",
                                "==",
                                True,
                                "boolean",
                                "tripwire_registry.both_states_probe",
                                "Card proof gate: each detector must be shown to FIRE in a synthetic failure state. A detector silent in both states measures nothing.",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "tripwire-set"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 5, "divergence_before_convergence": True},
            "turn": {"max_words": 400},
            # must_respond_to_prior stays FALSE on purpose: narratives are written independently
            # so they do not converge socially. The response obligations attach to the later
            # challenge stages, not to generation.
            "obligations": {
                "must_respond_to_prior": False,
                "declare_confidence": True,
                "forced_dissent": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 6,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 60,
            "turns": 25,
            "speaking_quota_per_participant": 6,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
        },
        "targets": {
            "unique_ideas": 18,
            "raw_ideas": 24,
            "categories": 4,
            "novelty_ratio": 0.6,
            "diversity_index": 0.6,
            "objections": 5,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.78,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "ranked_choice",
            "belief_aggregation": {
                "method": "trimmed_mean",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": False,
                "evidence_outranks_majority": True,
            },
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": False,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "unique_ideas >= 15 AND categories_covered >= 4 AND every_objection_addressed == true AND all_participants_spoke == true",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 4,
                "every_participant_spoke": True,
                "min_objections_addressed": 3,
            },
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 60,
                "on_cap": "conditional_decision",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "conditional_decision",
                "minority_report",
                "dissent",
                "irreducible_disagreement",
            ],
            "conditional_decision_requires": [
                "every tripwire detector demonstrated firing in a synthetic failure state"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.85},
            "resolution": [
                "recruit_independent_critic",
                "rotate_roles",
                "forced_dissent",
                "narrow_scope",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
        },
        "anti_failure": {
            "controls": [
                "idea_count_gaming",
                "duplicate_novelty",
                "premature_convergence",
                "echo_chamber",
                "instant_unanimity",
                "silence",
                "lost_dissent",
                "weak_synthesis",
                "participant_dominance",
                # dissent is UNATTRIBUTED here, which protects the dissenter but makes
                # quiet removal of a narrative cheap - so suppression is named too.
                "minority_suppression",
            ],
            "fast_unanimity_response": [
                "forced_dissent",
                "recruit_independent_critic",
                "role_rotation",
                "strongest_counterexample",
            ],
            "injection_defense": {"treat_artifacts_as_data": True},
        },
        "outputs": {
            "required": [
                "idea_ledger",
                "idea_catalog",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "experiments",
                "action_plan",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("seeded"),
        "metadata": {
            "title": "P43 premortem",
            "spec_citations": [
                f"{DOC}:800-814",
                "_USER-PROMPTS.md:10929",
                "_USER-PROMPTS.md:11236-11237",
            ],
            "lineage": [
                "P43 premortem",
                "Klein premortem",
                "estate: metaswarm plan-review-gate adversarial lens",
            ],
            "notes": "Idea-count gaming is the live risk for any narrative-generating protocol, so dedup.trivial_variant_policy is REJECT (not merge) and novelty_ratio 0.6 is a target, while the stopping rule gates on unique_ideas (deduplicated) and categories_covered - four near-identical narratives cannot satisfy it. Anonymity is blind_to_peers during generation so narratives do not converge socially. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P44


def p44() -> Dict[str, Any]:
    return {
        "council_id": "p44-postmortem-5whys-causal",
        "preset": "postmortem_council",
        "objective": {
            "statement": "Reconstruct an incident from artifacts only, drive why-chains to a systemic cause, and remediate the whole blast radius.",
            "charter": "Blameless. Every link in the causal chain cites a timestamped artifact; a link with no artifact is marked UNVERIFIED inline. The milestone supersedes the prior failure entry so the dead end is retired, not re-walked.",
            "risk_tier": "high",
            "desired_output": "root_cause",
            "success_criteria": [
                "timeline reconstructed from artifacts only",
                "every causal link cites a timestamped artifact",
                "blast radius enumerated: files, commits, index entries, downstream consumers",
                "remediation covers the whole set, not the first symptom",
                "the prior failure ledger entry superseded by this milestone",
            ],
            "consensus_intent": "adjudicate",
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
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5},
            "roster": [
                seat(
                    "timeline-clerk",
                    "scribe",
                    ["artifact forensics", "event ledger"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    tools=["event_ledger"],
                    source_access=["repo", "transcripts"],
                    rights={"may_speak": True, "may_vote": False},
                ),
                seat(
                    "juror-1",
                    "juror",
                    ["systems failure"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "juror-2",
                    "juror",
                    ["tooling and CI"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
                seat(
                    "juror-3",
                    "juror",
                    ["human factors"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                ),
                seat(
                    "blast-radius-auditor",
                    "verifier",
                    ["blast radius", "downstream consumers"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    tools=["blast_radius_enumerator"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
            ],
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "topology": {"kind": "jury"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "timeline",
                    "custom_name": "artifact-only-timeline-reconstruction",
                    "rounds": 1,
                    "participants": ["timeline-clerk", "blast-radius-auditor"],
                },
                {
                    "kind": "socratic",
                    "stage_id": "why-chain",
                    "rounds": 5,
                    "quotas": {"objections_per_participant": 2},
                },
                {
                    "kind": "custom",
                    "stage_id": "blast-radius",
                    "custom_name": "blast-radius-enumeration-and-remediation",
                    "rounds": 1,
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:causal_links_without_artifact",
                                "==",
                                0,
                                "number",
                                "event_ledger.link_auditor",
                                "Card failure mode: a 5-why chain can be a just-so story. One artifact per link, or the link is UNVERIFIED inline.",
                            ),
                            custom(
                                "custom:blast_radius_items_unremediated",
                                "==",
                                0,
                                "number",
                                "blast_radius_enumerator",
                                "Remediate the WHOLE set, not the first symptom.",
                            ),
                            custom(
                                "custom:prior_failure_entry_superseded",
                                "==",
                                True,
                                "boolean",
                                "event_ledger.note",
                                "A milestone that contradicts a failure entry must supersede it so the dead end is retired.",
                            ),
                        ]
                    },
                },
                {"kind": "jury", "stage_id": "adjudicate", "rounds": 2},
                {"kind": "synthesis", "stage_id": "root-cause"},
            ],
            "speaking_order": "reverse_seniority",
            "rounds": {"min": 3, "max": 7},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "standard",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 5,
                "runner": "local",
            },
        },
        "budgets": {
            "effort": "high",
            "turns": 35,
            "sources": 25,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "evidence_items": 10,
            "objections": 6,
            "coverage_score": 0.85,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "juror",
            "quorum": {
                "min_voters": 3,
                "min_fraction": 0.6,
                "on_failure": "extend_rounds",
            },
            "belief_aggregation": {
                "method": "median",
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
                "strategic_abstention_check": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.75,
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
        "source_expression": "evidence_items >= 10 AND every_objection_addressed == true AND (verdict == CONFIRMED OR verdict == PARTIAL)",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 3,
                "min_evidence_items": 10,
                "min_objections_addressed": 4,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 7, "on_cap": "conditional_decision"},
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
                "each UNVERIFIED causal link either evidenced or removed",
                "every blast-radius item remediated or explicitly accepted",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "circular_citation_check": True},
            "resolution": [
                "run_experiment",
                "split_question",
                "recruit_independent_critic",
                "judge_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "evidence_free_majority",
                "premature_convergence",
                "sycophancy",
                "participant_dominance",
                "instant_unanimity",
                "circular_citation",
                "lost_dissent",
                "weak_synthesis",
                "silence",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "blind_re_evaluation",
                "forced_dissent",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
            },
        },
        "outputs": {
            "required": [
                "transcript",
                "evidence_map",
                "claim_evidence_contradiction_graph",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "experiments",
                "action_plan",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("deterministic_where_possible", "both"),
        "metadata": {
            "title": "P44 postmortem-5whys-causal",
            "spec_citations": [f"{DOC}:816-830", "_USER-PROMPTS.md:10927"],
            "lineage": [
                "P44 postmortem-5whys-causal",
                "blameless postmortem",
                "5 whys",
                "AGENTS.md 3 event ledger",
                "AGENTS.md 9b blast radius",
            ],
            "notes": "speaking_order is reverse_seniority: the blame-framing failure mode is countered structurally by letting the least senior seat speak first, before an authority position exists to agree with. The verdict branch accepts PARTIAL so an honestly-scoped root cause is a terminal state and an overclaimed one is not. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P45


def p45() -> Dict[str, Any]:
    reviewer_panel = {
        "schema_version": "1.0.0",
        "council_id": "p45-sub-blind-reviewer-panel",
        "objective": {
            "statement": "Three mutually blind reviewers each return a verdict plus itemised comments against the stated standard.",
            "risk_tier": "moderate",
            "desired_output": "review_verdict",
            "success_criteria": [
                "three independent review sets",
                "reviewer comment-set overlap below the ceiling",
            ],
            "consensus_intent": "elicit_distribution",
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse", "vendor_diverse"],
            },
            "count": {"mode": "exact", "exact_n": 3},
            "diversity": {
                "min_distinct_vendors": 3,
                "min_distinct_expertise": 3,
                "max_share_per_vendor": 0.34,
            },
            "roster": [
                seat(
                    "reviewer-1",
                    "domain_expert",
                    ["correctness lens"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    anonymous=True,
                    context={
                        "briefing": "Lens: correctness and evidence. Do not review style."
                    },
                    independence={
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                ),
                seat(
                    "reviewer-2",
                    "security_reviewer",
                    ["threat model lens"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                    anonymous=True,
                    context={
                        "briefing": "Lens: security and blast radius. Do not review style."
                    },
                    independence={
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                ),
                seat(
                    "reviewer-3",
                    "architect",
                    ["maintainability lens"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                    anonymous=True,
                    context={
                        "briefing": "Lens: interfaces and operability. Do not review style."
                    },
                    independence={
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                ),
            ],
            "anonymity": {"mode": "double_blind"},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["prompt", "expertise", "position_similarity"],
                "max_similarity": 0.4,
            },
        },
        "topology": {"kind": "delphi"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "read",
                    "independent": True,
                    "anonymous": True,
                    "quotas": {"objections_per_participant": 3},
                },
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 1, "max": 2},
            "obligations": {
                "must_cite_evidence": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 3},
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "agreement_index",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": False,
                "suppression_check": True,
            },
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "source_expression": "independent_positions >= 3 AND diversity_index >= 0.5",
            "expression": None,
            "minimum_deliberation": {
                "min_rounds": 1,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 2, "on_cap": "synthesize_best_effort"},
        },
        "outcomes": {
            "allowed": ["decision", "no_decision", "minority_report", "dissent"]
        },
        "anti_failure": {
            "controls": [
                "echo_chamber",
                "instant_unanimity",
                "sycophancy",
                "silence",
                "collusion",
                "role_collapse",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "recruit_independent_critic",
            ],
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "argument_ledger",
                "dissent_minority_report",
            ]
        },
        "metadata": {
            "title": "P45 blind reviewer panel (subcouncil)",
            "notes": "Mutual blindness plus a per-reviewer lens is the countermeasure to the card's failure mode (reviewers converge because they share a brief). Vendor diversity is 3-of-3 so a shared model prior cannot be the reason three reviews agree.",
        },
    }

    return {
        "council_id": "p45-scientific-peer-review",
        "preset": "scientific_peer_review",
        "objective": {
            "statement": "Give an artifact an independent competent read against a stated standard, with a right of reply.",
            "charter": "Journal peer review. k mutually blind reviewers; an editor reconciles; the author responds point-by-point. Near-identical review sets mean one reviewer wearing k hats, so comment-set overlap is a gate.",
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "k independent reviews, each ACCEPT/MINOR/MAJOR/REJECT with itemised comments",
                "reviewer comment-set Jaccard below the ceiling",
                "the author answered every point",
                "an editorial reconciliation naming which comments are binding",
            ],
            "consensus_intent": "adjudicate",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 3},
            "roster": [
                seat(
                    "editor",
                    "judge",
                    ["editorial reconciliation"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="judge",
                    tools=["council_eval.jaccard"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_recruit": True,
                        "may_call_experiment": True,
                    },
                ),
                seat(
                    "author",
                    "proposer",
                    ["the artifact under review"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    rights={"may_speak": True, "may_vote": False},
                    conflicts=[
                        {
                            "kind": "authored_artifact",
                            "detail": "authored the artifact under review",
                            "recused": True,
                        }
                    ],
                ),
                seat(
                    "overlap-auditor",
                    "verifier",
                    ["review independence", "set overlap"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                    tools=["council_eval.jaccard"],
                ),
            ],
            "recruitment": {
                "dynamic": True,
                "triggers": ["missing_expertise", "low_novelty"],
                "max_recruits": 2,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
        },
        "topology": {
            "kind": "nested_subcouncil",
            "subcouncils": [reviewer_panel],
            "fan_in": {
                "reducer": "synthesize",
                "require_all_subcouncils_complete": True,
            },
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "dispatch",
                    "custom_name": "dispatch-blind-reviews",
                    "rounds": 1,
                    "participants": ["editor"],
                },
                {
                    "kind": "custom",
                    "stage_id": "reconcile",
                    "custom_name": "editorial-reconciliation-and-right-of-reply",
                    "rounds": 2,
                    # Itemised comments are the unit of peer review: a reviewer who files fewer than
                    # three loses the lens they were recruited for, and the Jaccard ceiling below
                    # cannot discriminate between review sets that are nearly empty.
                    "quotas": {
                        "objections_per_participant": 3,
                        "counterexamples_per_round": 1,
                    },
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:reviewer_comment_jaccard",
                                "<=",
                                0.4,
                                "number",
                                "council_eval.jaccard",
                                "Card proof gate: reviewer comment-set Jaccard must be below a ceiling; near-identical review sets mean one reviewer wearing k hats.",
                            ),
                            custom(
                                "custom:author_unanswered_points",
                                "==",
                                0,
                                "number",
                                "editor_checklist",
                                "Right of reply is not optional: the author must respond point-by-point.",
                            ),
                            custom(
                                "custom:subcouncil_reviews_received",
                                ">=",
                                3,
                                "number",
                                "fan_in.synthesize",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "editorial-verdict"},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": False,
                "max_experiments": 3,
                "runner": "ci",
            },
        },
        "budgets": {
            "effort": "high",
            "turns": 20,
            "speaking_quota_per_participant": 6,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "evidence_items": 6,
            "objections": 9,
            "diversity_index": 0.5,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.4,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "judge",
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "judge",
        },
        "consensus": {
            "threshold": 0.6,
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
        "source_expression": "independent_positions >= 3 AND diversity_index >= 0.5 AND every_objection_addressed == true AND (verdict == ACCEPT OR verdict == REJECT)",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 3,
                "min_objections_addressed": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {"max_rounds": 4, "on_cap": "conditional_decision"},
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
                "every MAJOR comment closed or explicitly waived by the editor"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.9},
            "resolution": [
                "recruit_independent_critic",
                "judge_ruling",
                "rotate_roles",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "judge"},
        },
        "anti_failure": {
            "controls": [
                "echo_chamber",
                "instant_unanimity",
                "sycophancy",
                "collusion",
                "role_collapse",
                "missing_expertise",
                "lost_dissent",
                "weak_synthesis",
                "hidden_conflict_of_interest",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "recruit_independent_critic",
                "forced_dissent",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
            },
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
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
            "title": "P45 scientific-peer-review",
            "spec_citations": [
                f"{DOC}:835-849",
                "_USER-PROMPTS.md:10926",
                "_USER-PROMPTS.md:11193",
            ],
            "lineage": [
                "P45 scientific-peer-review",
                "journal peer review",
                "estate: metaswarm design-review-gate",
            ],
            "notes": "Nested by construction: the blind reviewer panel is a SUBCOUNCIL so its double-blind anonymity cannot leak into the editorial layer, and the editor never participates in the reads it reconciles. The author holds a contributor seat with may_vote false and a declared authored_artifact conflict. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P46


def _arb_sub(
    cid: str,
    title: str,
    statement: str,
    members: List[Dict[str, Any]],
    method: str,
    src: str,
    extra_voting: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    voting: Dict[str, Any] = {
        "method": method,
        "evidence_gate": {
            "votes_require_evidence": True,
            "evidence_outranks_majority": True,
            "reject_evidence_free_majority": True,
        },
        "tie_break": "extend_rounds",
    }
    if extra_voting:
        voting.update(extra_voting)
    return {
        "schema_version": "1.0.0",
        "council_id": cid,
        "objective": {
            "statement": statement,
            "risk_tier": "moderate",
            "desired_output": "recommendation",
            "success_criteria": ["a domain verdict with itemised conditions"],
            "consensus_intent": "seek_consensus",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
        },
        "participants": {
            "selection": {"mode": "exact", "strategies": ["exact", "expertise_ranked"]},
            "count": {"mode": "exact", "exact_n": len(members)},
            "roster": members,
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "read",
                    "independent": True,
                },
                {
                    "kind": "round_robin",
                    "stage_id": "discuss",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 2},
                },
                {"kind": "synthesis", "stage_id": "domain-verdict"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 1, "max": 3},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "adversarial",
        },
        "voting": voting,
        "consensus": {
            "threshold": 0.6,
            "measure": "vote_share",
            "minority_report": "optional",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            "source_expression": src,
            "expression": None,
            "minimum_deliberation": {"min_rounds": 1, "every_participant_spoke": True},
            "hard_caps": {"max_rounds": 3, "on_cap": "escalate_to_owner"},
        },
        "outcomes": {
            "allowed": ["decision", "conditional_decision", "no_decision", "dissent"]
        },
        "anti_failure": {
            "controls": [
                "sycophancy",
                "instant_unanimity",
                "evidence_free_majority",
                "silence",
                "missing_expertise",
            ],
            "fast_unanimity_response": ["forced_dissent", "strongest_counterexample"],
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "argument_ledger",
                "final_recommendation",
            ]
        },
        "metadata": {
            "title": title,
            "notes": "Domain subcouncil of the ARB; its verdict feeds the chairs' vote.",
        },
    }


def p46() -> Dict[str, Any]:
    subs = [
        _arb_sub(
            "p46-sub-security-review",
            "ARB security subcouncil",
            "Assess the submission against the estate threat model and issue conditions.",
            [
                seat(
                    "sec-a",
                    "security_reviewer",
                    ["threat modelling"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "sec-b",
                    "red_team",
                    ["attack paths"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
            ],
            "consent_no_objection",
            "objections_open == 0 AND evidence_items >= 3",
        ),
        _arb_sub(
            "p46-sub-cost-and-operability",
            "ARB cost and SRE subcouncil",
            "Assess run cost, operability and rollback for the submission.",
            [
                seat(
                    "cost-analyst",
                    "custom:cost_officer",
                    ["run cost", "quota"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "sre",
                    "risk_officer",
                    ["operability", "rollback"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                ),
            ],
            "majority",
            "objections_open == 0 AND confidence >= 0.7",
        ),
        _arb_sub(
            "p46-sub-product-fit",
            "ARB product subcouncil",
            "Assess whether the submission serves the stated user outcome.",
            [
                seat(
                    "pm",
                    "product_manager",
                    ["outcome fit"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "advocate",
                    "user_advocate",
                    ["owner workflow"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
            ],
            "consent_no_objection",
            "objections_open == 0 AND all_participants_spoke == true",
        ),
    ]

    return {
        "council_id": "p46-architecture-review-board",
        "preset": "architecture_review_board",
        "objective": {
            "statement": "A standing board reviews cross-cutting submissions and tracks its conditions to closure.",
            "charter": "Fixed seats, a submission template, and APPROVE / APPROVE-WITH-CONDITIONS / RETURN. Standing membership is the point: conditions carry ACROSS submissions, and an open condition from a prior review blocks the next one.",
            "risk_tier": "high",
            "desired_output": "go_no_go",
            "success_criteria": [
                "a verdict of APPROVE, APPROVE-WITH-CONDITIONS or RETURN",
                "every condition recorded with an owner and a closure test",
                "no submission admitted while a prior condition is open",
            ],
            "consensus_intent": "seek_consensus",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": True,
                "forbidden_actions": ["closing a condition without its closure test"],
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "stakeholder_balanced", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 5},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 5},
            "roster": [
                seat(
                    "board-chair",
                    "chair",
                    ["architecture governance"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="chair",
                    rights={"may_speak": True, "may_vote": True, "may_recruit": True},
                ),
                seat(
                    "security-chair",
                    "security_reviewer",
                    ["threat modelling"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="veto_holder",
                    rights={"may_speak": True, "may_vote": True, "may_veto": True},
                ),
                seat(
                    "cost-chair",
                    "custom:cost_officer",
                    ["run cost"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "sre-chair",
                    "risk_officer",
                    ["operability"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                ),
                seat(
                    "conditions-registrar",
                    "scribe",
                    ["conditions register"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="contributor",
                    tools=["conditions_register"],
                    rights={"may_speak": True, "may_vote": False},
                ),
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "conflict_of_interest", "dominance"],
                "preserve_prior_positions": True,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "recuse_from_vote",
            },
        },
        "topology": {
            "kind": "council_of_councils",
            "chair": "board-chair",
            "committees": [
                {
                    "committee_id": "standing-board",
                    "mandate": "Standing seats that carry memory across submissions.",
                    "members": [
                        "board-chair",
                        "security-chair",
                        "cost-chair",
                        "sre-chair",
                    ],
                },
            ],
            "fan_in": {
                "reducer": "vote_of_chairs",
                "require_all_subcouncils_complete": True,
            },
            "subcouncils": subs,
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "admission",
                    "custom_name": "prior-conditions-admission-gate",
                    "rounds": 1,
                    "participants": ["conditions-registrar", "board-chair"],
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:open_conditions_from_prior_review",
                                "==",
                                0,
                                "number",
                                "conditions_register",
                                "Card proof gate: open-condition count must GATE the next submission - tested with a deliberately unclosed condition.",
                            ),
                            custom(
                                "custom:conditions_without_owner",
                                "==",
                                0,
                                "number",
                                "conditions_register",
                                "Card failure mode: conditions are issued and never closed.",
                            ),
                            custom(
                                "custom:conditions_without_closure_test",
                                "==",
                                0,
                                "number",
                                "conditions_register",
                            ),
                        ]
                    },
                },
                {"kind": "fishbowl", "stage_id": "subcouncil-readout"},
                {
                    "kind": "cross_examination",
                    "stage_id": "board-questions",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 2},
                },
                {"kind": "synthesis", "stage_id": "board-verdict"},
            ],
            "speaking_order": "seniority",
            "rounds": {"min": 2, "max": 5},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": False,
                "max_experiments": 3,
                "runner": "ci",
            },
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 90,
            "turns": 30,
            "speaking_quota_per_participant": 7,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "evidence_items": 6,
            "objections": 8,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "supermajority",
            "supermajority_threshold": 0.6,
            "quorum": {
                "min_voters": 3,
                "min_fraction": 0.75,
                "on_failure": "extend_rounds",
            },
            "delegation": {
                "allowed": True,
                "max_chain_length": 2,
                "cycles_forbidden": True,
                "map": {"cost-chair": "sre-chair"},
            },
            "veto": {
                "holders": ["security-chair"],
                "scope": "safety_only",
                "must_justify": True,
                "overridable_by_owner": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": True,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.6,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "quorum_met == true AND consensus >= 0.6 AND objections_open == 0 AND subcouncils_complete >= 3",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 3,
                "min_objections_addressed": 3,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 90,
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
                "every issued condition has an owner and a closure test",
                "the conditions register shows zero open conditions before the next submission",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "vote_oscillation_rounds": 2},
            "resolution": [
                "chair_ruling",
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
            "controls": [
                "moderator_capture",
                "sycophancy",
                "participant_dominance",
                "instant_unanimity",
                "strategic_voting",
                "strategic_abstention",
                "evidence_free_majority",
                "lost_dissent",
                "role_collapse",
                "hidden_conflict_of_interest",
                # A STANDING board with a 0.6 supermajority can outvote the same seat
                # every week; min_dissenters_to_block is 1 and suppression is named.
                "minority_suppression",
            ],
            "fast_unanimity_response": [
                "forced_dissent",
                "role_rotation",
                "recruit_independent_critic",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
            },
        },
        "outputs": {
            "required": [
                "transcript",
                "option_cards",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "action_plan",
                "final_recommendation",
                "decision_lineage",
                "resumable_state",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("deterministic_where_possible", "both"),
        "metadata": {
            "title": "P46 architecture-review-board",
            "spec_citations": [
                f"{DOC}:851-865",
                "_USER-PROMPTS.md:11193",
                "_USER-PROMPTS.md:11187-11188",
            ],
            "lineage": [
                "P46 architecture-review-board",
                "enterprise ARB",
                "estate: metaswarm architect and CTO agents",
            ],
            "notes": "OWNER-DECISION on this card is YES and its recommended default is NO (adopt only above 1 architecture decision per week), so objective.owner_constraints.approval_required is true. speaking_order is seniority BECAUSE the card conflicts with P05 rotating-chair: standing memory is the mechanism. Delegation exists so an absent standing seat does not silently drop quorum, and the map is a single acyclic hop. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P47


def p47() -> Dict[str, Any]:
    return {
        "council_id": "p47-incident-war-room",
        "preset": "incident_war_room",
        "objective": {
            "statement": "During an outage, trade deliberation quality for decision latency explicitly and pre-commit to the retrospective.",
            "charter": "SRE incident command. One commander decides unilaterally; seats report facts only; the scribe timestamps every action with a rollback note. Entry requires a named failing detector; the postmortem is scheduled at OPEN, not at close.",
            "risk_tier": "critical",
            "desired_output": "decision",
            "success_criteria": [
                "entry justified by a named failing detector artifact",
                "every action timestamped with a rollback note",
                "a postmortem id scheduled before the first action, not at stand-down",
                "all decisions marked provisional and revisited at stand-down",
            ],
            "consensus_intent": "adjudicate",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "command_output",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": False,
                "forbidden_actions": [
                    "entering war-room mode without an incident trigger artifact",
                    "taking an irreversible action without a rollback note",
                ],
                "deadline_minutes": 45,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 4},
            "roster": [
                seat(
                    "incident-commander",
                    "chair",
                    ["incident command"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="chair",
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_veto": True,
                        "may_call_experiment": True,
                        "may_recruit": True,
                    },
                    effort="max",
                ),
                seat(
                    "facts-1",
                    "custom:facts_reporter",
                    ["telemetry", "process state"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="contributor",
                    rights={
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                    context={
                        "briefing": "Report observed facts with their probe. Do not propose, do not argue, do not vote."
                    },
                ),
                seat(
                    "facts-2",
                    "custom:facts_reporter",
                    ["service dependencies"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="contributor",
                    rights={
                        "may_speak": True,
                        "may_vote": False,
                        "may_call_experiment": True,
                    },
                    context={
                        "briefing": "Report observed facts with their probe. Do not propose, do not argue, do not vote."
                    },
                ),
                seat(
                    "war-room-scribe",
                    "scribe",
                    ["action log", "rollback notes"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="observer",
                    tools=["scribe_log", "incident_registry"],
                    rights={"may_speak": True, "may_vote": False},
                ),
            ],
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "role_collapse"],
                "preserve_prior_positions": True,
            },
        },
        "topology": {"kind": "chair_led", "chair": "incident-commander"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "stage_id": "entry",
                    "custom_name": "incident-entry-gate",
                    "rounds": 1,
                    "participants": ["incident-commander", "war-room-scribe"],
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:named_failing_detector_present",
                                "==",
                                True,
                                "boolean",
                                "incident_registry",
                                "Card failure mode: war-room mode used for non-incidents. Entry requires an explicit incident trigger artifact.",
                            ),
                            custom(
                                "custom:scheduled_postmortem_id_present",
                                "==",
                                True,
                                "boolean",
                                "incident_registry",
                                "Card proof gate: the postmortem id is created at OPEN. Scheduling it at close is the failure this protocol pre-commits against.",
                            ),
                        ]
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "facts",
                    "custom_name": "facts-only-reporting",
                    "rounds": 3,
                    "participants": ["facts-1", "facts-2", "war-room-scribe"],
                },
                # Consensus is suspended DURING the incident, not permanently. "Decisions are
                # provisional and revisited at stand-down" is exactly cross-examination of the
                # commander's calls, so it is a real stage with a counterexample quota rather
                # than a promise. This is where the suspended response obligations land.
                {
                    "kind": "cross_examination",
                    "stage_id": "stand-down-challenge",
                    "rounds": 1,
                    "quotas": {
                        "objections_per_participant": 1,
                        "counterexamples_per_round": 1,
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "stand-down",
                    "custom_name": "stand-down-and-provisional-review",
                    "rounds": 1,
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:actions_without_rollback_note",
                                "==",
                                0,
                                "number",
                                "scribe_log",
                                "Card reversibility note: actions taken may be hard to revert; require a rollback note per action.",
                            ),
                            custom(
                                "custom:provisional_decisions_unreviewed",
                                "==",
                                0,
                                "number",
                                "scribe_log",
                            ),
                        ]
                    },
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 1, "max": 6},
            "turn": {"max_words": 120, "time_limit_seconds": 90},
            # must_respond_to_prior is FALSE during the incident (facts seats report, they do not
            # debate) but cross_examination and rebuttal are TRUE because they are owed at
            # stand-down. Latency is bought from the live phase only.
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "declare_confidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
            },
            "critique_intensity": "gentle",
            "experiments": {
                "allowed": True,
                "required_before_decision": False,
                "max_experiments": 10,
                "runner": "local",
            },
        },
        "budgets": {
            "effort": "max",
            "time_minutes": 45,
            "turns": 40,
            "speaking_quota_per_participant": 12,
            "max_inactivity_rounds": 1,
        },
        "targets": {
            "evidence_items": 4,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.9,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "synthesis_only",
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
            },
            "tie_break": "chair",
        },
        "consensus": {
            "threshold": 0.0,
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
        "source_expression": "(executable_test_settled == true AND objections_open == 0) OR time_minutes >= 45",
        "stopping_extra": {
            "minimum_deliberation": {"min_rounds": 1, "min_evidence_items": 2},
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 45,
                "on_cap": "conditional_decision",
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
                "every provisional decision revisited at stand-down",
                "the scheduled postmortem executed against its id",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 1},
            "resolution": [
                "chair_ruling",
                "run_experiment",
                "narrow_scope",
                "escalate_to_owner",
            ],
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
                "sycophancy",
                "silence",
                "role_collapse",
                "instant_unanimity",
                "lost_dissent",
                "evidence_free_majority",
                "weak_synthesis",
            ],
            "fast_unanimity_response": ["forced_dissent", "strongest_counterexample"],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
                "quarantine_untrusted_sources": True,
            },
        },
        "outputs": {
            "required": [
                "transcript",
                "evidence_map",
                "dissent_minority_report",
                "unresolved_unknowns",
                "action_plan",
                "decision_lineage",
                "resumable_state",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("best_effort", "both"),
        "metadata": {
            "title": "P47 incident-war-room",
            "spec_citations": [
                f"{DOC}:867-881",
                "_USER-PROMPTS.md:10932",
                "_USER-PROMPTS.md:11189",
            ],
            "lineage": ["P47 incident-war-room", "SRE incident command"],
            "notes": "The latency-for-quality trade is EXPLICIT and bounded: the OR branch fires at time_minutes >= 45, matching hard_caps.max_minutes and objective.owner_constraints.deadline_minutes, so the trade cannot silently become permanent. voting is synthesis_only because the commander decides unilaterally - but minority_report is REQUIRED, so suspending consensus does not suspend the record of dissent. Anti-failure leads with moderator_capture: unilateral authority is this protocol's own declared security risk. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- P48


def p48() -> Dict[str, Any]:
    return {
        "council_id": "p48-kill-the-company",
        "preset": "custom",
        "objective": {
            "statement": "Task the seats with destroying the estate's own capability, then invert the attack list into a ranked defence backlog.",
            "charter": "Bodell kill-the-company, aimed at the harness rather than an artifact. Each attack must name the concrete file, task or config it would touch; the backlog is ranked by how CHEAPLY the attack succeeds.",
            "risk_tier": "high",
            "desired_output": "ranked_options",
            "success_criteria": [
                "every attack names a concrete file, task or config",
                "at least one attack maps to an already-known real incident",
                "the attack list inverted into a defence backlog ranked by attack cheapness",
            ],
            "consensus_intent": "elicit_distribution",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "forbidden_actions": [
                    "executing any attack against the live estate",
                    "targeting any system the owner does not control",
                ]
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
            "count": {"mode": "exact", "exact_n": 6},
            "diversity": {
                "min_distinct_vendors": 3,
                "min_distinct_expertise": 5,
                "max_share_per_vendor": 0.5,
            },
            "roster": [
                seat(
                    "attacker-1",
                    "red_team",
                    ["harness internals", "hooks and gates"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    context={
                        "briefing": "Design the change that would most damage this estate's capability. Name the file, task or config. Paper attacks are rejected."
                    },
                ),
                seat(
                    "attacker-2",
                    "red_team",
                    ["supply chain", "marketplace and plugins"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
                seat(
                    "attacker-3",
                    "red_team",
                    ["credentials and sessions"],
                    model="gemini-3-pro",
                    vendor="google",
                    authority="voter",
                ),
                seat(
                    "defender-1",
                    "blue_team",
                    ["detection and gates"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                ),
                seat(
                    "defender-2",
                    "blue_team",
                    ["recovery and rollback"],
                    model="gpt-5-codex",
                    vendor="openai",
                    authority="voter",
                ),
                seat(
                    "calibration-auditor",
                    "calibrator",
                    ["incident history", "attack plausibility"],
                    model="opus-5",
                    vendor="anthropic",
                    authority="voter",
                    tools=["attack_ledger"],
                    rights={
                        "may_speak": True,
                        "may_vote": True,
                        "may_call_experiment": True,
                    },
                ),
            ],
            "recruitment": {
                "dynamic": True,
                "triggers": ["low_novelty", "fast_unanimity", "missing_expertise"],
                "max_recruits": 3,
            },
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 2},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["vendor", "position_similarity"],
                "max_similarity": 0.8,
            },
        },
        "topology": {"kind": "red_blue"},
        "protocol": {
            "sequence": [
                {
                    "kind": "brainstorm",
                    "stage_id": "attack-generation",
                    "rounds": 3,
                    "independent": True,
                    "anonymous": True,
                    "participants": ["attacker-1", "attacker-2", "attacker-3"],
                    "quotas": {"ideas_per_participant": 8, "novel_ideas_per_round": 3},
                },
                {
                    "kind": "war_game",
                    "stage_id": "attack-vs-defence",
                    "rounds": 2,
                    "quotas": {
                        "counterexamples_per_round": 2,
                        "objections_per_participant": 2,
                    },
                },
                {
                    "kind": "custom",
                    "stage_id": "invert",
                    "custom_name": "attack-list-to-defence-backlog",
                    "rounds": 1,
                    "exit_when": {
                        "all_of": [
                            custom(
                                "custom:attacks_without_concrete_target",
                                "==",
                                0,
                                "number",
                                "attack_ledger",
                                "Card failure mode: produces fantasy attacks. Every attack must name the concrete file, task or config it would touch.",
                            ),
                            custom(
                                "custom:attacks_matching_known_incident",
                                ">=",
                                1,
                                "number",
                                "attack_ledger.calibration_probe",
                                "Card proof gate: at least one attack must map to an already-known real incident (e.g. install.py replacing the hooks key), proving the lens is calibrated rather than imaginative.",
                            ),
                            custom(
                                "custom:defence_items_without_cost_estimate",
                                "==",
                                0,
                                "number",
                                "attack_ledger",
                                "Ranking is by how CHEAPLY the attack succeeds, so a defence item without an attack-cost estimate cannot be ranked.",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "defence-backlog"},
            ],
            "speaking_order": "random",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 300},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "steelman_before_rebuttal": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "declare_confidence": True,
                "forced_dissent": True,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": False,
                "max_experiments": 4,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "xhigh",
            "time_minutes": 120,
            "turns": 48,
            "speaking_quota_per_participant": 9,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "unique_ideas": 24,
            "raw_ideas": 40,
            "categories": 5,
            "novelty_ratio": 0.6,
            "diversity_index": 0.65,
            "counterexamples": 6,
            "objections": 10,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.75,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "bayesian",
            "belief_aggregation": {
                "method": "logarithmic_pool",
                "require_confidence_per_vote": True,
                "calibration_source": "attack_ledger.calibration_probe",
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
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.5,
            "measure": "confidence_overlap",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": True,
            "fast_unanimity_is_suspicious": True,
        },
        "source_expression": "unique_ideas >= 20 AND novelty_ratio >= 0.6 AND categories_covered >= 5 AND all_participants_spoke == true",
        "stopping_extra": {
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "min_minutes": 20,
                "every_participant_spoke": True,
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
                "irreducible_disagreement",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "each top-ranked defence item assigned an owner and a detector"
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.8},
            "resolution": [
                "rotate_roles",
                "recruit_independent_critic",
                "forced_dissent",
                "strongest_counterexample",
                "narrow_scope",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
        },
        "anti_failure": {
            "controls": [
                "idea_count_gaming",
                "duplicate_novelty",
                "echo_chamber",
                "instant_unanimity",
                "premature_convergence",
                "role_collapse",
                "participant_dominance",
                "hallucinated_expertise",
                "lost_dissent",
                "weak_synthesis",
            ],
            "fast_unanimity_response": [
                "role_rotation",
                "forced_dissent",
                "strongest_counterexample",
                "recruit_independent_critic",
            ],
            "injection_defense": {
                "treat_artifacts_as_data": True,
                "strip_instructions_from_participant_output": True,
                "quarantine_untrusted_sources": True,
            },
        },
        "outputs": {
            "required": [
                "idea_ledger",
                "idea_catalog",
                "option_cards",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "action_plan",
                "final_recommendation",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": audit_block("seeded"),
        "metadata": {
            "title": "P48 kill-the-company",
            "spec_citations": [
                f"{DOC}:883-897",
                "_USER-PROMPTS.md:10929",
                "_USER-PROMPTS.md:11236-11237",
            ],
            "lineage": [
                "P48 kill-the-company",
                "Lisa Bodell kill-the-company exercise",
            ],
            "notes": "Role collapse is the signature failure of this protocol (attackers start defending what they know), so attack generation runs anonymous and INDEPENDENT before red meets blue, role_collapse is a declared control, and role_rotation leads the fast-unanimity response. objective.owner_constraints forbids executing any attack and forbids non-owner targets - the exercise produces a backlog, never an action. "
            + RECEIPT_NOTE,
        },
    }


# --------------------------------------------------------------------------- assemble

BUILDERS = [p37, p38, p39, p40, p41, p42, p43, p44, p45, p46, p47, p48]


def finalize_stopping(node: Dict[str, Any]) -> None:
    """Replace every `expression: None` sentinel with parse(source_expression).

    SEM-001 compares the two forms for tree equality; deriving one from the other
    with the reference parser makes drift impossible rather than merely unlikely.
    """
    stopping = node.get("stopping")
    if isinstance(stopping, dict) and stopping.get("expression") is None:
        src = stopping["source_expression"]
        tree = parse(src)
        if parse(unparse(tree)) != tree:
            raise SystemExit(f"FAILED:gen tree not idempotent under unparse: {src!r}")
        stopping["expression"] = tree
    for sub in (node.get("topology") or {}).get("subcouncils") or []:
        finalize_stopping(sub)


def build(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a builder's flat dict into a schema-ordered CouncilSpec."""
    src = raw.pop("source_expression")
    extra = raw.pop("stopping_extra", {})
    stopping = {"source_expression": src, "expression": None}
    stopping.update(extra)

    spec: Dict[str, Any] = {"schema_version": "1.0.0"}
    for key in ("council_id", "preset", "participation"):
        if key in raw:
            spec[key] = raw.pop(key)
    spec.setdefault("participation", "agent_only")
    for key in (
        "objective",
        "participants",
        "preparation",
        "topology",
        "protocol",
        "budgets",
        "targets",
        "voting",
        "consensus",
    ):
        if key in raw:
            spec[key] = raw.pop(key)
    spec["stopping"] = stopping
    for key in ("outcomes", "deadlock", "anti_failure", "outputs", "audit", "metadata"):
        if key in raw:
            spec[key] = raw.pop(key)
    if raw:
        raise SystemExit(f"FAILED:gen unconsumed keys {sorted(raw)}")
    finalize_stopping(spec)
    return spec


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    slugs = {
        "p37": "pairwise-comparison",
        "p38": "analysis-of-competing-hypotheses",
        "p39": "key-assumptions-check",
        "p40": "quality-of-information-check",
        "p41": "deception-detection",
        "p42": "argument-mapping",
        "p43": "premortem",
        "p44": "postmortem-5whys-causal",
        "p45": "scientific-peer-review",
        "p46": "architecture-review-board",
        "p47": "incident-war-room",
        "p48": "kill-the-company",
    }
    written = []
    for builder in BUILDERS:
        spec = build(builder())
        cid = spec["council_id"]
        num_ = cid.split("-", 1)[0]
        expect = f"{num_}-{slugs[num_]}"
        if cid != expect:
            raise SystemExit(f"FAILED:gen council_id {cid!r} != expected {expect!r}")
        path = os.path.join(OUT, f"{cid}.councilspec.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(spec, fh, indent=2, ensure_ascii=True)
            fh.write("\n")
        written.append(path)
    if len(written) != 12:
        print(f"FAILED:gen-protocols wrote {len(written)} files, expected 12")
        return 1
    for path in written:
        print(f"wrote {path}")
    print(f"SUCCESS:gen-protocols 12 CouncilSpec instances in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
