#!/usr/bin/env python3
"""Twenty structurally valid CouncilSpec fixtures for IMP-0262 determinism.

Harness 11-COUNCIL-SPECIFICATION.schema.json is absent on this worktree (same
finding as CNL-0001). Fixtures follow the reconstructed 13-section charter
shape: charter, participants, roles, engagement, budgets, evidence, voting,
stopping, outcomes, integrity, artifacts, execution, plus optional meta.

These are compile-time inputs, not a byte-copy of an unread file.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

VENDORS = ("anthropic", "openai", "google", "local")
MODELS = ("opus", "sonnet", "gpt", "gemini")
ROLES = ("Architect", "Skeptic", "Pragmatist", "Critic", "Chair", "Clerk")
RULES = (
    "majority",
    "unanimous-or-record-dissent",
    "supermajority",
    "chair-break",
)
STANDARDS = (
    "executable-proof-only",
    "cited-anchor",
    "two-independent-signals",
)


def _stopping(n: int, max_rounds: int) -> Any:
    mode = n % 3
    if mode == 0:
        return f"ALL(votes_cast) AND rounds>={max_rounds}"
    if mode == 1:
        return {"mode": "expression", "expression": "ALL(votes_cast) AND NOT timeout"}
    return {"max_rounds": max_rounds, "on_timeout": "halt", "on_unresolved": "BLOCKED"}


def make_spec(n: int) -> dict:
    """Build fixture n in 0..19. Distinct seat counts, rounds, rules, stopping shapes."""
    n_seats = 2 + (n % 5)
    max_rounds = 1 + (n % 4)
    roles = [ROLES[i % len(ROLES)] for i in range(n_seats)]
    seats = []
    for i in range(n_seats):
        seats.append(
            {
                "id": f"seat-{n:02d}-{i:02d}",
                "role": roles[i],
                "vendor": VENDORS[(n + i) % len(VENDORS)],
                "model": MODELS[(n + i) % len(MODELS)],
                "expertise": "council-systems" if i == 0 else "review",
                "vote_weight": 1 + (i % 2),
                "tools": ["Read", "Grep"] if i % 2 == 0 else ["Read"],
                "authority": "draft" if i == 0 else "vote",
            }
        )
    spec = {
        "charter": {
            "objective": f"Compile fixture {n:02d} into an explicit round/turn/gate plan",
            "risk_tier": ("low", "medium", "high")[n % 3],
            "desired_output": "typed-execution-plan",
            "success_criteria": "byte-identical recompile; every seat/round/gate named",
            "consensus_intent": RULES[n % len(RULES)],
        },
        "participants": seats,
        "roles": roles,
        "engagement": {"min_turns": max_rounds, "max_inactivity": 2 + (n % 3)},
        "budgets": {"tokens": 1000 * (n + 1), "time_seconds": 60 * (n + 1)},
        "evidence": {
            "standard": STANDARDS[n % len(STANDARDS)],
            "hash_inputs": True,
        },
        "voting": {
            "rule": RULES[n % len(RULES)],
            "quorum": max(1, n_seats - (n % 2)),
        },
        "stopping": _stopping(n, max_rounds),
        "outcomes": {
            "allowed": ["decision", "irreducible-disagreement", "timeout"][: 2 + (n % 2)]
        },
        "integrity": {"hash_transcript": True, "anonymity": "named"},
        "artifacts": {"persist": True, "plan_required_before_model_call": True},
        "execution": {"runtime": "councilspec-compiler", "topology": "round-robin"},
        "meta": {"schema_version": "2", "fixture": n},
    }
    return spec


def twenty_specs() -> list[dict]:
    rows = [make_spec(n) for n in range(20)]
    assert len(rows) == 20
    return rows


def reorder_keys(obj: Any, rotate: bool = True) -> Any:
    """Same values, different dict insertion order. List order is preserved."""
    if isinstance(obj, dict):
        keys = list(obj.keys())
        if rotate and keys:
            keys = keys[1:] + keys[:1]
        else:
            keys = list(reversed(keys))
        return {k: reorder_keys(obj[k], rotate) for k in keys}
    if isinstance(obj, list):
        return [reorder_keys(x, rotate) for x in obj]
    return obj


def spec_pair(n: int) -> tuple[dict, dict]:
    """Two equivalent specs whose dict keys were inserted in different orders."""
    a = make_spec(n)
    b = reorder_keys(deepcopy(a), rotate=True)
    return a, b
