#!/usr/bin/env python3
"""Fixture ledger + events for CNL-0115 standing-watch probes."""
from __future__ import annotations

from engine import material_digest, question_fingerprint

QUESTION = "Q-shipping-window"
POLICY_V1 = "sha256:policy-v1-keep-weekday-window"
POLICY_V2 = "sha256:policy-v2-allow-saturday"
CONSTRAINT = "no-weekend-ship"

MATERIAL_V1 = {
    "policy_sha256": POLICY_V1,
    "constraint": CONSTRAINT,
    "sla_class": "standard",
}
MATERIAL_V2 = {
    "policy_sha256": POLICY_V2,
    "constraint": "saturday-ok",
    "sla_class": "standard",
}


def settled_ledger() -> dict:
    fp = question_fingerprint(QUESTION, MATERIAL_V1)
    return {
        "watch_id": "watch.shipping-window",
        "bindings": [
            {
                "source_id": "src-shipping-policy",
                "predicate": "content-hash-change",
                "last_digest": material_digest(MATERIAL_V1),
            }
        ],
        "settled": [
            {
                "question_id": QUESTION,
                "question_fingerprint": fp,
                "decision_id": "D-2026-07-13-shipping-window",
                "lineage_root": (
                    "idea:I-keep-current-window→option:O-no-change→"
                    "claim:C-stable-sla→vote:V-3-0→"
                    "decision:D-2026-07-13-shipping-window"
                ),
                "material_inputs_digest": material_digest(MATERIAL_V1),
                "decided_logical": "wake-1",
            }
        ],
    }


def task(task_id: str, event: dict, ledger: dict | None = None) -> dict:
    return {
        "id": task_id,
        "event": event,
        "ledger": ledger if ledger is not None else settled_ledger(),
    }


def task_stale_six_weeks() -> dict:
    """Same question, same material inputs, 42 days later. Must not re-litigate."""
    return task(
        "fixture.standing-watch.stale-six-weeks",
        {
            "kind": "trigger",
            "question_id": QUESTION,
            "material_inputs": {
                **MATERIAL_V1,
                "elapsed_days": 42,
                "wall_clock": "2026-08-24T00:00:00Z",
                "asker_id": "owner-reask",
                "etag": "W/\"rotated-etag\"",
                "ad_markup": "<div>promo</div>",
            },
            "source_id": "src-shipping-policy",
        },
    )


def task_clock() -> dict:
    return task(
        "fixture.standing-watch.clock-tick",
        {
            "kind": "clock",
            "question_id": QUESTION,
            "material_inputs": MATERIAL_V1,
            "wall_clock": "2026-08-24T00:00:00Z",
        },
    )


def task_delta() -> dict:
    return task(
        "fixture.standing-watch.material-delta",
        {
            "kind": "trigger",
            "question_id": QUESTION,
            "material_inputs": MATERIAL_V2,
            "source_id": "src-shipping-policy",
        },
    )


def task_new() -> dict:
    return task(
        "fixture.standing-watch.new-question",
        {
            "kind": "trigger",
            "question_id": "Q-retention-period",
            "material_inputs": {"policy_sha256": "sha256:retention-v1", "days": 90},
            "source_id": "src-retention-policy",
        },
    )


def task_reopen() -> dict:
    return task(
        "fixture.standing-watch.authorized-reopen",
        {
            "kind": "reopen",
            "question_id": QUESTION,
            "material_inputs": MATERIAL_V1,
            "reopen_token": "owner-reopen-2026-08-24",
            "new_evidence_pointer": "evidence/incident-2026-08-20.json",
        },
    )


def task_reask() -> dict:
    """Owner asks again with neither token nor new evidence."""
    return task(
        "fixture.standing-watch.bare-reask",
        {
            "kind": "reopen",
            "question_id": QUESTION,
            "material_inputs": MATERIAL_V1,
            "reopen_token": "",
            "new_evidence_pointer": None,
        },
    )


def empty_ledger() -> dict:
    return {
        "watch_id": "watch.shipping-window",
        "bindings": [],
        "settled": [],
    }
