#!/usr/bin/env python3
"""Recorded three-decision council artifact for IMP-0316.

Decision D2 is chair-override with a reject-majority tally. A CLI that
guesses the rule from the tally would name a majority-reject rule; the
audit CLI must name the stored rule, and UNKNOWN once that field is gone.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE_PATH = HERE / "fixtures" / "recorded-council.json"

COUNCIL_ID = "cnl-imp-0316-recorded"

RULE_MAJORITY = "rule.majority-quorum"
RULE_CHAIR = "rule.chair-override"
RULE_QUALIFIED = "rule.qualified-majority-with-abstain"


def _event(seq: int, kind: str, round_id: int, **extra: Any) -> dict[str, Any]:
    row = {
        "seq": seq,
        "id": f"e{seq}",
        "kind": kind,
        "round": round_id,
    }
    row.update(extra)
    return row


def recorded_council() -> dict[str, Any]:
    """Three recorded decisions with raw event ranges and explicit rule ids."""
    events: list[dict[str, Any]] = [
        _event(0, "round_start", 1, title="Ship the audit CLI?"),
        _event(
            1,
            "claim",
            1,
            actor="alice",
            text="Ship tools/council/cli/audit.py; replay must name rule, tally, evidence.",
        ),
        _event(2, "vote", 1, actor="alice", choice="accept"),
        _event(3, "vote", 1, actor="bob", choice="accept"),
        _event(4, "vote", 1, actor="carol", choice="accept"),
        _event(5, "vote", 1, actor="dave", choice="reject"),
        _event(
            6,
            "dissent",
            1,
            actor="dave",
            text="Without event-range spot-check the lineage is theatre.",
        ),
        _event(
            7,
            "decision",
            1,
            decision_id="D1",
            deciding_rule_id=RULE_MAJORITY,
            outcome="accept",
        ),
        _event(8, "round_start", 2, title="Require owner sign-off on every replay?"),
        _event(
            9,
            "claim",
            2,
            actor="dave",
            text="Chair override: owner sign-off is waived for offline audit-only replay.",
        ),
        _event(10, "vote", 2, actor="alice", choice="reject"),
        _event(11, "vote", 2, actor="bob", choice="reject"),
        _event(12, "vote", 2, actor="carol", choice="reject"),
        _event(13, "vote", 2, actor="dave", choice="accept"),
        _event(
            14,
            "decision",
            2,
            decision_id="D2",
            deciding_rule_id=RULE_CHAIR,
            outcome="accept",
        ),
        _event(15, "round_start", 3, title="Persist lineage export on disk?"),
        _event(
            16,
            "claim",
            3,
            actor="bob",
            text="Persist lineage JSON next to the artifact so later audits do not re-ask a model.",
        ),
        _event(17, "vote", 3, actor="alice", choice="accept"),
        _event(18, "vote", 3, actor="bob", choice="accept"),
        _event(19, "vote", 3, actor="carol", choice="abstain"),
        _event(20, "vote", 3, actor="dave", choice="accept"),
        _event(
            21,
            "decision",
            3,
            decision_id="D3",
            deciding_rule_id=RULE_QUALIFIED,
            outcome="accept",
        ),
    ]
    decisions = [
        {
            "decision_id": "D1",
            "round": 1,
            "outcome": "accept",
            "deciding_rule_id": RULE_MAJORITY,
            "tally": {"accept": 3, "reject": 1, "abstain": 0},
            "evidence_event_seqs": [1],
            "event_range": [0, 8],
            "dissents": [
                {
                    "id": "dis-dave-1",
                    "actor": "dave",
                    "event_seq": 6,
                    "claim": "Without event-range spot-check the lineage is theatre.",
                }
            ],
        },
        {
            "decision_id": "D2",
            "round": 2,
            "outcome": "accept",
            "deciding_rule_id": RULE_CHAIR,
            "tally": {"accept": 1, "reject": 3, "abstain": 0},
            "evidence_event_seqs": [9],
            "event_range": [8, 15],
            "dissents": [
                {
                    "id": "dis-alice-2",
                    "actor": "alice",
                    "event_seq": 10,
                    "claim": "Owner sign-off should remain mandatory.",
                }
            ],
        },
        {
            "decision_id": "D3",
            "round": 3,
            "outcome": "accept",
            "deciding_rule_id": RULE_QUALIFIED,
            "tally": {"accept": 3, "reject": 0, "abstain": 1},
            "evidence_event_seqs": [16],
            "event_range": [15, 22],
            "dissents": [],
        },
    ]
    return {
        "schema": "council.artifact.v1",
        "council_id": COUNCIL_ID,
        "title": "IMP-0316 recorded council (offline audit fixture)",
        "rounds": [
            {"round": 1, "title": "Ship the audit CLI?", "decision_id": "D1"},
            {
                "round": 2,
                "title": "Require owner sign-off on every replay?",
                "decision_id": "D2",
            },
            {
                "round": 3,
                "title": "Persist lineage export on disk?",
                "decision_id": "D3",
            },
        ],
        "events": events,
        "decisions": decisions,
    }


def strip_deciding_rules(artifact: dict[str, Any]) -> dict[str, Any]:
    """Remove every deciding-rule id. Used by the UNKNOWN negative control."""
    doc = copy.deepcopy(artifact)
    for decision in doc.get("decisions") or []:
        if isinstance(decision, dict):
            decision.pop("deciding_rule_id", None)
            decision.pop("deciding_rule", None)
    for event in doc.get("events") or []:
        if isinstance(event, dict) and event.get("kind") == "decision":
            event.pop("deciding_rule_id", None)
            event.pop("deciding_rule", None)
    return doc


def guess_majority_rule(tally: dict[str, Any]) -> str:
    """What a guessing CLI would emit from tally alone. Not used by audit.py."""
    accept = int(tally.get("accept", 0) or 0)
    reject = int(tally.get("reject", 0) or 0)
    if accept > reject:
        return "rule.majority-quorum"
    if reject > accept:
        return "rule.majority-reject"
    return "rule.tie"


def write_recorded(path: Path | None = None) -> Path:
    dest = path or FIXTURE_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(recorded_council(), indent=2, sort_keys=True, ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )
    return dest
