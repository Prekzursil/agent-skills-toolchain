#!/usr/bin/env python3
"""Canonical CNL-0115 preset body (typed delta, not a fork)."""
from __future__ import annotations

PRESET: dict = {
    "id": "council.preset.standing-watch.trigger-woken",
    "title": "Standing watch council: long-running, trigger-woken, low-intensity",
    "family": "STANDING-WATCH",
    "anonymity": False,
    "rebuttal": False,
    "extends": [
        {
            "id": "P51",
            "kind": "protocol",
            "relation": "extends",
            "note": (
                "Catalog-cited timeboxed-spike-council (CNL-0045). Same "
                "low-intensity short panel (max_rounds=2, majority). This "
                "preset does not clock-start or forget: it sleeps, wakes on "
                "a named trigger, and blocks re-litigation via a settled ledger."
            ),
        },
        {
            "id": "C-cited:P51-timeboxed-spike-council",
            "kind": "preset",
            "relation": "extends",
        },
        {
            "id": "CNL-0011",
            "kind": "mechanism",
            "relation": "binds",
            "note": (
                "Replay seeds are populated only for a wake session. Sleep "
                "state is not a paused-transcript freeze."
            ),
        },
        {
            "id": "CNL-0075",
            "kind": "mechanism",
            "relation": "realizes",
            "note": (
                "Each new settled row carries a lineage_root from idea to "
                "decision so a later wake can exhibit the prior chain."
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
        {
            "id": "WatchClerk",
            "title": "Watch clerk",
            "voting": False,
            "seated_when": "always",
            "note": "Classifies incoming events. ACK-UNCHANGED is not a vote.",
        },
        {
            "id": "Archivist",
            "title": "Archivist",
            "voting": False,
            "seated_when": "always",
            "note": "Serialises sleep_state (ledger + bindings). Does not carry transcripts.",
        },
        {
            "id": "DutySentinel",
            "title": "Duty sentinel",
            "voting": False,
            "bind_triggers": True,
            "seated_when": "always",
            "note": "Owns trigger bindings declared before sleep. Mid-sleep bindings cannot be added to manufacture a wake.",
        },
        {
            "id": "Chair",
            "title": "Chair",
            "voting": True,
            "seated_when": "wake",
        },
        {
            "id": "Skeptic",
            "title": "Skeptic",
            "voting": True,
            "seated_when": "wake",
        },
        {
            "id": "Pragmatist",
            "title": "Pragmatist",
            "voting": True,
            "seated_when": "wake",
        },
    ],
    "protocol_schedule": [
        {
            "id": "classify-trigger",
            "purpose": "WatchClerk classifies clock vs trigger vs reopen vs re-ask",
        },
        {
            "id": "fingerprint-question",
            "purpose": "hash question_id + material inputs; drop wall-clock and cosmetics",
        },
        {
            "id": "settled-lookup",
            "purpose": "ACK-UNCHANGED on fingerprint match; else wake with prior as exhibit",
        },
        {
            "id": "wake-deliberate",
            "purpose": "low-intensity panel seated only on wake; max_rounds=2",
            "optional": True,
        },
        {
            "id": "lineage-bind",
            "purpose": "bind CNL-0075 lineage_root onto the new settled row",
            "optional": True,
        },
        {
            "id": "record-ledger",
            "purpose": "one live decision per question_id; replace row, do not fork",
        },
        {
            "id": "return-to-sleep",
            "purpose": "unseat voting roles; persist sleep_state; clear replay_seeds",
        },
    ],
    "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": (
            "Same majority rule as P51. Quorum applies only on wake. "
            "ACK-UNCHANGED is a clerk classification, not a ballot."
        ),
    },
    "stopping": {
        "max_rounds": 2,
        "expression": (
            "no_trigger→SLEEP || stale_fp→ACK-UNCHANGED || "
            "wake_rounds<=2 && unresolved→BLOCKED-OPEN"
        ),
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN",
    },
    "watch": {
        "kind": "standing-watch",
        "trigger_woken": True,
        "sleep_default": True,
        "settled_ledger_blocks_relitigation": True,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": True,
        "fingerprint_excludes_wall_clock": True,
        "reopen_requires_token_and_new_evidence": True,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": True,
    },
    "default_binding": {
        "base_spec_ref": "CouncilSpec.v2",
        "base_spec_version": "catalog-cited-absent-on-this-worktree",
        "protocol": "P51",
    },
    "editable_dials": [
        "stopping.max_rounds",
        "voting.quorum",
        "watch.bindings",
    ],
    "locked_dials": [
        "watch.trigger_woken",
        "watch.sleep_default",
        "watch.settled_ledger_blocks_relitigation",
        "watch.clock_tick_is_not_a_trigger",
        "watch.fingerprint_excludes_wall_clock",
        "watch.reopen_requires_token_and_new_evidence",
        "voting.rule",
    ],
    "anti_failure": {
        "on_split": "surface-disagreement",
        "no_silent_average": True,
        "name_only_duplicate_forbidden": True,
        "no_relitigation_on_stale_fingerprint": True,
    },
    "audit": {
        "persist_sleep_state": True,
        "hash_material_inputs": True,
        "record_ack_separately_from_decision": True,
    },
}
