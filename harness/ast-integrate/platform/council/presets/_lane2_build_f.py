"""Lane-2 preset builder, batch F: the one spec-required archetype this lane
gap-fills after measuring what the other lanes actually shipped.

WHY THIS FILE EXISTS. The lane's first gap-fill attempt was
general_purpose_auto_composed. Measuring the directory (see
_lane2_probe_controls.py) showed a sibling lane had ALREADY shipped it as
c-g73-general-purpose-auto-composed, so that file was deleted rather than left as
a second, divergent implementation of the same archetype. The same measurement
showed three required archetypes that NO file in the directory carried:
roadmap_prioritization, stakeholder_user_panel, standing_watch_council.

Only ONE of the three is honestly buildable from lane 2's slice.
stakeholder_user_panel is adjacent to C-S28 stakeholder-negotiation-5 (design
index 28, this lane) but is a DIFFERENT council: a user panel REPORTS
experience, it does not bargain over an allocation. Relabelling C-S28 to cover
it would have been label-stuffing - one card cannot honestly be two presets - so
this is authored as its own instance.

roadmap_prioritization and standing_watch_council are NOT built here: neither has
a design card in indices 17-32 and inventing one would be a design decision, not
an implementation. They are reported as unassigned in LANE-2-STATUS.json with a
recommended carrier each.
"""

from __future__ import annotations

from typing import Any, Dict

from _lane2_build_a import FULL_OUTCOMES_MR
from _lane2_build_b import _agent
from _lane2_common import (
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
    audit,
    injection_defense,
    notes,
    outcomes,
)


def g_stakeholder_user_panel() -> Dict[str, Any]:
    users = [
        (
            "user-daily",
            "Daily driver (uses it every session)",
            "opus-5",
            "anthropic",
            "everyday workflow",
        ),
        (
            "user-new",
            "New user (first week)",
            "gpt-5-codex",
            "openai",
            "onboarding friction",
        ),
        (
            "user-power",
            "Power user (edge cases and scale)",
            "gemini-3-pro",
            "google",
            "scale and edge cases",
        ),
        (
            "user-recovering",
            "Recovering user (hit a failure and worked around it)",
            "opus-5",
            "anthropic",
            "failure recovery and workarounds",
        ),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "council_id": "g-up01-stakeholder-user-panel",
        "preset": "stakeholder_user_panel",
        "participation": "hybrid",
        "objective": {
            "statement": "Elicit what the people who actually use the thing experience, as evidence, "
            "before any decision is taken about changing it.",
            "charter": "Stakeholder / user panel. This council does NOT decide and does NOT bargain - "
            "it REPORTS. Each seat speaks from one usage position and must cite a concrete episode, "
            "not a preference. A panel that produces a decision has overwritten the evidence it was "
            "convened to gather.",
            "risk_tier": "moderate",
            "desired_output": "review_verdict",
            "success_criteria": [
                "every seat cited at least two concrete episodes, with when and what happened",
                "no seat argued for a solution; each described experience",
                "disagreement between usage positions is preserved, not averaged away",
            ],
            "consensus_intent": "elicit_distribution",
            "evidence_requirements": {
                "citation_required": True,
                "anchor_style": "any",
                "min_independent_sources": 2,
                "evidence_outranks_votes": True,
            },
            "owner_constraints": {"approval_required": False, "deadline_minutes": 45},
        },
        "participants": {
            "selection": {
                "mode": "exact",
                "strategies": ["exact", "stakeholder_balanced", "model_diverse"],
                "explain_choices": True,
                "owner_override_allowed": True,
            },
            "count": {"mode": "exact", "exact_n": 6, "min": 6, "max": 6},
            "diversity": {"min_distinct_vendors": 3, "min_distinct_expertise": 5},
            "roster": [
                _agent(
                    u[0],
                    u[1],
                    "user_advocate",
                    u[2],
                    u[3],
                    authority="contributor",
                    effort="high",
                    expertise=[u[4]],
                    rights={"may_speak": True, "may_vote": True},
                    independence={
                        "fresh_context": True,
                        "sees_peers_before_first_position": False,
                    },
                )
                for u in users
            ]
            + [
                _agent(
                    "facilitator",
                    "Facilitator (asks, never advocates)",
                    "facilitator",
                    "opus-5",
                    "anthropic",
                    authority="chair",
                    effort="high",
                    rights={"may_speak": True, "may_vote": False},
                ),
                {
                    "participant_id": "owner-observer",
                    "display_name": "Owner (observes, does not steer the panel)",
                    "kind": "human",
                    "vendor": "human",
                    "role": "observer",
                    "authority": "observer",
                    "expertise": ["owner intent"],
                    "rights": {"may_speak": False, "may_vote": False},
                },
            ],
            "anonymity": {"mode": "pseudonymous", "reveal_after_round": 2},
            "conflicts_policy": {
                "disclosure_required": True,
                "on_conflict": "disclose_only",
            },
            "duplicate_detection": {
                "enabled": True,
                "dimensions": ["position_similarity", "expertise"],
                "max_similarity": 0.75,
            },
        },
        "preparation": {
            "research_required": False,
            "independent_prep": True,
            "required_artifacts": ["position_memo"],
        },
        # NOTE: "fishbowl" is a legal protocol STAGE kind but NOT a topology kind
        # (measured: the topology enum has no fishbowl). The fishbowl is expressed
        # as the panel-discussion stage below; the topology is facilitator-led.
        "topology": {"kind": "chair_led", "chair": "facilitator"},
        "protocol": {
            "sequence": [
                {
                    "kind": "blind_independent_first_pass",
                    "stage_id": "episodes",
                    "independent": True,
                    "anonymous": True,
                    "quotas": {"ideas_per_participant": 2},
                    "exit_when": {
                        "all_of": [
                            {
                                "metric": "independent_positions",
                                "op": ">=",
                                "value": 4,
                                "note": "one independent account per user seat, gathered before any seat "
                                "hears another - a panel that talks first converges on the "
                                "loudest episode",
                            },
                            {
                                "metric": "evidence_items",
                                "op": ">=",
                                "value": 8,
                                "note": "two concrete episodes per user seat",
                            },
                        ]
                    },
                },
                {"kind": "fishbowl", "stage_id": "panel-discussion", "rounds": 2},
                {
                    "kind": "custom",
                    "stage_id": "divergence-map",
                    "custom_name": "map where the usage positions DISAGREE and keep both accounts",
                    "participants": ["facilitator"],
                },
                {"kind": "synthesis", "stage_id": "experience-report"},
            ],
            "speaking_order": "round_robin",
            "rounds": {"min": 3, "max": 5, "divergence_before_convergence": True},
            "turn": {"max_words": 500},
            "obligations": {
                "must_cite_evidence": True,
                "must_respond_to_prior": False,
                "declare_confidence": True,
                "declare_conflicts": True,
            },
            "critique_intensity": "gentle",
        },
        "budgets": {
            "effort": "high",
            "time_minutes": 45,
            "tool_calls": 60,
            "turns": 30,
            "speaking_quota_per_participant": 5,
            "max_inactivity_rounds": 2,
        },
        "targets": {
            "evidence_items": 12,
            "coverage_score": 0.85,
            "diversity_index": 0.6,
        },
        "voting": {
            "method": "score",
            "score_scale": {"min": 1, "max": 5},
            "quorum": {"min_voters": 3, "on_failure": "extend_rounds"},
            "belief_aggregation": {
                "method": "median",
                "require_confidence_per_vote": True,
            },
            "abstention": {
                "allowed": True,
                "counts_toward_quorum": False,
                "must_justify": True,
            },
            "evidence_gate": {
                "votes_require_evidence": True,
                "reject_evidence_free_majority": True,
            },
            "tie_break": "no_decision",
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
            "source_expression": "independent_positions >= 4 AND evidence_items >= 12 AND "
            "all_participants_spoke == true",
            "expression": {
                "all_of": [
                    {"metric": "independent_positions", "op": ">=", "value": 4},
                    {"metric": "evidence_items", "op": ">=", "value": 12},
                    {"metric": "all_participants_spoke", "op": "==", "value": True},
                ]
            },
            "minimum_deliberation": {
                "min_rounds": 3,
                "min_independent_positions": 4,
                "min_evidence_items": 12,
                "every_participant_spoke": True,
            },
            "hard_caps": {
                "max_rounds": 5,
                "max_minutes": 45,
                "on_cap": "synthesize_best_effort",
            },
        },
        "outcomes": outcomes(
            FULL_OUTCOMES_MR,
            ["the report names which usage position each finding came from"],
        ),
        "deadlock": {
            "detection": {"no_progress_rounds": 2, "repetition_similarity": 0.85},
            "resolution": [
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
            "controls": [
                "participant_dominance",
                "echo_chamber",
                "premature_convergence",
                "instant_unanimity",
                "lost_dissent",
                "minority_suppression",
                "moderator_capture",
                "prompt_injection",
            ],
            "fast_unanimity_response": ["blind_re_evaluation", "forced_dissent"],
            "injection_defense": injection_defense(),
        },
        "outputs": {
            "required": [
                "independent_opening_positions",
                "transcript",
                "evidence_map",
                "dissent_minority_report",
                "unresolved_unknowns",
                "final_recommendation",
                "decision_lineage",
            ],
            "receipt_schema": RECEIPT_SCHEMA,
        },
        "audit": audit(
            retain_days=180, owner_approval_for=[], forbid_irreversible=True
        ),
        "metadata": {
            "title": "Stakeholder / user experience panel (4 users + facilitator + owner observer)",
            "owner": "Prekzursil",
            "lineage": [
                "spec REQUIRED preset: stakeholder/user panel",
                "adjacent card C-S28 stakeholder-negotiation-5 (a DIFFERENT council)",
                "P03 fishbowl",
                "P23 silent-start-pooling",
            ],
            "spec_citations": ["_USER-PROMPTS.md:10473-11437"],
            "notes": notes(
                card="(no design card in indices 17-32; authored from the spec's required-preset list)",
                seats_declared=0,
                roles_line="user_advocate_x4,facilitator,owner_observer",
                preset_label_rationale="stakeholder_user_panel - a spec-REQUIRED archetype that a "
                "directory-wide measurement showed no file carried.",
                dials={
                    "$.participants.roster (the four user seats)": "WHICH usage positions are at the "
                    "table. The four here (daily, new, power, recovering) are chosen to disagree; "
                    "four seats that use the thing the same way produce one account, not four",
                    "$.participants.anonymity.reveal_after_round": "pseudonymity protects a negative "
                    "account from being softened; unmask later, not never",
                    "$.voting.method + $.score_scale": "score with a median aggregate. The panel "
                    "rates experience; it does not elect an option",
                    "$.protocol.critique_intensity": "gentle on purpose - adversarial pressure on a "
                    "user account suppresses the accounts you most need",
                },
                outcome_lineage=FULL_OUTCOMES_MR,
                extra="LANE-2 GAP FILL, NOT A LANE-2 SLICE MEMBER, and NOT a relabel of C-S28. "
                "C-S28 stakeholder-negotiation-5 in this same lane bargains over an ALLOCATION with "
                "BATNAs and concessions; this council gathers EVIDENCE about experience and is "
                "forbidden from deciding (tie_break=no_decision, owner may not steer, "
                "may_speak=false on the owner seat). "
                "IF ANOTHER LANE ALSO BUILT stakeholder_user_panel, DEDUPE - this file is namespaced "
                "g-up01-* rather than c-* precisely so the duplicate is trivially detectable. "
                "This lane's FIRST gap-fill attempt (general_purpose_auto_composed, g00-*) was "
                "deleted for exactly that reason once c-g73-* was measured in the directory.",
            ),
        },
    }
