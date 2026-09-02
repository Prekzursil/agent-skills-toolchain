#!/usr/bin/env python3
"""Canonical CNL-0110 requirements-council preset (typed delta)."""
from __future__ import annotations

PRESET_ID = "council.preset.requirements.elicit-then-reconcile"

REQUIRED_CLASSES = (
    "operator",
    "owner",
    "implementer",
    "affected-party",
    "constraint-bearer",
)

PROFILE_AXES = (
    "role_set",
    "protocol_schedule",
    "elicit_voting_rule",
    "reconcile_voting_rule",
    "elicit_stop",
    "reconcile_stop",
    "phase_split",
    "unreconcilable_outcome",
    "balance_metric",
)


def preset() -> dict:
    return {
        "id": PRESET_ID,
        "kind": "council_preset",
        "title": "Requirements council: elicit wants, then reconcile contradictions",
        "extends_c_ids": ["C13", "C14"],
        "extends_c_ids_basis": (
            "WORK-UNIT-CATALOG CNL-0110 plus CNL-0102 named family presets: "
            "C13 requirements-elicitation (P23/P01/P22, approval) and C14 "
            "requirements-conflict-reconciliation (P12/P09/P56, consent). This "
            "preset composes the two arms into one two-phase schedule with "
            "phase-local voting. Library bytes were not read."
        ),
        "base_spec": {
            "id": "councilspec.v2",
            "version_pin": "unpinned-library-absent",
            "note": (
                "CNL-0101 artifact and 11-COUNCIL-SPECIFICATION.schema.json are "
                "absent on this worktree. This preset is a typed delta over the "
                "axes catalog-cited for every 12-COUNCIL record "
                "(anti_failure/audit/voting/consensus/stopping) plus roles and "
                "a two-step protocol_schedule. It is not a fork of a copied spec."
            ),
        },
        "delta": {
            "roles": list(REQUIRED_CLASSES),
            "protocol_schedule": ["p-elicit", "p-reconcile"],
            "phases": {
                "elicit": {
                    "id": "p-elicit",
                    "purpose": "surface attributed wants; do not aggregate them",
                    "aggregates_wants": False,
                },
                "reconcile": {
                    "id": "p-reconcile",
                    "purpose": "classify each contradicting pair; never blend",
                    "information_gain_gate": True,
                },
            },
            "voting": {
                "elicit": {
                    "rule": "record-only",
                    "quorum": 0,
                    "note": "elicitation has no vote; a vote here would smuggle reconciliation into capture",
                },
                "reconcile": {
                    "rule": "pairwise-originator-conjunction",
                    "quorum": 2,
                    "note": (
                        "a rewrite of pair (A,B) is accepted only if both originating "
                        "stakeholder classes accept it. Majority and ranked-choice are "
                        "refused: wants are not mutually exclusive options (CNL-0109 trap)."
                    ),
                },
            },
            "stopping": {
                "elicit": {
                    "max_rounds": 2,
                    "done_when": "each required class has >=1 attributed want",
                    "on_timeout": "halt-incomplete-ledger",
                },
                "reconcile": {
                    "max_rounds": 3,
                    "done_when": "each contradicting pair is reconciled|deferred-conditional|irreducible-disagreement",
                    "on_timeout": "halt-unclassified-pairs-are-not-irreducible",
                    "irreducible_requires_zero_information_gain": True,
                },
            },
            "anti_failure": {
                "on_split": "surface-disagreement",
                "no_silent_average": True,
                "no_blend_of_contradicting_wants": True,
                "underfilled_class_blocks_elicit": True,
            },
            "audit": {
                "persist_transcript": True,
                "hash_inputs": True,
                "want_ledger_append_only": True,
                "pair_outcomes_must_cite_attempts": True,
            },
            "consensus": {
                "reducer": "pairwise-originator-conjunction",
                "local_completion_forbidden": True,
            },
            "outcomes": {
                "unreconcilable_pair": "irreducible-disagreement",
                "reconciled_pair": "decision",
                "untried_pair": "incomplete",
                "council_compound": (
                    "decision-or-conditional-decision over reconciled pairs, "
                    "plus irreducible-disagreement annex for unreconcilable pairs"
                ),
            },
            "balance_metric": {
                "id": "required-class-coverage",
                "required_classes": list(REQUIRED_CLASSES),
                "pass_when": "min(count per required class) >= 1",
                "fail_when": "any required class has count == 0",
                "threshold_declared_before_score": True,
                "note": (
                    "Shannon-style diversity is refused: it can pass with one "
                    "token member of a class. Coverage of each required class "
                    "is the dispute-resistant metric used here (operationalizes "
                    "CNL-0017; CNL-0017 artifact is absent)."
                ),
            },
        },
        "editable_dials": [
            "stopping.elicit.max_rounds",
            "stopping.reconcile.max_rounds",
            "delta.roles",
        ],
        "default_binding": {
            "stopping.elicit.max_rounds": 2,
            "stopping.reconcile.max_rounds": 3,
            "delta.roles": list(REQUIRED_CLASSES),
        },
        "on_base_version_bump": (
            "migrate every bound dial or list the dials that cannot migrate; "
            "silent override of a non-editable dial is REJECTED (CNL-0101 test)."
        ),
    }


def fingerprint(p: dict | None = None) -> dict:
    p = p or preset()
    d = p["delta"]
    return {
        "role_set": tuple(sorted(d["roles"])),
        "protocol_schedule": tuple(d["protocol_schedule"]),
        "elicit_voting_rule": d["voting"]["elicit"]["rule"],
        "reconcile_voting_rule": d["voting"]["reconcile"]["rule"],
        "elicit_stop": d["stopping"]["elicit"]["done_when"],
        "reconcile_stop": d["stopping"]["reconcile"]["done_when"],
        "phase_split": set(d["protocol_schedule"]) >= {"p-elicit", "p-reconcile"},
        "unreconcilable_outcome": d["outcomes"]["unreconcilable_pair"],
        "balance_metric": d["balance_metric"]["id"],
    }


def distance(a: dict, b: dict) -> tuple[int, list[str]]:
    differ: list[str] = []
    for axis in PROFILE_AXES:
        if a.get(axis) != b.get(axis):
            differ.append(axis)
    return len(differ), differ
