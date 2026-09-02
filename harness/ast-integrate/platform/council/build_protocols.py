"""Author council protocol blueprints P13-P24 as executable CouncilSpec instances.

Lane: build/proto-2 (PHASE 2C, protocols 13-24 of 48).

WHY A BUILDER AND NOT 12 HAND-TYPED FILES
-----------------------------------------
`stopping.expression` is a typed JSON tree and `stopping.source_expression` is its human
form; semantic rule SEM-001 fails a spec whose two forms disagree. Hand-transcribing a tree
next to its string is exactly the drift SEM-001 exists to catch, so every tree here is
DERIVED from its string with the shipped parser (`councilspec.expression.parse`). The JSON
files are the deliverable; this module is the authoring tool that keeps the two forms
provably identical.

Design source (prose, already reviewed, NOT re-litigated here):
  ~/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.md lines 305-503.

Contract the emitted instances must satisfy: platform/schema/councilspec.schema.json
(schema layer) + platform/lib/councilspec/semantics.py (SEM-001..SEM-012).

Run:  python platform/council/build_protocols.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from councilspec.expression import parse  # noqa: E402

OUT_DIR = REPO / "platform" / "council" / "protocols"
DESIGN_DOC = "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
RECEIPT = "platform/schema/receipt.schema.json"

# Failure classes this lane is required to defend against (the spawn brief's list, mapped
# onto anti_failure.controls enum values). Every protocol must declare >= 3 of these.
MANDATED_CONTROLS = frozenset(
    {
        "echo_chamber",
        "sycophancy",
        "moderator_capture",
        "participant_dominance",
        "silence",
        "circular_debate",
        "role_collapse",
        "missing_expertise",
        "strategic_voting",
        "evidence_free_majority",
        "premature_convergence",
        "endless_debate",
        "idea_count_gaming",
        "lost_dissent",
        "weak_synthesis",
    }
)


def stop(source: str) -> Dict[str, Any]:
    """Return the {source_expression, expression} pair, tree derived from the string."""
    return {"source_expression": source, "expression": parse(source)}


def leaf(metric: str, op: str, value: Any, producer: str, note: str) -> Dict[str, Any]:
    """A stage-level exit_when leaf. Custom metrics MUST name their producer (SEM-012)."""
    out: Dict[str, Any] = {"metric": metric, "op": op, "value": value}
    if metric.startswith("custom:"):
        out["value_type"] = (
            "boolean"
            if isinstance(value, bool)
            else "number"
            if isinstance(value, (int, float))
            else "string"
        )
        out["producer"] = producer
    out["note"] = note
    return out


AUDIT_STRICT: Dict[str, Any] = {
    "transcript": True,
    "replay": True,
    "resume": True,
    "determinism": "deterministic_where_possible",
    "privacy": {
        "redact_secrets": True,
        "redaction_policy": "deny_by_default",
        "retain_days": 90,
        "pii_policy": "redact",
    },
    "safety": {
        "forbid_irreversible_actions": True,
        "owner_approval_for": ["merge", "release"],
    },
    "persistence": {"store": "both", "checkpoint_every_round": True},
    "calibration": {"post_run": True, "score": "brier"},
}

INJECTION_DEFENSE = {
    "treat_artifacts_as_data": True,
    "strip_instructions_from_participant_output": True,
    "quarantine_untrusted_sources": True,
}


# --------------------------------------------------------------------------- P13


def p13() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "council_id": "p13-hostile-cross-examination",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Determine whether ONE flagged claim survives depth-first hostile cross-examination, or names the question it cannot answer.",
            "charter": "ADVERSARIAL family. One examiner, one witness, a referee who rules non-answers. Scope is a single claim; the merits of sibling claims are out of scope.",
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "the examiner put at least 3 questions on the SAME claim",
                "every non-answer was ruled and the question re-put verbatim",
                "the selection reason for this claim is logged before the first question",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.85,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 60},
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
                    "participant_id": "referee",
                    "display_name": "Referee (rules non-answers, logs claim selection)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["adjudication", "evidence standards"],
                    "role": "chair",
                    "authority": "judge",
                    "rights": {"may_speak": True, "may_vote": True},
                },
                {
                    "participant_id": "examiner",
                    "display_name": "Examiner (uncooperative, hunts the unanswerable question)",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["cross-examination", "falsification"],
                    "role": "custom:examiner",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "effort": "high",
                },
                {
                    "participant_id": "witness",
                    "display_name": "Witness (author or defender of the flagged claim)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["the claim under examination"],
                    "role": "custom:witness",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                },
                {
                    "participant_id": "clerk",
                    "display_name": "Evidence clerk (anchors, non-answer log)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["evidence handling", "transcript integrity"],
                    "role": "scribe",
                    "authority": "observer",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "replacement": {
                "enabled": True,
                "triggers": [
                    "role_collapse",
                    "inactivity",
                    "prompt_injection_detected",
                ],
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
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {"kind": "chair_led", "chair": "referee"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "claim-statement",
                    "independent": True,
                    "participants": ["witness"],
                    "rounds": 1,
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "xexam",
                    "rounds": 6,
                    "participants": ["examiner", "witness", "referee"],
                    "quotas": {
                        "objections_per_participant": 3,
                        "counterexamples_per_round": 1,
                    },
                    "exit_when": {
                        "any_of": [
                            leaf(
                                "custom:non_answer_streak",
                                ">=",
                                2,
                                "non_answer_detector",
                                "two consecutive ruled non-answers terminate the claim as unsupported",
                            ),
                            leaf(
                                "objections_open",
                                "==",
                                0,
                                "",
                                "every put question was answered directly",
                            ),
                        ]
                    },
                },
                {
                    "kind": "synthesis",
                    "stage_id": "referee-ruling",
                    "rounds": 1,
                    "participants": ["referee"],
                },
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": False},
            "turn": {"max_words": 400},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {"allowed": True, "max_experiments": 2, "runner": "sandbox"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 60,
            "tool_calls": 80,
            "sources": 12,
            "turns": 24,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 3,
        },
        "targets": {
            "objections": 6,
            "counterexamples": 2,
            "evidence_items": 8,
            "novelty_ratio": 0.5,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "judge",
            "quorum": {"min_voters": 1, "on_failure": "escalate_to_owner"},
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
            "threshold": 1.0,
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
        "stopping": {
            **stop(
                "objections_addressed >= 3 AND (objections_open == 0 AND evidence_items >= 6 "
                "OR unresolved_load_bearing_counterexample >= 1 OR rounds_elapsed >= 6)"
            ),
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 1,
                "every_participant_spoke": True,
                "min_evidence_items": 4,
                "min_objections_addressed": 3,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 60,
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
                "the claim is re-scoped to exactly what the answered questions support",
                "the unanswered question is recorded verbatim as an open unknown",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "circular_citation_check": True,
            },
            "resolution": [
                "strongest_counterexample",
                "narrow_scope",
                "chair_ruling",
                "escalate_to_owner",
            ],
            "escalation": {"after_attempts": 2, "to": "judge"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "circular_debate",
                "endless_debate",
                "role_collapse",
                "moderator_capture",
                "participant_dominance",
                "evidence_free_majority",
                "prompt_injection",
            ],
            "fast_unanimity_response": [
                "strongest_counterexample",
                "blind_re_evaluation",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "transcript",
                "argument_ledger",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P13 hostile cross-examination",
            "spec_citations": [f"{DESIGN_DOC}:305-321"],
            "notes": (
                "Anti-rabbit-hole: hard cap 6 rounds and a logged claim-selection reason. The card's "
                "adoption proof (non-answer detection must fire on a deliberately evasive control) is the "
                "xexam stage exit_when custom:non_answer_streak, producer non_answer_detector - the producer "
                "is NOT implemented by this unit, so the detector itself is NOT-CHECKED here."
            ),
        },
    }


# --------------------------------------------------------------------------- P14


def p14() -> Dict[str, Any]:
    jurors = [
        ("juror-1", "opus-5", "anthropic", ["log analysis", "timeline reconstruction"]),
        ("juror-2", "gpt-5-codex", "openai", ["static analysis", "reading diffs"]),
        ("juror-3", "gemini-3-pro", "google", ["measurement design", "statistics"]),
        ("juror-4", "opus-5", "anthropic", ["build systems", "CI forensics"]),
        ("juror-5", "gpt-5-codex", "openai", ["test semantics", "coverage"]),
    ]
    roster: List[Dict[str, Any]] = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "juror",
            "authority": "voter",
            "vote_weight": 1.0,
            "rights": {"may_speak": True, "may_vote": True},
            "context": {"partition_id": "facts-only"},
            "independence": {"sees_peers_before_first_position": False},
        }
        for pid, model, vendor, exp in jurors
    ]
    roster.append(
        {
            "participant_id": "judge",
            "display_name": "Judge (applies the rule to the found facts; may not find facts)",
            "model": "opus-5",
            "vendor": "anthropic",
            "expertise": ["decision rules", "compliance gates"],
            "role": "judge",
            "authority": "judge",
            "rights": {"may_speak": True, "may_vote": True},
            "context": {"partition_id": "found-facts-and-rule"},
        }
    )
    roster.append(
        {
            "participant_id": "clerk",
            "model": "opus-5",
            "vendor": "anthropic",
            "expertise": ["fact-set diffing", "transcript integrity"],
            "role": "scribe",
            "authority": "observer",
            "rights": {"may_speak": True, "may_vote": False},
        }
    )
    return {
        "schema_version": "1.0.0",
        "council_id": "p14-judge-and-jury",
        "preset": "evidence_adjudication_jury",
        "participation": "agent_only",
        "objective": {
            "statement": "Separate fact-finding from rule-application: the jury finds facts under an evidence standard, the judge applies the gate rule to exactly those facts.",
            "charter": "JUDICIAL family. The judge may not add, remove or reinterpret a fact; the jury may not apply the rule. Any judge-side fact the jury did not find is a protocol violation.",
            "risk_tier": "high",
            "desired_output": "go_no_go",
            "success_criteria": [
                "the judge output quotes the jury fact list verbatim and adds none",
                "a diff of judge facts against jury facts is empty",
                "each found fact carries its own file_line anchor",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.9,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": True, "deadline_minutes": 120},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "vendor_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 7, "min": 7, "max": 7},
            "diversity": {
                "min_distinct_vendors": 3,
                "min_distinct_expertise": 5,
                "max_share_per_vendor": 0.6,
            },
            "roster": roster,
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 2},
            "information_partition": {
                "enabled": True,
                "strategy": "role_scoped",
                "partitions": [
                    {
                        "partition_id": "facts-only",
                        "visible_to": [
                            "juror-1",
                            "juror-2",
                            "juror-3",
                            "juror-4",
                            "juror-5",
                        ],
                        "sources": ["the artifact under review", "the evidence pack"],
                    },
                    {
                        "partition_id": "found-facts-and-rule",
                        "visible_to": ["judge"],
                        "sources": [
                            "the jury's found-fact list",
                            "the decision rule text",
                        ],
                    },
                ],
            },
            "replacement": {
                "enabled": True,
                "triggers": ["role_collapse", "inactivity", "conflict_of_interest"],
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
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "position_memo"],
        },
        "topology": {
            "kind": "jury",
            "committees": [
                {
                    "committee_id": "jury",
                    "mandate": "find facts only, under the declared evidence standard",
                    "members": ["juror-1", "juror-2", "juror-3", "juror-4", "juror-5"],
                }
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "fact-drafting",
                    "independent": True,
                    "anonymous": True,
                    "rounds": 1,
                    "participants": [
                        "juror-1",
                        "juror-2",
                        "juror-3",
                        "juror-4",
                        "juror-5",
                    ],
                },
                {
                    "kind": "jury",
                    "stage_id": "fact-finding",
                    "rounds": 3,
                    "participants": [
                        "juror-1",
                        "juror-2",
                        "juror-3",
                        "juror-4",
                        "juror-5",
                    ],
                    "quotas": {"objections_per_participant": 2},
                    "exit_when": {
                        "all_of": [
                            leaf(
                                "unanimity",
                                "==",
                                True,
                                "",
                                "the fact set is agreed by every juror",
                            ),
                            leaf(
                                "evidence_items", ">=", 8, "", "each fact is anchored"
                            ),
                        ]
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "fact-challenge",
                    "rounds": 1,
                    "participants": [
                        "judge",
                        "juror-1",
                        "juror-2",
                        "juror-3",
                        "juror-4",
                        "juror-5",
                    ],
                },
                {
                    "kind": "synthesis",
                    "stage_id": "rule-application",
                    "rounds": 1,
                    "participants": ["judge"],
                    "exit_when": leaf(
                        "custom:judge_added_facts",
                        "==",
                        0,
                        "fact_set_diff",
                        "diff(judge facts, jury facts) must be empty; any addition is a protocol violation",
                    ),
                },
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
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
            "time_minutes": 120,
            "tool_calls": 200,
            "sources": 25,
            "turns": 40,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "objections": 6,
            "counterexamples": 3,
            "evidence_items": 16,
            "coverage_score": 0.9,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "judge",
            "quorum": {
                "min_voters": 5,
                "min_fraction": 0.7,
                "on_failure": "extend_rounds",
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
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
            "tie_break": "judge",
        },
        "consensus": {
            "threshold": 1.0,
            "measure": "vote_share",
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
            **stop(
                "all_participants_spoke == true AND evidence_items >= 8 AND "
                "(verdict == CONFIRMED OR verdict == REFUTED OR deadlock_detected == true)"
            ),
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 5,
                "every_participant_spoke": True,
                "min_evidence_items": 8,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 120,
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
                "every fact the rule depends on is anchored and unanimous",
                "the judge records which rule clause each fact satisfies",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "circular_citation_check": True,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "blind_re_evaluation",
                "strongest_counterexample",
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
            "controls": [
                "role_collapse",
                "moderator_capture",
                "sycophancy",
                "evidence_free_majority",
                "lost_dissent",
                "premature_convergence",
                "hidden_conflict_of_interest",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "strongest_counterexample",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "evidence_map",
                "claim_evidence_contradiction_graph",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P14 judge and jury",
            "spec_citations": [f"{DESIGN_DOC}:324-339"],
            "notes": (
                "Fact/rule separation is carried mechanically by information_partition (jurors see the "
                "artifact, the judge sees ONLY the found-fact list plus the rule) plus the rule-application "
                "stage exit_when custom:judge_added_facts == 0, producer fact_set_diff. The producer is not "
                "implemented by this unit: the separation is SPECIFIED and schema-valid, NOT-CHECKED at runtime."
            ),
        },
    }


# --------------------------------------------------------------------------- P15


def p15() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "council_id": "p15-claim-by-claim-adjudication",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Adjudicate an artifact one atomic claim at a time so a document verdict is a function of claim verdicts, not a global impression.",
            "charter": "JUDICIAL family. Verdict granularity is the CLAIM. Each claim gets CONFIRMED / REFUTED / UNVERIFIED / SCOPED with its own anchor. A coverage line (claims_found vs claims_adjudicated) with a truncation flag is mandatory.",
            "risk_tier": "high",
            "desired_output": "review_verdict",
            "success_criteria": [
                "every extracted claim carries an independent verdict and its own anchor",
                "the coverage line reports claims_found and claims_adjudicated with a truncation flag",
                "a seeded overclaim is returned REFUTED while its correctly-scoped sibling is CONFIRMED",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.9,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 180},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 4},
            "roster": [
                {
                    "participant_id": "extractor-a",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["claim extraction", "implicit premises"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "extractor-b",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["claim extraction", "scope analysis"],
                    "role": "verifier",
                    "authority": "contributor",
                    "rights": {"may_speak": True, "may_vote": False},
                    "independence": {"sees_peers_before_first_position": False},
                },
                {
                    "participant_id": "adjudicator-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["evidence grading", "overclaim detection"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "adjudicator-2",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["evidence grading", "reproduction"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "adjudicator-3",
                    "model": "gemini-3-pro",
                    "vendor": "google",
                    "expertise": ["measurement validity", "statistics"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                },
                {
                    "participant_id": "coverage-clerk",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["coverage accounting", "truncation flags"],
                    "role": "scribe",
                    "authority": "observer",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["prompt", "position_similarity"],
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
            "required_artifacts": ["evidence_pack", "prior_art_scan"],
        },
        "topology": {
            "kind": "committee",
            "committees": [
                {
                    "committee_id": "extraction",
                    "mandate": "enumerate atomic claims, including implicit ones, and emit the coverage line",
                    "members": ["extractor-a", "extractor-b", "coverage-clerk"],
                },
                {
                    "committee_id": "adjudication",
                    "mandate": "one independent verdict per claim, each with its own anchor",
                    "members": ["adjudicator-1", "adjudicator-2", "adjudicator-3"],
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "claim-extraction",
                    "independent": True,
                    "rounds": 1,
                    "participants": ["extractor-a", "extractor-b"],
                },
                {
                    "kind": "custom",
                    "custom_name": "coverage_line_and_truncation_flag",
                    "stage_id": "coverage-line",
                    "rounds": 1,
                    "participants": ["coverage-clerk"],
                    "exit_when": leaf(
                        "custom:claims_unadjudicated",
                        "==",
                        0,
                        "claim_coverage_line",
                        "claims_found minus claims_adjudicated must be zero, or the truncation flag is set and the artifact verdict is PARTIAL",
                    ),
                },
                {
                    "kind": "jury",
                    "stage_id": "per-claim-verdicts",
                    "rounds": 2,
                    "participants": ["adjudicator-1", "adjudicator-2", "adjudicator-3"],
                    "quotas": {
                        "objections_per_participant": 5,
                        "counterexamples_per_round": 2,
                    },
                },
                {
                    "kind": "cross_examination",
                    "stage_id": "contested-claims",
                    "rounds": 2,
                    "quotas": {"counterexamples_per_round": 2},
                },
                {"kind": "synthesis", "stage_id": "document-verdict", "rounds": 1},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 10, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 5, "runner": "ci"},
        },
        "budgets": {
            "effort": "xhigh",
            "time_minutes": 180,
            "tool_calls": 300,
            "sources": 40,
            "turns": 50,
            "speaking_quota_per_participant": 12,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "objections": 10,
            "counterexamples": 5,
            "evidence_items": 40,
            "coverage_score": 0.95,
            "novelty_ratio": 0.4,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.9,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "juror",
            "quorum": {"min_voters": 3, "on_failure": "recruit"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
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
            "tie_break": "no_decision",
        },
        "consensus": {
            "threshold": 0.9,
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
        "stopping": {
            **stop(
                "coverage_score >= 0.95 AND objections_open == 0 AND "
                "(evidence_items >= 40 OR evidence_saturation == true)"
            ),
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 2,
                "every_participant_spoke": True,
                "min_evidence_items": 20,
                "min_objections_addressed": 5,
            },
            "hard_caps": {
                "max_rounds": 10,
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
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the coverage line is published with its truncation flag",
                "every UNVERIFIED claim names the experiment that would settle it",
                "every REFUTED overclaim is accompanied by its correctly-scoped rewrite",
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
                "split_question",
                "strongest_counterexample",
                "declare_no_decision",
            ],
            "escalation": {"after_attempts": 3, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "weak_synthesis",
                "premature_convergence",
                "evidence_free_majority",
                "idea_count_gaming",
                "lost_dissent",
                "circular_citation",
                "sycophancy",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "strongest_counterexample",
                "recruit_independent_critic",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "claim_evidence_contradiction_graph",
                "evidence_map",
                "argument_ledger",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P15 claim-by-claim adjudication",
            "spec_citations": [f"{DESIGN_DOC}:340-355"],
            "notes": (
                "idea_count_gaming is declared here for the INVERSE of brainstorming: splitting one claim "
                "into trivial variants to inflate the adjudicated count. dedup.trivial_variant_policy=merge "
                "plus targets.coverage_score is the mechanical guard. The seeded-overclaim adoption proof "
                "needs a live executor and is NOT-CHECKED by this unit."
            ),
        },
    }


# --------------------------------------------------------------------------- P16


def p16() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "council_id": "p16-grand-jury-threshold",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Decide only whether there is enough evidentiary substance to justify convening a full council; never decide the merits.",
            "charter": "JUDICIAL family, front door for any council at cost tier deep or above. Output space is PROCEED / INSUFFICIENT / DISMISS. Any statement on the merits is out of scope and must be struck.",
            "risk_tier": "moderate",
            "desired_output": "go_no_go",
            "success_criteria": [
                "the output is exactly one of PROCEED, INSUFFICIENT or DISMISS",
                "a DISMISS names the single anchor that would reverse it",
                "no seat expressed a position on the merits",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.7,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": False,
                "deadline_minutes": 20,
                "budget_ceiling_tokens": 120000,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 3, "min": 3, "max": 3},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 2},
            "roster": [
                {
                    "participant_id": "sufficiency-1",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["evidentiary sufficiency", "triage"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "effort": "low",
                },
                {
                    "participant_id": "sufficiency-2",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["evidentiary sufficiency", "cost control"],
                    "role": "juror",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "effort": "low",
                },
                {
                    "participant_id": "reversal-clerk",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["reversal anchors", "logging"],
                    "role": "verifier",
                    "authority": "voter",
                    "vote_weight": 1.0,
                    "effort": "low",
                },
            ],
            "recruitment": {
                "dynamic": False,
                "triggers": ["missing_expertise"],
                "max_recruits": 0,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": False,
            "independent_prep": True,
            "min_sources": 1,
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "sufficiency-read",
                    "independent": True,
                    "rounds": 1,
                },
                {
                    "kind": "round_robin",
                    "stage_id": "threshold-call",
                    "rounds": 1,
                    "quotas": {"objections_per_participant": 1},
                    "exit_when": {
                        "any_of": [
                            leaf(
                                "custom:threshold_verdict",
                                "==",
                                "PROCEED",
                                "sufficiency_tally",
                                "PROCEED routes to the full council; the merits stay untouched",
                            ),
                            leaf(
                                "custom:dismiss_reversal_anchor_present",
                                "==",
                                True,
                                "dismiss_anchor_logger",
                                "a DISMISS is only admissible when the anchor that would reverse it is logged",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "routing-note", "rounds": 1},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 1, "max": 2, "divergence_before_convergence": False},
            "turn": {"max_words": 250},
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "cross_examination": False,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "standard",
            "experiments": {"allowed": False, "max_experiments": 0, "runner": "local"},
        },
        "budgets": {
            "effort": "low",
            "time_minutes": 20,
            "tokens": 120000,
            "tool_calls": 20,
            "sources": 5,
            "turns": 6,
            "speaking_quota_per_participant": 2,
            "min_engagement_turns": 1,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 1,
        },
        "targets": {
            "objections": 2,
            "evidence_items": 3,
            "novelty_ratio": 0.5,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "supermajority",
            "supermajority_threshold": 0.66,
            "quorum": {"min_voters": 3, "on_failure": "escalate_to_owner"},
            "abstention": {
                "allowed": False,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.66,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": False,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            **stop(
                "all_participants_spoke == true AND (consensus >= 0.66 OR rounds_elapsed >= 2)"
            ),
            "minimum_deliberation": {
                "min_rounds": 1,
                "min_independent_positions": 3,
                "every_participant_spoke": True,
                "min_evidence_items": 2,
            },
            "hard_caps": {"max_rounds": 2, "max_minutes": 20, "on_cap": "no_decision"},
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
                "INSUFFICIENT names exactly what additional evidence would flip it to PROCEED",
                "DISMISS logs the anchor that would reverse it and that path is reversible on request",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 1, "vote_oscillation_rounds": 2},
            "resolution": ["narrow_scope", "escalate_to_owner", "declare_no_decision"],
            "escalation": {"after_attempts": 1, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": True,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "silence",
                "strategic_abstention",
                "moderator_capture",
                "missing_expertise",
                "premature_convergence",
                "minority_suppression",
            ],
            "fast_unanimity_response": ["forced_dissent", "strongest_counterexample"],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "votes_by_round",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P16 grand-jury threshold",
            "spec_citations": [f"{DESIGN_DOC}:356-371"],
            "notes": (
                "The card's silent-veto failure mode is answered structurally: abstention is FORBIDDEN, "
                "minority_report is REQUIRED, and a DISMISS is inadmissible unless "
                "custom:dismiss_reversal_anchor_present is true (producer dismiss_anchor_logger). The three "
                "output tokens PROCEED / INSUFFICIENT / DISMISS are carried as a custom:threshold_verdict "
                "metric because the schema's outcome enum has no merits-free routing verdict - that is a "
                "substrate gap, reported not hidden."
            ),
        },
    }


# --------------------------------------------------------------------------- P17


def p17() -> Dict[str, Any]:
    jurors = [
        ("hung-juror-1", "opus-5", "anthropic", ["risk analysis"]),
        ("hung-juror-2", "gpt-5-codex", "openai", ["reproduction", "test design"]),
        ("hung-juror-3", "gemini-3-pro", "google", ["statistics", "base rates"]),
        ("hung-juror-4", "opus-5", "anthropic", ["security review"]),
        ("hung-juror-5", "gpt-5-codex", "openai", ["operations", "rollback"]),
        ("hung-juror-6", "opus-5", "anthropic", ["cost modeling"]),
        ("hung-juror-7", "gemini-3-pro", "google", ["user impact"]),
    ]
    roster: List[Dict[str, Any]] = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "juror",
            "authority": "voter",
            "vote_weight": 1.0,
            "rights": {"may_speak": True, "may_vote": True},
        }
        for pid, model, vendor, exp in jurors
    ]
    roster.append(
        {
            "participant_id": "foreperson",
            "display_name": "Foreperson (delivers the Allen charge; may not argue)",
            "model": "opus-5",
            "vendor": "anthropic",
            "expertise": ["process discipline", "deadlock hygiene"],
            "role": "chair",
            "authority": "chair",
            "rights": {"may_speak": True, "may_vote": False},
        }
    )
    return {
        "schema_version": "1.0.0",
        "council_id": "p17-jury-with-allowed-hung",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Reach unanimity on the question or return IRREDUCIBLE_DISAGREEMENT; never manufacture a plurality the evidence does not support.",
            "charter": "JUDICIAL family. Failure to decide is a legitimate terminal state. One Allen-charge round may urge reconsideration WITHOUT any new argument or new anchor; the foreperson must reject a new anchor in that round.",
            "risk_tier": "critical",
            "desired_output": "decision",
            "success_criteria": [
                "a genuinely balanced question returns IRREDUCIBLE_DISAGREEMENT rather than a coin-flip majority",
                "the Allen round introduces zero new anchors",
                "every dissent survives verbatim into the record",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.9,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 3,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": True, "deadline_minutes": 150},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "vendor_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 8, "min": 8, "max": 8},
            "diversity": {
                "min_distinct_vendors": 3,
                "min_distinct_expertise": 6,
                "max_share_per_vendor": 0.5,
            },
            "roster": roster,
            "anonymity": {"mode": "blind_to_peers", "reveal_after_round": 1},
            "replacement": {
                "enabled": True,
                "triggers": ["dominance", "inactivity", "role_collapse"],
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
            "required_artifacts": ["evidence_pack", "risk_list"],
        },
        "topology": {"kind": "jury", "chair": "foreperson"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "independent-verdicts",
                    "independent": True,
                    "anonymous": True,
                    "rounds": 1,
                },
                {
                    "kind": "jury",
                    "stage_id": "deliberation",
                    "rounds": 4,
                    "quotas": {
                        "objections_per_participant": 3,
                        "counterexamples_per_round": 1,
                    },
                },
                {
                    "kind": "custom",
                    "custom_name": "allen_charge_no_new_argument",
                    "stage_id": "allen-charge",
                    "rounds": 1,
                    "participants": ["foreperson"],
                    "exit_when": {
                        "all_of": [
                            leaf(
                                "custom:new_anchors_in_allen_round",
                                "==",
                                0,
                                "allen_round_anchor_diff",
                                "the Allen round may urge reconsideration but may not smuggle in a new anchor",
                            ),
                            leaf(
                                "unanimity",
                                "==",
                                True,
                                "",
                                "reconsideration succeeded; otherwise the outcome is IRREDUCIBLE_DISAGREEMENT",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "verdict-or-hung", "rounds": 1},
            ],
            "speaking_order": "lowest_confidence_first",
            "rounds": {"min": 3, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": True,
            },
            "critique_intensity": "adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 3,
                "runner": "ci",
            },
        },
        "budgets": {
            "effort": "xhigh",
            "time_minutes": 150,
            "tool_calls": 250,
            "sources": 35,
            "turns": 60,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 3,
        },
        "targets": {
            "objections": 10,
            "counterexamples": 4,
            "evidence_items": 24,
            "coverage_score": 0.9,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "unanimity",
            "quorum": {
                "min_voters": 7,
                "min_fraction": 0.85,
                "on_failure": "no_decision",
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "none",
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
            "threshold": 1.0,
            "measure": "vote_share",
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
        "stopping": {
            **stop(
                "rounds_elapsed >= 3 AND (unanimity == true OR deadlock_detected == true OR rounds_elapsed >= 8)"
            ),
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 7,
                "every_participant_spoke": True,
                "min_evidence_items": 12,
                "min_objections_addressed": 5,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 150,
                "on_cap": "escalate_to_owner",
            },
        },
        "outcomes": {
            "allowed": [
                "decision",
                "no_decision",
                "irreducible_disagreement",
                "proof_of_impossibility",
                "minority_report",
                "dissent",
            ]
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.85,
                "vote_oscillation_rounds": 2,
            },
            "resolution": [
                "forced_dissent",
                "blind_re_evaluation",
                "run_experiment",
                "declare_no_decision",
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
                "sycophancy",
                "premature_convergence",
                "participant_dominance",
                "lost_dissent",
                "minority_suppression",
                "strategic_voting",
                "endless_debate",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "strongest_counterexample",
                "role_rotation",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "experiments",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P17 jury with allowed hung verdict",
            "spec_citations": [f"{DESIGN_DOC}:372-387"],
            "notes": (
                "The stopping rule cannot fire before round 3 even under unanimity - that conjunct is the "
                "coercion guard, and the both-states control includes a round-2 unanimous snapshot that "
                "must evaluate FALSE. hard_caps.max_rounds=8 matches the rounds_elapsed >= 8 escape so "
                "SEM-011 has a declared cap to agree with."
            ),
        },
    }


# --------------------------------------------------------------------------- P18


def p18() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "council_id": "p18-two-key-dual-control",
        "preset": "custom",
        "participation": "hybrid",
        "objective": {
            "statement": "Authorise an irreversible action only when two independent authorities both return AUTHORISE on the identical action string.",
            "charter": "JUDICIAL family, dual control. Two isolated keys, different vendors, no shared brief, no tie-break. Either refusal is terminal. The action string is hashed and both keys must have signed the SAME hash.",
            "risk_tier": "critical",
            "desired_output": "go_no_go",
            "success_criteria": [
                "a single AUTHORISE does not open the gate",
                "both keys signed the identical action-string hash",
                "the two briefs differ in provenance, not merely in wording",
            ],
            "consensus_intent": "adjudicate",
            "confidence_target": 0.95,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "command_output",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {
                "approval_required": True,
                "forbidden_actions": [
                    "execute the action before both keys return AUTHORISE",
                    "substitute a tie-break for a missing second key",
                    "rotate, revoke or print any credential",
                ],
                "deadline_minutes": 30,
            },
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "vendor_diverse", "adversarial"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 3, "min": 3, "max": 3},
            "diversity": {
                "min_distinct_vendors": 2,
                "min_distinct_models": 2,
                "max_share_per_vendor": 0.5,
            },
            "roster": [
                {
                    "participant_id": "key-a",
                    "display_name": "Key A (independent authority, vendor 1)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["irreversible-action review", "blast radius"],
                    "role": "verifier",
                    "authority": "veto_holder",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True, "may_veto": True},
                    "context": {"partition_id": "brief-a"},
                    "independence": {
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                },
                {
                    "participant_id": "key-b",
                    "display_name": "Key B (independent authority, vendor 2)",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["irreversible-action review", "rollback feasibility"],
                    "role": "security_reviewer",
                    "authority": "veto_holder",
                    "vote_weight": 1.0,
                    "rights": {"may_speak": True, "may_vote": True, "may_veto": True},
                    "context": {"partition_id": "brief-b"},
                    "independence": {
                        "sees_peers_before_first_position": False,
                        "fresh_context": True,
                    },
                },
                {
                    "participant_id": "owner",
                    "kind": "human",
                    "vendor": "human",
                    "expertise": ["owner intent"],
                    "role": "stakeholder",
                    "authority": "owner",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "anonymity": {"mode": "blind_to_peers"},
            "information_partition": {
                "enabled": True,
                "strategy": "disjoint_evidence",
                "partitions": [
                    {
                        "partition_id": "brief-a",
                        "visible_to": ["key-a"],
                        "sources": [
                            "the action string and its hash",
                            "the primary provenance chain",
                        ],
                    },
                    {
                        "partition_id": "brief-b",
                        "visible_to": ["key-b"],
                        "sources": [
                            "the action string and its hash",
                            "an independently derived provenance chain",
                        ],
                    },
                ],
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["prompt", "vendor", "model", "position_similarity"],
                "max_similarity": 0.6,
            },
            "conflicts_policy": {"disclosure_required": True, "on_conflict": "exclude"},
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "risk_list"],
        },
        "topology": {
            "kind": "caucus",
            "caucuses": [
                {
                    "caucus_id": "key-a-isolated",
                    "members": ["key-a"],
                    "private_rounds": 1,
                },
                {
                    "caucus_id": "key-b-isolated",
                    "members": ["key-b"],
                    "private_rounds": 1,
                },
            ],
        },
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "key-a-review",
                    "independent": True,
                    "rounds": 1,
                    "participants": ["key-a"],
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 1,
                    },
                    "exit_when": leaf(
                        "custom:action_string_hash_matches",
                        "==",
                        True,
                        "action_string_hasher",
                        "key A must have signed the same action-string hash the gate will execute",
                    ),
                },
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "key-b-review",
                    "independent": True,
                    "rounds": 1,
                    "participants": ["key-b"],
                    "quotas": {
                        "objections_per_participant": 2,
                        "counterexamples_per_round": 1,
                    },
                    "exit_when": leaf(
                        "custom:action_string_hash_matches",
                        "==",
                        True,
                        "action_string_hasher",
                        "key B must have signed the SAME hash; a differing hash is a refusal, not a retry",
                    ),
                },
                {
                    "kind": "custom",
                    "custom_name": "logical_and_over_two_isolated_verdicts",
                    "stage_id": "and-gate",
                    "rounds": 1,
                    "exit_when": {
                        "all_of": [
                            leaf("quorum_met", "==", True, "", "both keys reported"),
                            leaf(
                                "custom:brief_provenance_differs",
                                "==",
                                True,
                                "brief_provenance_hasher",
                                "correlated keys are not two keys; provenance must differ, not just wording",
                            ),
                        ]
                    },
                },
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 1, "max": 2, "divergence_before_convergence": False},
            "turn": {"max_words": 450},
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "cross_examination": False,
                "rebuttal_required": False,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "maximally_adversarial",
            "experiments": {
                "allowed": True,
                "required_before_decision": True,
                "max_experiments": 2,
                "runner": "sandbox",
            },
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 30,
            "tool_calls": 60,
            "sources": 10,
            "turns": 6,
            "speaking_quota_per_participant": 2,
            "min_engagement_turns": 1,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 0,
        },
        "targets": {
            "objections": 2,
            "counterexamples": 1,
            "evidence_items": 6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.6,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "unanimity",
            "quorum": {
                "min_voters": 2,
                "min_fraction": 1.0,
                "on_failure": "no_decision",
            },
            "veto": {
                "holders": ["key-a", "key-b"],
                "scope": "final_decision",
                "must_justify": True,
                "overridable_by_owner": False,
            },
            "abstention": {
                "allowed": False,
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
            "threshold": 1.0,
            "measure": "vote_share",
            "minority_report": "required",
            "dissent_policy": {
                "preserve_verbatim": True,
                "attributed": True,
                "min_dissenters_to_block": 1,
                "suppression_check": True,
            },
            "irreducible_disagreement_allowed": False,
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            **stop(
                "quorum_met == true AND participants_active >= 2 AND (unanimity == true OR dissent_count >= 1)"
            ),
            "minimum_deliberation": {
                "min_rounds": 1,
                "min_independent_positions": 2,
                "every_participant_spoke": False,
                "min_evidence_items": 4,
            },
            "hard_caps": {"max_rounds": 2, "max_minutes": 30, "on_cap": "no_decision"},
        },
        "outcomes": {
            "allowed": ["decision", "no_decision", "minority_report", "dissent"],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 1},
            "resolution": ["declare_no_decision", "escalate_to_owner"],
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
                "echo_chamber",
                "evidence_free_majority",
                "silence",
                "hidden_conflict_of_interest",
                "prompt_injection",
                "sycophancy",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "recruit_independent_critic",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "evidence_map",
                "votes_by_round",
                "dissent_minority_report",
                "final_recommendation",
                "decision_lineage",
                "resumable_state",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": {
            **AUDIT_STRICT,
            "safety": {
                "forbid_irreversible_actions": True,
                "owner_approval_for": [
                    "execute the authorised action",
                    "merge",
                    "release",
                    "delete",
                ],
            },
        },
        "metadata": {
            "title": "P18 two-key dual control",
            "spec_citations": [f"{DESIGN_DOC}:388-403"],
            "notes": (
                "SCOPE, stated honestly: the card says dual control has NO aggregation function, and the "
                "schema's voting.method enum has no such value. The nearest faithful encoding is unanimity "
                "over exactly two voters (a logical AND) with quorum.min_fraction 1.0, abstention forbidden, "
                "both keys as veto holders not overridable by the owner, and tie_break no_decision. The "
                "isolation the card demands is carried separately by caucuses, per-key information "
                "partitions, fresh_context and duplicate_detection at max_similarity 0.6. The card's "
                "required both-states proof - a single AUTHORISE must NOT open the gate - is executed as "
                "two independent negative snapshots in PROTOCOL-EXPECTATIONS.json. The per-key quota "
                "(2 objections, 1 counterexample) is the anti-rubber-stamp control: a key that returns "
                "AUTHORISE having recorded zero objections examined nothing."
            ),
        },
    }


# --------------------------------------------------------------------------- P19


def p19() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "council_id": "p19-rfc-last-call",
        "preset": "custom",
        "participation": "hybrid",
        "objective": {
            "statement": "Publish a frozen draft for a bounded comment window and close only when EVERY comment has been individually dispositioned.",
            "charter": "JUDICIAL family, IETF last call. Completeness of disposition is the stopping rule: accepted, rejected-with-a-distinct-reason, or deferred-with-a-named-owner. An unaddressed comment blocks close even after the window expires.",
            "risk_tier": "moderate",
            "desired_output": "specification",
            "success_criteria": [
                "comment count equals disposition count",
                "every rejection carries a distinct reason string, not a boilerplate",
                "every deferral names an owner",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.8,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": True, "deadline_minutes": 240},
        },
        "participants": {
            "selection": {
                "mode": "mixed",
                "strategies": ["exact", "stakeholder_balanced", "expertise_ranked"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "range", "min": 3, "max": 12},
            "diversity": {"min_distinct_vendors": 2, "min_distinct_expertise": 3},
            "roster": [
                {
                    "participant_id": "rfc-editor",
                    "display_name": "Editor (freezes the draft, dispositions every comment)",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["specification editing", "disposition discipline"],
                    "role": "chair",
                    "authority": "chair",
                    "rights": {
                        "may_speak": True,
                        "may_vote": True,
                        "may_recruit": True,
                    },
                },
                {
                    "participant_id": "reviewer-impl",
                    "model": "gpt-5-codex",
                    "vendor": "openai",
                    "expertise": ["implementability", "edge cases"],
                    "role": "critic",
                    "authority": "contributor",
                },
                {
                    "participant_id": "reviewer-security",
                    "model": "opus-5",
                    "vendor": "anthropic",
                    "expertise": ["threat modeling", "abuse cases"],
                    "role": "security_reviewer",
                    "authority": "veto_holder",
                    "rights": {"may_speak": True, "may_vote": True, "may_veto": True},
                },
                {
                    "participant_id": "owner",
                    "kind": "human",
                    "vendor": "human",
                    "expertise": ["owner intent"],
                    "role": "stakeholder",
                    "authority": "owner",
                    "rights": {"may_speak": True, "may_vote": False},
                },
            ],
            "recruitment": {
                "dynamic": True,
                "triggers": ["missing_expertise", "owner_request", "low_novelty"],
                "max_recruits": 8,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 1,
            "prep_time_minutes": 30,
            "required_artifacts": ["prior_art_scan", "position_memo"],
        },
        "topology": {"kind": "chair_led", "chair": "rfc-editor"},
        "protocol": {
            "sequence": [
                {
                    "kind": "custom",
                    "custom_name": "freeze_draft_and_publish_hash",
                    "stage_id": "freeze",
                    "rounds": 1,
                    "participants": ["rfc-editor"],
                    "exit_when": leaf(
                        "custom:draft_frozen_hash_published",
                        "==",
                        True,
                        "draft_freezer",
                        "the window opens against a frozen, hashed draft so late edits cannot orphan a comment",
                    ),
                },
                {
                    "kind": "round_robin",
                    "stage_id": "comment-window",
                    "rounds": 2,
                    "quotas": {"objections_per_participant": 4},
                },
                {
                    "kind": "custom",
                    "custom_name": "disposition_every_comment",
                    "stage_id": "disposition",
                    "rounds": 2,
                    "exit_when": {
                        "all_of": [
                            leaf(
                                "objections_open",
                                "==",
                                0,
                                "",
                                "no comment is left undispositioned",
                            ),
                            leaf(
                                "custom:distinct_rejection_reasons_ratio",
                                ">=",
                                1,
                                "disposition_reason_uniqueness_check",
                                "one distinct reason per rejected comment; bulk boilerplate rejection is inadmissible",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "close-or-reopen", "rounds": 1},
            ],
            "speaking_order": "chair_directed",
            "rounds": {"min": 2, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": False,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "standard",
            "experiments": {"allowed": True, "max_experiments": 2, "runner": "ci"},
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 240,
            "tool_calls": 120,
            "sources": 20,
            "turns": 40,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 1,
            "max_inactivity_rounds": 3,
            "rebuttal_depth": 2,
        },
        "targets": {
            "objections": 8,
            "evidence_items": 12,
            "coverage_score": 0.95,
            "novelty_ratio": 0.4,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.9,
                "trivial_variant_policy": "flag_for_review",
            },
        },
        "voting": {
            "method": "consent_no_objection",
            "quorum": {"min_voters": 3, "on_failure": "extend_rounds"},
            "veto": {
                "holders": ["reviewer-security"],
                "scope": "safety_only",
                "must_justify": True,
                "overridable_by_owner": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": True,
                "must_justify": False,
                "strategic_abstention_check": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
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
            "fast_unanimity_is_suspicious": True,
        },
        "stopping": {
            **stop(
                "every_objection_addressed == true AND objections_open == 0 AND "
                "(time_minutes >= 60 OR consent_reached == true)"
            ),
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_minutes": 60,
                "min_independent_positions": 3,
                "every_participant_spoke": False,
                "min_objections_addressed": 1,
            },
            "hard_caps": {
                "max_rounds": 6,
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
                "every deferred comment names its owner and a revisit trigger",
                "the closing note lists each rejected comment with its distinct reason",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 3, "repetition_similarity": 0.9},
            "resolution": [
                "narrow_scope",
                "split_question",
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
                "weak_synthesis",
                "lost_dissent",
                "moderator_capture",
                "silence",
                "premature_convergence",
                "minority_suppression",
                "idea_count_gaming",
            ],
            "fast_unanimity_response": ["forced_dissent", "recruit_independent_critic"],
            "injection_defense": INJECTION_DEFENSE,
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
                "action_plan",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P19 RFC last call",
            "spec_citations": [f"{DESIGN_DOC}:404-419"],
            "notes": (
                "The window (time_minutes >= 60) sits in the OR branch while objections_open == 0 sits in "
                "the AND spine, so window expiry alone can never close the call - the negative snapshot "
                "with an expired window and two open comments proves it evaluates FALSE. Bulk-boilerplate "
                "rejection is caught by custom:distinct_rejection_reasons_ratio (producer "
                "disposition_reason_uniqueness_check), which this unit specifies but does not implement."
            ),
        },
    }


# --------------------------------------------------------------------------- P20


def p20() -> Dict[str, Any]:
    panel = [
        ("delphi-1", "opus-5", "anthropic", ["domain estimation"]),
        ("delphi-2", "gpt-5-codex", "openai", ["reproduction", "measurement"]),
        ("delphi-3", "gemini-3-pro", "google", ["base rates", "statistics"]),
        ("delphi-4", "opus-5", "anthropic", ["failure modes"]),
        ("delphi-5", "gpt-5-codex", "openai", ["operations"]),
    ]
    roster: List[Dict[str, Any]] = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "forecaster",
            "authority": "voter",
            "vote_weight": 1.0,
            "anonymous": True,
            "independence": {
                "sees_peers_before_first_position": False,
                "fresh_context": True,
            },
        }
        for pid, model, vendor, exp in panel
    ]
    roster.append(
        {
            "participant_id": "facilitator",
            "display_name": "Facilitator (returns the anonymised distribution AND the outlier rationales)",
            "model": "opus-5",
            "vendor": "anthropic",
            "expertise": ["delphi facilitation", "anonymisation"],
            "role": "facilitator",
            "authority": "contributor",
            "rights": {"may_speak": True, "may_vote": False},
        }
    )
    return {
        "schema_version": "1.0.0",
        "council_id": "p20-delphi-anonymous-rounds",
        "preset": "forecasting_council",
        "participation": "agent_only",
        "objective": {
            "statement": "Reach a stable panel judgement under strict anonymity, revising against the anonymised distribution plus outlier rationales rather than against status.",
            "charter": "ANONYMOUS family, RAND Delphi. Identities are never revealed. The facilitator returns the distribution AND the outlier RATIONALES - a spread without rationales is regression to the mean, not convergence to truth.",
            "risk_tier": "moderate",
            "desired_output": "forecast",
            "success_criteria": [
                "spread narrows across rounds and each round returns outlier rationales",
                "no participant identity is disclosed at any point",
                "narrowing inside round 1 fires the anti-sycophancy response instead of stopping",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.8,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 120},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": roster,
            "anonymity": {"mode": "double_blind"},
            "replacement": {
                "enabled": True,
                "triggers": ["inactivity", "dominance"],
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
            "min_sources": 2,
            "required_artifacts": ["evidence_pack", "benchmark_baseline"],
        },
        "topology": {"kind": "delphi"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "round-0-independent",
                    "independent": True,
                    "anonymous": True,
                    "rounds": 1,
                },
                {
                    "kind": "delphi_round",
                    "stage_id": "revision-rounds",
                    "rounds": 3,
                    "anonymous": True,
                    "independent": True,
                    "quotas": {
                        "objections_per_participant": 2,
                        "novel_ideas_per_round": 1,
                    },
                    "exit_when": {
                        "all_of": [
                            leaf(
                                "custom:estimate_spread_delta",
                                "<=",
                                0.05,
                                "delphi_spread_tracker",
                                "stability, not agreement, is the Delphi exit; a flat spread across rounds means the protocol is not running",
                            ),
                            leaf(
                                "rounds_elapsed",
                                ">=",
                                2,
                                "",
                                "stability claimed in round 1 is suspicious, not stable",
                            ),
                        ]
                    },
                },
                {
                    "kind": "synthesis",
                    "stage_id": "distribution-report",
                    "rounds": 1,
                    "participants": ["facilitator"],
                },
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 450},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": False,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "standard",
            "experiments": {"allowed": True, "max_experiments": 2, "runner": "ci"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 120,
            "tool_calls": 150,
            "sources": 25,
            "turns": 30,
            "speaking_quota_per_participant": 5,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 1,
        },
        "targets": {
            "objections": 6,
            "evidence_items": 15,
            "novelty_ratio": 0.4,
            "diversity_index": 0.6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "bayesian",
            "quorum": {"min_voters": 5, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
                "calibration_source": "prior council calibration reports",
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.8,
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
            **stop(
                "independent_positions >= 5 AND rounds_elapsed >= 3 AND "
                "(consensus >= 0.8 OR no_new_objection_rounds >= 2)"
            ),
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 5,
                "every_participant_spoke": True,
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
                "irreducible_disagreement",
                "minority_report",
                "dissent",
            ],
            "conditional_decision_requires": [
                "the reported answer is the distribution, with the outlier rationales attached",
                "any round whose spread did not move is flagged as a non-running protocol",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.9,
                "vote_oscillation_rounds": 3,
            },
            "resolution": [
                "forced_dissent",
                "recruit_independent_critic",
                "strongest_counterexample",
                "narrow_scope",
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
                "premature_convergence",
                "sycophancy",
                "echo_chamber",
                "silence",
                "lost_dissent",
                "strategic_voting",
                "participant_dominance",
            ],
            "fast_unanimity_response": [
                "forced_dissent",
                "strongest_counterexample",
                "recruit_independent_critic",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "argument_ledger",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "calibration_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P20 Delphi anonymous rounds",
            "spec_citations": [f"{DESIGN_DOC}:423-438"],
            "notes": (
                "The registry has no spread metric, so the card's real stability criterion is carried by "
                "the stage-level custom:estimate_spread_delta (producer delphi_spread_tracker) while the "
                "top-level rule uses consensus measured as confidence_overlap. The negative snapshot with "
                "consensus 0.95 at round 1 must evaluate FALSE - that is the round-1-narrowing trap the "
                "card names, encoded as an executable control rather than prose."
            ),
        },
    }


# --------------------------------------------------------------------------- P21


def p21() -> Dict[str, Any]:
    panel = [
        ("estimator-1", "opus-5", "anthropic", ["effort estimation", "this codebase"]),
        ("estimator-2", "gpt-5-codex", "openai", ["effort estimation", "test cost"]),
        ("estimator-3", "gemini-3-pro", "google", ["reference classes", "statistics"]),
        ("estimator-4", "opus-5", "anthropic", ["integration cost", "CI"]),
        ("estimator-5", "gpt-5-codex", "openai", ["review and rework cost"]),
    ]
    roster: List[Dict[str, Any]] = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "forecaster",
            "authority": "voter",
            "vote_weight": 1.0,
            "anonymous": True,
            "independence": {"sees_peers_before_first_position": False},
        }
        for pid, model, vendor, exp in panel
    ]
    roster.append(
        {
            "participant_id": "plot-facilitator",
            "display_name": "Facilitator (plots the range without names; restricts discussion to the extremes)",
            "model": "opus-5",
            "vendor": "anthropic",
            "expertise": ["wideband delphi facilitation"],
            "role": "facilitator",
            "authority": "contributor",
            "rights": {"may_speak": True, "may_vote": False},
        }
    )
    return {
        "schema_version": "1.0.0",
        "council_id": "p21-wideband-delphi-estimation",
        "preset": "forecasting_council",
        "participation": "agent_only",
        "objective": {
            "statement": "Produce an effort estimate that is a defensible RANGE, discussing only the assumptions behind the extremes.",
            "charter": "ANONYMOUS family, Boehm wideband Delphi. Anonymous individual estimates, then a nameless range plot, then discussion restricted to the assumptions of the highest and lowest estimate, then re-estimate. Reporting the mean when the honest answer is the range is a failure.",
            "risk_tier": "moderate",
            "desired_output": "forecast",
            "success_criteria": [
                "discussion touched only the extremes' assumptions",
                "the recorded answer is a range, or a point with the range attached",
                "on a task with a known actual, the recorded range contains the actual",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.75,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 75},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "calibration_ranked"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": roster,
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
            "required_artifacts": ["benchmark_baseline", "prior_art_scan"],
        },
        "topology": {"kind": "delphi"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "anonymous-estimates",
                    "independent": True,
                    "anonymous": True,
                    "rounds": 1,
                },
                {
                    "kind": "delphi_round",
                    "stage_id": "range-plot",
                    "rounds": 1,
                    "anonymous": True,
                    "participants": ["plot-facilitator"],
                },
                {
                    "kind": "custom",
                    "custom_name": "extremes_assumptions_only_review",
                    "stage_id": "extremes-review",
                    "rounds": 1,
                    "quotas": {"objections_per_participant": 2},
                    "exit_when": leaf(
                        "custom:non_extreme_discussion_turns",
                        "==",
                        0,
                        "extremes_scope_guard",
                        "only the assumptions behind the highest and lowest estimate are in scope; anything else is out of protocol",
                    ),
                },
                {
                    "kind": "delphi_round",
                    "stage_id": "re-estimate",
                    "rounds": 1,
                    "anonymous": True,
                    "exit_when": leaf(
                        "custom:range_contains_reference_actual",
                        "==",
                        True,
                        "reference_class_backtest",
                        "backtest gate: on a task with a known actual cost, the recorded range must contain it",
                    ),
                },
                {"kind": "synthesis", "stage_id": "range-or-point", "rounds": 1},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 4, "divergence_before_convergence": True},
            "turn": {"max_words": 400},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": False,
                "forced_dissent": False,
            },
            "critique_intensity": "standard",
            "experiments": {"allowed": False, "max_experiments": 0, "runner": "local"},
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 75,
            "tool_calls": 60,
            "sources": 15,
            "turns": 20,
            "speaking_quota_per_participant": 4,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 1,
        },
        "targets": {
            "objections": 4,
            "evidence_items": 10,
            "novelty_ratio": 0.35,
            "diversity_index": 0.5,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": 0, "max": 400},
            "quorum": {"min_voters": 5, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "trimmed_mean",
                "require_confidence_per_vote": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "evidence_outranks_majority": False,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.7,
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
            **stop(
                "rounds_elapsed >= 2 AND (consensus >= 0.7 OR calibration_error <= 0.15 OR rounds_elapsed >= 4)"
            ),
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 5,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
            },
            "hard_caps": {
                "max_rounds": 4,
                "max_minutes": 75,
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
                "the range is reported as the answer, not replaced by its mean",
                "each extreme's load-bearing assumption is written down",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "vote_oscillation_rounds": 2},
            "resolution": [
                "narrow_scope",
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
            "controls": [
                "premature_convergence",
                "echo_chamber",
                "sycophancy",
                "participant_dominance",
                "strategic_voting",
                "weak_synthesis",
            ],
            "fast_unanimity_response": ["forced_dissent", "blind_re_evaluation"],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "calibration_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P21 wideband Delphi estimation",
            "spec_citations": [f"{DESIGN_DOC}:439-454"],
            "notes": (
                "Range-as-outcome is encoded in outcomes.conditional_decision_requires plus "
                "belief_aggregation trimmed_mean; the extremes-only scope restriction that distinguishes "
                "this from plain Delphi is the extremes-review stage exit_when "
                "custom:non_extreme_discussion_turns == 0. rounds_elapsed >= 4 in the OR branch equals "
                "hard_caps.max_rounds so the cap and the rule agree."
            ),
        },
    }


# --------------------------------------------------------------------------- P22


def p22() -> Dict[str, Any]:
    seats = [
        ("sheet-1", "opus-5", "anthropic", ["divergent generation"]),
        ("sheet-2", "gpt-5-codex", "openai", ["mechanism design"]),
        ("sheet-3", "gemini-3-pro", "google", ["analogical transfer"]),
        ("sheet-4", "opus-5", "anthropic", ["constraint relaxation"]),
        ("sheet-5", "gpt-5-codex", "openai", ["adjacent-domain patterns"]),
        ("sheet-6", "gemini-3-pro", "google", ["operational feasibility"]),
    ]
    roster = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "proposer",
            "authority": "contributor",
            "anonymous": True,
            "rights": {"may_speak": True, "may_vote": False},
        }
        for pid, model, vendor, exp in seats
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p22-brainwriting-635",
        "preset": "hundred_idea_brainstorm",
        "participation": "agent_only",
        "objective": {
            "statement": "Generate a large idea set by silent parallel writing where every pass must BUILD ON the neighbour's entry rather than restate it.",
            "charter": "ANONYMOUS family, Rohrbach 6-3-5. Six seats, three ideas each, five passes. No seat ever critiques. A pass that restates its input is not a contribution and is rejected by the overlap detector.",
            "risk_tier": "low",
            "desired_output": "idea_set",
            "success_criteria": [
                "at least 90 unique ideas survive deduplication",
                "every chained entry extends its input instead of restating it",
                "no critique turn occurs during generation",
            ],
            "consensus_intent": "surface_disagreement",
            "confidence_target": 0.6,
            "evidence_requirements": {
                "citation_required": False,
                "anchor_style": "any",
                "min_independent_sources": 0,
                "evidence_outranks_votes": False,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 90},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "model_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 6},
            "roster": roster,
            "anonymity": {"mode": "pseudonymous"},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt"],
                "max_similarity": 0.8,
            },
            "conflicts_policy": {
                "disclosure_required": False,
                "on_conflict": "disclose_only",
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
                    "kind": "brainstorm",
                    "stage_id": "seed-3-each",
                    "rounds": 1,
                    "independent": True,
                    "anonymous": True,
                    "quotas": {"ideas_per_participant": 3, "novel_ideas_per_round": 3},
                },
                {
                    "kind": "custom",
                    "custom_name": "chained_build_on_five_passes",
                    "stage_id": "five-passes",
                    "rounds": 5,
                    "anonymous": True,
                    "quotas": {"ideas_per_participant": 3, "novel_ideas_per_round": 3},
                    "exit_when": {
                        "all_of": [
                            leaf(
                                "custom:max_ngram_overlap_with_prior",
                                "<=",
                                0.4,
                                "build_on_overlap_detector",
                                "a chained entry that overlaps its input above 0.4 is a restatement, not a build-on",
                            ),
                            leaf(
                                "no_new_idea_rounds",
                                "<=",
                                1,
                                "",
                                "generation is still producing",
                            ),
                        ]
                    },
                },
                {
                    "kind": "nominal_group",
                    "stage_id": "dedup-and-cluster",
                    "rounds": 1,
                    "quotas": {"novel_ideas_per_round": 1},
                },
                {"kind": "synthesis", "stage_id": "idea-catalog", "rounds": 1},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 6, "max": 8, "divergence_before_convergence": True},
            "turn": {"max_words": 350},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": False,
                "cross_examination": False,
                "rebuttal_required": False,
                "steelman_before_rebuttal": False,
                "declare_confidence": False,
                "declare_conflicts": False,
                "forced_dissent": False,
            },
            "critique_intensity": "gentle",
            "experiments": {"allowed": False, "max_experiments": 0, "runner": "local"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 90,
            "tool_calls": 40,
            "sources": 5,
            "turns": 40,
            "speaking_quota_per_participant": 8,
            "min_engagement_turns": 6,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 0,
        },
        "targets": {
            "unique_ideas": 90,
            "raw_ideas": 108,
            "categories": 8,
            "novelty_ratio": 0.7,
            "diversity_index": 0.6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "reject",
            },
        },
        "voting": {
            "method": "synthesis_only",
            "quorum": {"min_voters": 6, "on_failure": "extend_rounds"},
            "abstention": {
                "allowed": False,
                "must_justify": False,
                "strategic_abstention_check": False,
            },
            "evidence_gate": {
                "votes_require_evidence": False,
                "evidence_outranks_majority": False,
                "reject_evidence_free_majority": False,
            },
            "tie_break": "no_decision",
        },
        "consensus": {
            "threshold": 0.0,
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
        "stopping": {
            **stop(
                "unique_ideas >= 90 AND novelty_ratio >= 0.7 AND (no_new_idea_rounds >= 2 OR rounds_elapsed >= 6)"
            ),
            "minimum_deliberation": {
                "min_rounds": 6,
                "min_independent_positions": 6,
                "every_participant_spoke": True,
                "min_evidence_items": 0,
            },
            "hard_caps": {
                "max_rounds": 8,
                "max_minutes": 90,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": {
            "allowed": ["decision", "conditional_decision", "no_decision", "dissent"]
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.8},
            "resolution": [
                "rotate_roles",
                "narrow_scope",
                "recruit_independent_critic",
            ],
            "escalation": {"after_attempts": 2, "to": "chair"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "idea_count_gaming",
                "duplicate_novelty",
                "echo_chamber",
                "participant_dominance",
                "silence",
                "premature_convergence",
            ],
            "fast_unanimity_response": ["role_rotation", "forced_dissent"],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "idea_ledger",
                "idea_catalog",
                "option_cards",
                "transcript",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P22 brainwriting 6-3-5",
            "spec_citations": [f"{DESIGN_DOC}:455-470"],
            "notes": (
                "critique_intensity is gentle BY DESIGN - the card says no seat ever critiques - so this is "
                "one of two protocols in the lane where cross_examination, rebuttal and steelman are all "
                "declared FALSE rather than omitted. The build-on rule is carried by must_respond_to_prior "
                "plus the five-passes exit_when custom:max_ngram_overlap_with_prior <= 0.4. The negative "
                "snapshot with 108 unique ideas at novelty_ratio 0.35 must evaluate FALSE: that is "
                "idea-count gaming by trivial variants, executed as a control."
            ),
        },
    }


# --------------------------------------------------------------------------- P23


def p23() -> Dict[str, Any]:
    seats = [
        ("brief-1", "opus-5", "anthropic", ["architecture"]),
        ("brief-2", "gpt-5-codex", "openai", ["implementation"]),
        ("brief-3", "gemini-3-pro", "google", ["measurement", "statistics"]),
        ("brief-4", "opus-5", "anthropic", ["security"]),
        ("brief-5", "gpt-5-codex", "openai", ["operations", "rollback"]),
        ("brief-6", "opus-5", "anthropic", ["owner intent", "scope"]),
    ]
    roster = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "domain_expert",
            "authority": "voter",
            "vote_weight": 1.0,
            "context": {"partition_id": f"isolated-{pid}"},
            "independence": {
                "sees_peers_before_first_position": False,
                "fresh_context": True,
            },
        }
        for pid, model, vendor, exp in seats
    ]
    partitions = [
        {
            "partition_id": f"isolated-{pid}",
            "visible_to": [pid],
            "sources": ["the question", "the shared evidence pack"],
        }
        for pid, _, _, _ in seats
    ]
    return {
        "schema_version": "1.0.0",
        "council_id": "p23-silent-start-pooling",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Preserve independence by having every seat write a full brief with zero sibling visibility, pool them simultaneously, and only then open discussion.",
            "charter": "ANONYMOUS family. The frozen pre-discussion brief set IS the artifact: it is the independence baseline against which the movement caused by discussion is measured. Discussion may not begin until the baseline hashes exist.",
            "risk_tier": "high",
            "desired_output": "recommendation",
            "success_criteria": [
                "baseline hashes exist for all six briefs before any discussion turn is dispatched",
                "no seat read another seat's brief before pooling",
                "the report quantifies how far discussion moved each seat from its baseline",
            ],
            "consensus_intent": "seek_consensus",
            "confidence_target": 0.85,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "file_line",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 150},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 6},
            "roster": roster,
            "anonymity": {"mode": "blind_to_peers", "reveal_after_round": 1},
            "information_partition": {
                "enabled": True,
                "strategy": "staged_release",
                "partitions": partitions,
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt"],
                "max_similarity": 0.85,
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
            "prep_time_minutes": 40,
            "required_artifacts": ["position_memo", "evidence_pack", "risk_list"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "silent-briefs",
                    "independent": True,
                    "rounds": 1,
                    "quotas": {"objections_per_participant": 2},
                },
                {
                    "kind": "custom",
                    "custom_name": "freeze_and_hash_independence_baseline",
                    "stage_id": "freeze-baseline",
                    "rounds": 1,
                    "exit_when": leaf(
                        "custom:baseline_hashes_present",
                        "==",
                        True,
                        "baseline_hash_manifest",
                        "no discussion turn may be dispatched until every brief is hashed and archived",
                    ),
                },
                {
                    "kind": "round_robin",
                    "stage_id": "pooled-discussion",
                    "rounds": 3,
                    "quotas": {
                        "objections_per_participant": 3,
                        "counterexamples_per_round": 1,
                    },
                },
                {
                    "kind": "custom",
                    "custom_name": "measure_movement_against_baseline",
                    "stage_id": "movement-report",
                    "rounds": 1,
                    "exit_when": leaf(
                        "custom:seats_with_measured_movement",
                        ">=",
                        6,
                        "baseline_movement_differ",
                        "the counterfactual is only usable if every seat's drift from its own baseline is measured",
                    ),
                },
                {"kind": "synthesis", "stage_id": "pooled-recommendation", "rounds": 1},
            ],
            "speaking_order": "random",
            "rounds": {"min": 3, "max": 6, "divergence_before_convergence": True},
            "turn": {"max_words": 600},
            "obligations": {
                "must_respond_to_prior": True,
                "must_cite_evidence": True,
                "cross_examination": True,
                "rebuttal_required": True,
                "steelman_before_rebuttal": True,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "adversarial",
            "experiments": {"allowed": True, "max_experiments": 3, "runner": "ci"},
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 150,
            "tool_calls": 180,
            "sources": 30,
            "turns": 36,
            "speaking_quota_per_participant": 6,
            "min_engagement_turns": 3,
            "max_inactivity_rounds": 2,
            "rebuttal_depth": 2,
        },
        "targets": {
            "objections": 8,
            "counterexamples": 3,
            "evidence_items": 20,
            "coverage_score": 0.9,
            "novelty_ratio": 0.5,
            "diversity_index": 0.6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.85,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "supermajority",
            "supermajority_threshold": 0.75,
            "quorum": {"min_voters": 5, "on_failure": "extend_rounds"},
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
            "tie_break": "extend_rounds",
        },
        "consensus": {
            "threshold": 0.75,
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
        "stopping": {
            **stop(
                "independent_positions >= 6 AND all_participants_spoke == true AND "
                "(consensus >= 0.75 OR no_new_objection_rounds >= 2 OR rounds_elapsed >= 5)"
            ),
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 6,
                "every_participant_spoke": True,
                "min_evidence_items": 12,
                "min_objections_addressed": 4,
            },
            "hard_caps": {
                "max_rounds": 6,
                "max_minutes": 150,
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
                "the frozen baseline briefs are archived with their hashes",
                "the movement report names every seat whose position changed and why",
            ],
        },
        "deadlock": {
            "detection": {
                "no_progress_rounds": 2,
                "repetition_similarity": 0.88,
                "circular_citation_check": True,
            },
            "resolution": [
                "blind_re_evaluation",
                "strongest_counterexample",
                "run_experiment",
                "narrow_scope",
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
                "echo_chamber",
                "premature_convergence",
                "sycophancy",
                "participant_dominance",
                "silence",
                "lost_dissent",
                "moderator_capture",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "forced_dissent",
                "strongest_counterexample",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "argument_graph",
                "evidence_map",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P23 silent-start pooling",
            "spec_citations": [f"{DESIGN_DOC}:471-486"],
            "notes": (
                "The card's leak failure mode (briefs escaping via a shared scratch path) is answered by "
                "one information_partition per seat with visible_to = that seat only, plus per-seat "
                "context.partition_id and fresh_context. The independent_positions >= 6 conjunct is what "
                "makes the baseline load-bearing: the negative snapshot with 4 positions must evaluate FALSE."
            ),
        },
    }


# --------------------------------------------------------------------------- P24


def p24() -> Dict[str, Any]:
    seats = [
        ("bts-1", "opus-5", "anthropic", ["domain knowledge"]),
        ("bts-2", "gpt-5-codex", "openai", ["domain knowledge", "reproduction"]),
        ("bts-3", "gemini-3-pro", "google", ["statistics"]),
        ("bts-4", "opus-5", "anthropic", ["adjacent expertise"]),
        ("bts-5", "gpt-5-codex", "openai", ["adjacent expertise"]),
        ("bts-6", "gemini-3-pro", "google", ["general reasoning"]),
        ("bts-7", "opus-5", "anthropic", ["expert minority candidate"]),
    ]
    roster: List[Dict[str, Any]] = [
        {
            "participant_id": pid,
            "model": model,
            "vendor": vendor,
            "expertise": exp,
            "role": "forecaster",
            "authority": "voter",
            "vote_weight": 1.0,
            "anonymous": True,
            "independence": {
                "sees_peers_before_first_position": False,
                "fresh_context": True,
            },
        }
        for pid, model, vendor, exp in seats
    ]
    roster.append(
        {
            "participant_id": "sp-aggregator",
            "display_name": "Aggregator (computes actual support minus predicted support)",
            "model": "opus-5",
            "vendor": "anthropic",
            "expertise": ["surprisingly-popular scoring", "aggregation"],
            "role": "calibrator",
            "authority": "contributor",
            "rights": {"may_speak": True, "may_vote": False},
        }
    )
    return {
        "schema_version": "1.0.0",
        "council_id": "p24-surprisingly-popular-bts",
        "preset": "custom",
        "participation": "agent_only",
        "objective": {
            "statement": "Let a knowledgeable minority win a factual question by scoring answers on actual support minus predicted support, not on raw majority.",
            "charter": "ANONYMOUS family, Prelec surprisingly-popular / Bayesian truth serum. Each seat submits (a) its own answer and (b) its prediction of the panel distribution. The winner is the answer whose actual support most exceeds its predicted support. Mandated dissent is forbidden here because it destroys honest reporting.",
            "risk_tier": "moderate",
            "desired_output": "decision",
            "success_criteria": [
                "every seat submitted both an answer and a panel-distribution prediction",
                "the surprise margin is computed and published per answer",
                "a round whose meta-predictions are uniform across seats is discarded, not aggregated",
            ],
            "consensus_intent": "elicit_distribution",
            "confidence_target": 0.7,
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 1,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 60},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "expertise_ranked", "model_diverse"],
                "explain_choices": True,
            },
            "count": {"mode": "exact", "exact_n": 8, "min": 8, "max": 8},
            "diversity": {
                "min_distinct_vendors": 3,
                "min_distinct_expertise": 5,
                "max_share_per_vendor": 0.6,
            },
            "roster": roster,
            "anonymity": {"mode": "double_blind"},
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "prompt", "model"],
                "max_similarity": 0.8,
            },
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
        },
        "preparation": {
            "research_required": True,
            "independent_prep": True,
            "min_sources": 1,
            "required_artifacts": ["evidence_pack"],
        },
        "topology": {"kind": "flat"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "own-answer",
                    "independent": True,
                    "anonymous": True,
                    "rounds": 1,
                    "quotas": {
                        "ideas_per_participant": 1,
                        "objections_per_participant": 1,
                    },
                },
                {
                    "kind": "custom",
                    "custom_name": "meta_prediction_of_panel_distribution",
                    "stage_id": "meta-prediction",
                    "rounds": 1,
                    "anonymous": True,
                    "quotas": {"objections_per_participant": 1},
                    "exit_when": leaf(
                        "custom:seats_with_meta_prediction",
                        ">=",
                        7,
                        "meta_prediction_collector",
                        "the aggregation key is the meta-prediction; a seat without one cannot be scored",
                    ),
                },
                {
                    "kind": "custom",
                    "custom_name": "surprisingly_popular_aggregation",
                    "stage_id": "sp-aggregation",
                    "rounds": 1,
                    "participants": ["sp-aggregator"],
                    "exit_when": {
                        "all_of": [
                            leaf(
                                "custom:surprise_margin",
                                ">=",
                                0.1,
                                "sp_aggregator",
                                "actual support minus predicted support must be decisive, not noise",
                            ),
                            leaf(
                                "custom:meta_prediction_dispersion",
                                ">=",
                                0.15,
                                "meta_dispersion_detector",
                                "uniform meta-predictions mean the seats did not model the panel; discard the round",
                            ),
                        ]
                    },
                },
                {"kind": "synthesis", "stage_id": "sp-answer", "rounds": 1},
            ],
            "speaking_order": "simultaneous",
            "rounds": {"min": 2, "max": 3, "divergence_before_convergence": True},
            "turn": {"max_words": 400},
            "obligations": {
                "must_respond_to_prior": False,
                "must_cite_evidence": True,
                "cross_examination": False,
                "rebuttal_required": False,
                "steelman_before_rebuttal": False,
                "declare_confidence": True,
                "declare_conflicts": True,
                "forced_dissent": False,
            },
            "critique_intensity": "gentle",
            "experiments": {"allowed": True, "max_experiments": 1, "runner": "sandbox"},
        },
        "budgets": {
            "effort": "medium",
            "time_minutes": 60,
            "tool_calls": 70,
            "sources": 12,
            "turns": 20,
            "speaking_quota_per_participant": 3,
            "min_engagement_turns": 2,
            "max_inactivity_rounds": 1,
            "rebuttal_depth": 0,
        },
        "targets": {
            "objections": 3,
            "evidence_items": 8,
            "novelty_ratio": 0.3,
            "diversity_index": 0.6,
            "dedup": {
                "enabled": True,
                "max_similarity": 0.8,
                "trivial_variant_policy": "merge",
            },
        },
        "voting": {
            "method": "bayesian",
            "quorum": {
                "min_voters": 7,
                "min_fraction": 0.85,
                "on_failure": "no_decision",
            },
            "abstention": {
                "allowed": False,
                "must_justify": True,
                "strategic_abstention_check": True,
            },
            "belief_aggregation": {
                "method": "bayesian_update",
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
            "threshold": 0.5,
            "measure": "vote_share",
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
            **stop(
                "independent_positions >= 7 AND all_participants_spoke == true AND "
                "(confidence >= 0.7 OR rounds_elapsed >= 2)"
            ),
            "minimum_deliberation": {
                "min_rounds": 2,
                "min_independent_positions": 7,
                "every_participant_spoke": True,
                "min_evidence_items": 6,
            },
            "hard_caps": {"max_rounds": 3, "max_minutes": 60, "on_cap": "no_decision"},
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
                "the published answer is the surprisingly-popular one, with its surprise margin",
                "the majority answer is recorded alongside it so the divergence is visible",
            ],
        },
        "deadlock": {
            "detection": {"no_progress_rounds": 1, "vote_oscillation_rounds": 2},
            "resolution": [
                "recruit_independent_critic",
                "blind_re_evaluation",
                "declare_no_decision",
            ],
            "escalation": {"after_attempts": 1, "to": "owner"},
            "owner_intervention": {
                "allowed": True,
                "may_override_vote": False,
                "must_be_logged": True,
            },
        },
        "anti_failure": {
            "controls": [
                "echo_chamber",
                "strategic_voting",
                "sycophancy",
                "silence",
                "evidence_free_majority",
                "collusion",
            ],
            "fast_unanimity_response": [
                "blind_re_evaluation",
                "recruit_independent_critic",
            ],
            "injection_defense": INJECTION_DEFENSE,
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "votes_by_round",
                "confidence_trajectory",
                "dissent_minority_report",
                "unresolved_unknowns",
                "calibration_report",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT,
        },
        "audit": AUDIT_STRICT,
        "metadata": {
            "title": "P24 surprisingly popular / Bayesian truth serum",
            "spec_citations": [f"{DESIGN_DOC}:487-502"],
            "notes": (
                "SUBSTRATE GAP, reported not hidden: the card's stated dependency is "
                "voting.method=surprisingly_popular, and the CouncilSpec voting.method enum has no such "
                "value (17 values, none of them surprisingly_popular). The nearest faithful encoding is "
                "method=bayesian with belief_aggregation=bayesian_update plus a dedicated sp-aggregation "
                "stage whose exit_when carries custom:surprise_margin (producer sp_aggregator). "
                "forced_dissent is FALSE on purpose - the card marks P10 mandated-dissent as incompatible "
                "because it destroys honest meta-reporting. The Philadelphia-capital control the card "
                "requires before adoption needs a live executor: NOT-CHECKED here. Quota semantics here: "
                "ideas_per_participant 1 is one candidate answer per seat, and objections_per_participant 1 "
                "forces each seat to name one reason its OWN answer could be wrong, which is what keeps a "
                "confident majority from arriving unexamined."
            ),
        },
    }


BUILDERS = {
    "P13": p13,
    "P14": p14,
    "P15": p15,
    "P16": p16,
    "P17": p17,
    "P18": p18,
    "P19": p19,
    "P20": p20,
    "P21": p21,
    "P22": p22,
    "P23": p23,
    "P24": p24,
}


# Both-states controls. Every satisfying snapshot must evaluate True and every
# not_satisfying snapshot must evaluate False. The not_satisfying list is a per-conjunct
# mutation battery: one snapshot per load-bearing clause, so a clause that does nothing
# would be caught by its own control passing when it should fail.
EXPECTATIONS: Dict[str, Dict[str, Any]] = {
    "P13": {
        "satisfying": [
            {
                "why": "three questions put, all answered, anchored",
                "metrics": {
                    "objections_addressed": 4,
                    "objections_open": 0,
                    "evidence_items": 7,
                    "unresolved_load_bearing_counterexample": 0,
                    "rounds_elapsed": 4,
                },
            },
            {
                "why": "the examiner found an unanswerable question: a load-bearing counterexample stands",
                "metrics": {
                    "objections_addressed": 3,
                    "objections_open": 2,
                    "evidence_items": 4,
                    "unresolved_load_bearing_counterexample": 1,
                    "rounds_elapsed": 3,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "fewer than three questions put on the claim: depth-first minimum not met",
                "metrics": {
                    "objections_addressed": 2,
                    "objections_open": 1,
                    "evidence_items": 9,
                    "unresolved_load_bearing_counterexample": 0,
                    "rounds_elapsed": 5,
                },
            },
            {
                "why": "questions put but a question is still open and nothing else terminates",
                "metrics": {
                    "objections_addressed": 5,
                    "objections_open": 1,
                    "evidence_items": 9,
                    "unresolved_load_bearing_counterexample": 0,
                    "rounds_elapsed": 3,
                },
            },
            {
                "why": "answered but under-anchored: 4 evidence items is below the floor of 6",
                "metrics": {
                    "objections_addressed": 5,
                    "objections_open": 0,
                    "evidence_items": 4,
                    "unresolved_load_bearing_counterexample": 0,
                    "rounds_elapsed": 3,
                },
            },
        ],
    },
    "P14": {
        "satisfying": [
            {
                "why": "jury spoke, facts anchored, judge reached CONFIRMED",
                "metrics": {
                    "all_participants_spoke": True,
                    "evidence_items": 12,
                    "verdict": "CONFIRMED",
                    "deadlock_detected": False,
                },
            }
        ],
        "not_satisfying": [
            {
                "why": "a juror never spoke: silence must not be read as agreement",
                "metrics": {
                    "all_participants_spoke": False,
                    "evidence_items": 12,
                    "verdict": "CONFIRMED",
                    "deadlock_detected": False,
                },
            },
            {
                "why": "verdict reached on 4 anchored facts, below the floor of 8",
                "metrics": {
                    "all_participants_spoke": True,
                    "evidence_items": 4,
                    "verdict": "CONFIRMED",
                    "deadlock_detected": False,
                },
            },
            {
                "why": "no verdict yet and no deadlock: nothing terminal",
                "metrics": {
                    "all_participants_spoke": True,
                    "evidence_items": 12,
                    "verdict": "NOT_CHECKED",
                    "deadlock_detected": False,
                },
            },
        ],
    },
    "P15": {
        "satisfying": [
            {
                "why": "coverage 0.97, nothing open, 44 anchored items",
                "metrics": {
                    "coverage_score": 0.97,
                    "objections_open": 0,
                    "evidence_items": 44,
                    "evidence_saturation": False,
                },
            },
            {
                "why": "fewer items but evidence saturation reached",
                "metrics": {
                    "coverage_score": 0.96,
                    "objections_open": 0,
                    "evidence_items": 22,
                    "evidence_saturation": True,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "claim coverage 0.80: claims were missed, so a document verdict is unearned",
                "metrics": {
                    "coverage_score": 0.80,
                    "objections_open": 0,
                    "evidence_items": 50,
                    "evidence_saturation": True,
                },
            },
            {
                "why": "three claims still contested",
                "metrics": {
                    "coverage_score": 0.99,
                    "objections_open": 3,
                    "evidence_items": 50,
                    "evidence_saturation": True,
                },
            },
            {
                "why": "thin evidence and no saturation",
                "metrics": {
                    "coverage_score": 0.99,
                    "objections_open": 0,
                    "evidence_items": 10,
                    "evidence_saturation": False,
                },
            },
        ],
    },
    "P16": {
        "satisfying": [
            {
                "why": "all three seats reported and 2 of 3 agree",
                "metrics": {
                    "all_participants_spoke": True,
                    "consensus": 0.67,
                    "rounds_elapsed": 1,
                },
            },
            {
                "why": "no supermajority but the 2-round cap is reached, so the front door returns no_decision",
                "metrics": {
                    "all_participants_spoke": True,
                    "consensus": 0.34,
                    "rounds_elapsed": 2,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "a seat stayed silent: a DISMISS by silence is the card's named failure",
                "metrics": {
                    "all_participants_spoke": False,
                    "consensus": 1.0,
                    "rounds_elapsed": 2,
                },
            },
            {
                "why": "split panel inside the first round",
                "metrics": {
                    "all_participants_spoke": True,
                    "consensus": 0.34,
                    "rounds_elapsed": 1,
                },
            },
        ],
    },
    "P17": {
        "satisfying": [
            {
                "why": "unanimity after the minimum three rounds",
                "metrics": {
                    "rounds_elapsed": 4,
                    "unanimity": True,
                    "deadlock_detected": False,
                },
            },
            {
                "why": "hung at the cap: IRREDUCIBLE_DISAGREEMENT is a legitimate terminal state",
                "metrics": {
                    "rounds_elapsed": 8,
                    "unanimity": False,
                    "deadlock_detected": False,
                },
            },
            {
                "why": "deadlock detected after the minimum rounds",
                "metrics": {
                    "rounds_elapsed": 5,
                    "unanimity": False,
                    "deadlock_detected": True,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "COERCION GUARD: unanimity in round 2 does not stop the jury; suspiciously fast unanimity must be re-tested first",
                "metrics": {
                    "rounds_elapsed": 2,
                    "unanimity": True,
                    "deadlock_detected": False,
                },
            },
            {
                "why": "still deliberating: no unanimity, no deadlock, cap not reached",
                "metrics": {
                    "rounds_elapsed": 5,
                    "unanimity": False,
                    "deadlock_detected": False,
                },
            },
        ],
    },
    "P18": {
        "satisfying": [
            {
                "why": "both keys reported and both AUTHORISE",
                "metrics": {
                    "quorum_met": True,
                    "participants_active": 2,
                    "unanimity": True,
                    "dissent_count": 0,
                },
            },
            {
                "why": "both keys reported and one refused: a refusal is terminal, not a retry",
                "metrics": {
                    "quorum_met": True,
                    "participants_active": 2,
                    "unanimity": False,
                    "dissent_count": 1,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "THE CARD'S REQUIRED BOTH-STATES PROOF: a single AUTHORISE (quorum unmet, one key active) must NOT open the gate",
                "metrics": {
                    "quorum_met": False,
                    "participants_active": 1,
                    "unanimity": True,
                    "dissent_count": 0,
                },
            },
            {
                "why": "second, independent encoding of the same proof: quorum bookkeeping says met but only one key is actually active",
                "metrics": {
                    "quorum_met": True,
                    "participants_active": 1,
                    "unanimity": True,
                    "dissent_count": 0,
                },
            },
            {
                "why": "both keys active but neither a unanimous authorise nor a recorded refusal: still open",
                "metrics": {
                    "quorum_met": True,
                    "participants_active": 2,
                    "unanimity": False,
                    "dissent_count": 0,
                },
            },
        ],
    },
    "P19": {
        "satisfying": [
            {
                "why": "window elapsed and every comment dispositioned",
                "metrics": {
                    "every_objection_addressed": True,
                    "objections_open": 0,
                    "time_minutes": 75,
                    "consent_reached": False,
                },
            },
            {
                "why": "consent reached early with nothing outstanding",
                "metrics": {
                    "every_objection_addressed": True,
                    "objections_open": 0,
                    "time_minutes": 30,
                    "consent_reached": True,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "THE POINT OF THE PROTOCOL: the window expired and consent was declared, but two comments are undispositioned, so the call cannot close",
                "metrics": {
                    "every_objection_addressed": False,
                    "objections_open": 2,
                    "time_minutes": 300,
                    "consent_reached": True,
                },
            },
            {
                "why": "bookkeeping says addressed but one comment is still open: the two must agree",
                "metrics": {
                    "every_objection_addressed": True,
                    "objections_open": 1,
                    "time_minutes": 300,
                    "consent_reached": True,
                },
            },
            {
                "why": "clean but the window has not run and consent is not reached",
                "metrics": {
                    "every_objection_addressed": True,
                    "objections_open": 0,
                    "time_minutes": 10,
                    "consent_reached": False,
                },
            },
        ],
    },
    "P20": {
        "satisfying": [
            {
                "why": "five independent positions, three rounds, distributions overlap at 0.84",
                "metrics": {
                    "independent_positions": 6,
                    "rounds_elapsed": 3,
                    "consensus": 0.84,
                    "no_new_objection_rounds": 1,
                },
            },
            {
                "why": "no convergence but two quiet rounds: stability, which is the Delphi exit",
                "metrics": {
                    "independent_positions": 6,
                    "rounds_elapsed": 4,
                    "consensus": 0.55,
                    "no_new_objection_rounds": 2,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "only three independent positions: the panel is too thin to be a distribution",
                "metrics": {
                    "independent_positions": 3,
                    "rounds_elapsed": 4,
                    "consensus": 0.9,
                    "no_new_objection_rounds": 2,
                },
            },
            {
                "why": "THE CARD'S ROUND-1 TRAP: 0.95 overlap after one round is suspicious, not converged, and must not stop the council",
                "metrics": {
                    "independent_positions": 6,
                    "rounds_elapsed": 1,
                    "consensus": 0.95,
                    "no_new_objection_rounds": 2,
                },
            },
            {
                "why": "three rounds but neither overlap nor stability",
                "metrics": {
                    "independent_positions": 6,
                    "rounds_elapsed": 3,
                    "consensus": 0.5,
                    "no_new_objection_rounds": 0,
                },
            },
        ],
    },
    "P21": {
        "satisfying": [
            {
                "why": "two rounds and the estimates overlap",
                "metrics": {
                    "rounds_elapsed": 2,
                    "consensus": 0.75,
                    "calibration_error": 0.30,
                },
            },
            {
                "why": "no overlap at the 4-round cap: the recorded RANGE is the answer",
                "metrics": {
                    "rounds_elapsed": 4,
                    "consensus": 0.20,
                    "calibration_error": 0.50,
                },
            },
            {
                "why": "well-calibrated panel short of overlap",
                "metrics": {
                    "rounds_elapsed": 3,
                    "consensus": 0.40,
                    "calibration_error": 0.10,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "first-number anchoring guard: a single round cannot settle an estimate however tight it looks",
                "metrics": {
                    "rounds_elapsed": 1,
                    "consensus": 0.95,
                    "calibration_error": 0.05,
                },
            },
            {
                "why": "mid-protocol: no overlap, poor calibration, cap not reached",
                "metrics": {
                    "rounds_elapsed": 3,
                    "consensus": 0.40,
                    "calibration_error": 0.30,
                },
            },
        ],
    },
    "P22": {
        "satisfying": [
            {
                "why": "96 unique ideas at 0.74 novelty with two quiet rounds",
                "metrics": {
                    "unique_ideas": 96,
                    "novelty_ratio": 0.74,
                    "no_new_idea_rounds": 2,
                    "rounds_elapsed": 5,
                },
            },
            {
                "why": "target met at the sixth pass",
                "metrics": {
                    "unique_ideas": 92,
                    "novelty_ratio": 0.71,
                    "no_new_idea_rounds": 0,
                    "rounds_elapsed": 6,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "IDEA-COUNT GAMING CONTROL: 108 entries but novelty 0.35 means trivial variants, so the quota is not met",
                "metrics": {
                    "unique_ideas": 108,
                    "novelty_ratio": 0.35,
                    "no_new_idea_rounds": 3,
                    "rounds_elapsed": 6,
                },
            },
            {
                "why": "40 unique ideas is short of the 90 target however novel they are",
                "metrics": {
                    "unique_ideas": 40,
                    "novelty_ratio": 0.90,
                    "no_new_idea_rounds": 3,
                    "rounds_elapsed": 6,
                },
            },
            {
                "why": "quota and novelty met but generation is still producing and the passes are not done",
                "metrics": {
                    "unique_ideas": 95,
                    "novelty_ratio": 0.80,
                    "no_new_idea_rounds": 0,
                    "rounds_elapsed": 3,
                },
            },
        ],
    },
    "P23": {
        "satisfying": [
            {
                "why": "six frozen baselines, everyone spoke, 0.80 agreement",
                "metrics": {
                    "independent_positions": 6,
                    "all_participants_spoke": True,
                    "consensus": 0.80,
                    "no_new_objection_rounds": 0,
                    "rounds_elapsed": 3,
                },
            },
            {
                "why": "no supermajority but discussion has gone quiet",
                "metrics": {
                    "independent_positions": 6,
                    "all_participants_spoke": True,
                    "consensus": 0.60,
                    "no_new_objection_rounds": 2,
                    "rounds_elapsed": 4,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "INDEPENDENCE BASELINE INCOMPLETE: only four seats filed a brief before pooling, so the counterfactual does not exist",
                "metrics": {
                    "independent_positions": 4,
                    "all_participants_spoke": True,
                    "consensus": 0.90,
                    "no_new_objection_rounds": 2,
                    "rounds_elapsed": 4,
                },
            },
            {
                "why": "a seat never spoke in the pooled discussion",
                "metrics": {
                    "independent_positions": 6,
                    "all_participants_spoke": False,
                    "consensus": 0.90,
                    "no_new_objection_rounds": 2,
                    "rounds_elapsed": 4,
                },
            },
            {
                "why": "live disagreement, still moving, cap not reached",
                "metrics": {
                    "independent_positions": 6,
                    "all_participants_spoke": True,
                    "consensus": 0.40,
                    "no_new_objection_rounds": 1,
                    "rounds_elapsed": 3,
                },
            },
        ],
    },
    "P24": {
        "satisfying": [
            {
                "why": "seven independent answers, everyone reported, confident aggregate",
                "metrics": {
                    "independent_positions": 7,
                    "all_participants_spoke": True,
                    "confidence": 0.75,
                    "rounds_elapsed": 1,
                },
            },
            {
                "why": "low confidence but both rounds are done, so the SP answer is published with its margin",
                "metrics": {
                    "independent_positions": 8,
                    "all_participants_spoke": True,
                    "confidence": 0.40,
                    "rounds_elapsed": 2,
                },
            },
        ],
        "not_satisfying": [
            {
                "why": "five answers: below the 7-seat floor the card sets for surprisingly-popular to have any power",
                "metrics": {
                    "independent_positions": 5,
                    "all_participants_spoke": True,
                    "confidence": 0.90,
                    "rounds_elapsed": 2,
                },
            },
            {
                "why": "a seat did not submit, so its meta-prediction is missing and the aggregation key is incomplete",
                "metrics": {
                    "independent_positions": 7,
                    "all_participants_spoke": False,
                    "confidence": 0.90,
                    "rounds_elapsed": 2,
                },
            },
            {
                "why": "first round only and low confidence",
                "metrics": {
                    "independent_positions": 7,
                    "all_participants_spoke": True,
                    "confidence": 0.40,
                    "rounds_elapsed": 1,
                },
            },
        ],
    },
}


def slug(pid: str, spec: Dict[str, Any]) -> str:
    name = spec["council_id"].split("-", 1)[1]
    return f"{pid}-{name}.councilspec.json"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for pid, builder in BUILDERS.items():
        spec = builder()
        path = OUT_DIR / slug(pid, spec)
        path.write_text(
            json.dumps(spec, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest.append(
            {"id": pid, "council_id": spec["council_id"], "file": path.name}
        )
        print(f"wrote {path.name}  ({path.stat().st_size} bytes)")

    exp_path = OUT_DIR / "PROTOCOL-EXPECTATIONS.json"
    exp_path.write_text(
        json.dumps(
            {
                "purpose": (
                    "Both-states controls for every protocol stopping expression. Each satisfying "
                    "snapshot MUST evaluate True and each not_satisfying snapshot MUST evaluate False; "
                    "the not_satisfying list is a per-conjunct mutation battery, so a decorative clause "
                    "would be exposed by its own control refusing to fail."
                ),
                "mandated_controls": sorted(MANDATED_CONTROLS),
                "manifest": manifest,
                "expectations": EXPECTATIONS,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {exp_path.name}  ({exp_path.stat().st_size} bytes)")
    print(f"SUCCESS:build-protocols {len(manifest)} protocol instances emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
