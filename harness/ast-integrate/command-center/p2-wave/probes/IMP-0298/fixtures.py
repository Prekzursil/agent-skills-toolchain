"""Per-dimension exhaustion fixtures for IMP-0298.

Each fixture is a CouncilSpec budgets slice plus events that MUST trip
BUDGET_EXHAUSTED on exactly that dimension. A complete-run control is included
for the marker load-bearing negative control.
"""

from __future__ import annotations

from typing import Any

TITLE_DIMENSIONS: tuple[str, ...] = (
    "effort",
    "tokens",
    "tool_calls",
    "turns",
    "time",
    "experiments",
)

ALL_DIMENSIONS: tuple[str, ...] = TITLE_DIMENSIONS + (
    "sources",
    "speaking_quotas",
    "minimum_engagement",
    "maximum_inactivity",
    "rebuttal_depth",
    "escalation",
)

# Isolated specs: only the dimension under test is constrained.
EXHAUST_FIXTURES: dict[str, dict[str, Any]] = {
    "effort": {
        "spec": {"budgets": {"effort": {"limit": 2}}},
        "events": [
            {"text": "alpha", "effort": 1},
            {"text": "bravo", "effort": 1},
            {"text": "charlie", "effort": 1},
        ],
        "expect_exhausted": "effort",
    },
    "tokens": {
        "spec": {"budgets": {"tokens": {"limit": 4}}},
        "events": [
            {"text": "alpha bravo charlie delta echo foxtrot"},
        ],
        "expect_exhausted": "tokens",
        "expect_text_prefix": "alpha bravo charlie delta",
    },
    "tool_calls": {
        "spec": {"budgets": {"tool_calls": {"limit": 1}}},
        "events": [
            {"text": "use one", "tool_calls": ["search"]},
            {"text": "use two", "tool_calls": ["fetch"]},
        ],
        "expect_exhausted": "tool_calls",
    },
    "turns": {
        "spec": {"budgets": {"turns": {"limit": 1}}},
        "events": [
            {"text": "first turn text"},
            {"text": "second turn should be refused"},
        ],
        "expect_exhausted": "turns",
    },
    "time": {
        "spec": {"budgets": {"time": {"limit": 10}}},
        "events": [
            {"text": "in flight when the clock expires", "duration_ms": 50},
        ],
        "expect_exhausted": "time",
    },
    "experiments": {
        "spec": {"budgets": {"experiments": {"limit": 1}}},
        "events": [
            {"text": "run A", "experiment": "exp-a"},
            {"text": "run B", "experiment": "exp-b"},
        ],
        "expect_exhausted": "experiments",
    },
    "sources": {
        "spec": {"budgets": {"sources": {"limit": 1}}},
        "events": [
            {"text": "cite one", "source": "uri://a"},
            {"text": "cite two", "source": "uri://b"},
        ],
        "expect_exhausted": "sources",
    },
    "speaking_quotas": {
        "spec": {"budgets": {"speaking_quotas": {"limit": 1}}},
        "events": [
            {"participant": "seat-a", "text": "first floor"},
            {"participant": "seat-a", "text": "second floor refused"},
        ],
        "expect_exhausted": "speaking_quotas",
    },
    "minimum_engagement": {
        "spec": {"budgets": {"minimum_engagement": {"floor": 2}}},
        "events": [
            {"participant": "seat-a", "text": "only one unit", "engagement_units": 1},
        ],
        "expect_exhausted": "minimum_engagement",
    },
    "maximum_inactivity": {
        "spec": {"budgets": {"maximum_inactivity": {"limit": 1}}},
        "events": [
            {"text": "spoke once"},
            {"kind": "idle", "participant": "seat-a"},
            {"kind": "idle", "participant": "seat-a"},
        ],
        "expect_exhausted": "maximum_inactivity",
    },
    "rebuttal_depth": {
        "spec": {"budgets": {"rebuttal_depth": {"limit": 2}}},
        "events": [
            {"text": "too deep", "rebuttal_depth": 3},
        ],
        "expect_exhausted": "rebuttal_depth",
    },
    "escalation": {
        "spec": {"budgets": {"escalation": {"limit": 1}}},
        "events": [
            {"text": "escalate once", "escalation": 1},
            {"text": "escalate twice", "escalation": 1},
        ],
        "expect_exhausted": "escalation",
    },
}

COMPLETE_CONTROL: dict[str, Any] = {
    "spec": {"budgets": {"tokens": {"limit": 50}, "turns": {"limit": 10}}},
    "events": [{"text": "short complete answer within budget"}],
}
