#!/usr/bin/env python3
"""Canonical CNL-0106 preset body (typed delta, not a fork)."""
from __future__ import annotations

PRESET: dict = {
    "id": "council.preset.code-review-tribunal.executable-oracle",
    "title": "Code-review tribunal backed by an executable oracle",
    "family": "ENGINEERING-REVIEW",
    "anonymity": False,
    "rebuttal": False,
    "extends": [
        {
            "id": "P46",
            "kind": "protocol",
            "relation": "extends",
            "note": (
                "Catalog-cited architecture-review-board (CNL-0045). Same four "
                "review voices and majority vote; this preset adds a bound "
                "executable oracle as a gate after the vote."
            ),
        },
        {
            "id": "C-cited:P46-architecture-review-board",
            "kind": "preset",
            "relation": "extends",
        },
        {
            "id": "CNL-0068",
            "kind": "mechanism",
            "relation": "realizes",
            "note": (
                "Evidence outranks popularity: one bound failing test "
                "overturns a unanimous YES. Converse: an unbound failing "
                "test cannot veto."
            ),
        },
        {
            "id": "council.preset.catalog-class.editable",
            "kind": "catalog-class",
            "relation": "extends",
            "note": "ARC-0003 transcribed catalog-class.editable four-voice base.",
        },
    ],
    "roles": [
        {"id": "Architect", "title": "Architect", "voting": True},
        {"id": "Skeptic", "title": "Skeptic", "voting": True},
        {"id": "Pragmatist", "title": "Pragmatist", "voting": True},
        {"id": "Critic", "title": "Critic", "voting": True},
        {
            "id": "TestBinder",
            "title": "Test binder",
            "voting": False,
            "bind_oracle": True,
            "seated_when": "always",
            "note": (
                "Declares load-bearing commands BEFORE round 1. Reviewers "
                "cannot add bindings mid-flight to manufacture a veto."
            ),
        },
        {
            "id": "EvidenceClerk",
            "title": "Evidence clerk",
            "voting": False,
            "seated_when": "oracle-challenge",
            "note": "Seated only when the disputed artifact is the test.",
        },
    ],
    "protocol_schedule": [
        {
            "id": "bind-oracle",
            "purpose": "TestBinder records load-bearing commands before talk",
        },
        {
            "id": "P46",
            "purpose": "architecture/code review board; majority vote is an exhibit",
        },
        {
            "id": "oracle-gate",
            "purpose": "bound FAIL overrides majority; unbound FAIL is void",
        },
        {
            "id": "P50",
            "purpose": "evidence-clerk path when subject_kind=test or challenge filed",
            "optional": True,
        },
    ],
    "voting": {
        "rule": "majority",
        "quorum": 3,
        "on_tie": "NOT-YES",
        "note": (
            "Same majority rule as P46. The oracle is not a fifth vote; it is "
            "a gate on the recorded outcome."
        ),
    },
    "stopping": {
        "max_rounds": 6,
        "expression": (
            "bound_oracle_fail→NOT-YES || max_rounds<=6 && unresolved→BLOCKED"
        ),
        "on_timeout": "halt",
        "on_oracle_fail": "NOT-YES",
        "on_unresolved": "BLOCKED",
    },
    "oracle": {
        "kind": "executable-command",
        "fail_overrides_majority": True,
        "unbound_fail_cannot_veto": True,
        "disputed_test_demotes_oracle_to_exhibit": True,
        "binder_role": "TestBinder",
        "load_bearing_declared_before_deliberation": True,
        "inconclusive_blocks_yes": True,
    },
    "default_binding": {
        "base_spec_ref": "CouncilSpec.v2",
        "base_spec_version": "catalog-cited-absent-on-this-worktree",
        "protocol": "P46",
    },
    "editable_dials": [
        "stopping.max_rounds",
        "voting.quorum",
        "oracle_binding.load_bearing_commands",
    ],
    "locked_dials": [
        "oracle.fail_overrides_majority",
        "oracle.unbound_fail_cannot_veto",
        "oracle.disputed_test_demotes_oracle_to_exhibit",
        "oracle.load_bearing_declared_before_deliberation",
        "voting.rule",
    ],
    "anti_failure": {
        "on_split": "surface-disagreement",
        "no_silent_average": True,
        "name_only_duplicate_forbidden": True,
    },
    "audit": {
        "persist_transcript": True,
        "hash_inputs": True,
        "record_vote_separately_from_outcome": True,
    },
}
