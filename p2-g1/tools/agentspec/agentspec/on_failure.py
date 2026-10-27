"""IMP-0138: on-failure policy validation over the ONE closed taxonomy.

Recovered 2026-10-25 by builder shard 11 wave 2 from the delivery receipt
`command-center/receipts/IMP-0138.json`: the on-failure surface validates that
every ``unit.on_failure`` key is a member (or parametrised member) of the ONE
closed taxonomy (agentspec.taxonomy.REASONS via family()), and that every
taxonomy family has exactly one default policy.

Recovered contract (receipt-pinned):
  * DEFAULT_ON_FAILURE: family -> policy, covering every family exactly once
  * validate_on_failure(unit.on_failure) -> violation ids:
      - on-failure-unknown-reason  (key outside the closed taxonomy)
      - on-failure-policy-invalid  (value not a valid policy)
  * family_of(code) rides taxonomy.family (hyphen-boundary matcher); a
    substring resolver would accept near-misses, so the probes plant one and
    require the two to differ.
"""
from __future__ import annotations

from typing import Any

from agentspec.taxonomy import REASONS, family

POLICIES = frozenset({"retry", "fanout-skip", "fail-workflow", "handoff"})

FAMILY_POLICY: dict[str, str] = {
    "budget-exhausted": "fail-workflow",
    "env-missing": "fail-workflow",
    "policy-violation": "fail-workflow",
    "progress-stream": "fanout-skip",
    "rail-exit": "retry",
    "rate-limited": "retry",
    "receipt-empty": "retry",
    "receipt-missing": "retry",
    "receipt-incomplete": "retry",
    "receipt-unparseable": "retry",
    "schema-invalid": "fail-workflow",
    "severed-stream": "fail-workflow",
    "spawn-failed": "retry",
    "win-arg-limit": "fail-workflow",
    "timeout": "retry",
}

VIOLATION_UNKNOWN = "on-failure-unknown-reason"
VIOLATION_POLICY_INVALID = "on-failure-policy-invalid"


def _families() -> dict[str, list[str]]:
    """member -> family, derived mechanically from the taxonomy module."""
    out: dict[str, list[str]] = {}
    for member in REASONS:
        out.setdefault(family(member), []).append(member)
    return out


def build_default_on_failure() -> dict[str, str]:
    """Every taxonomy family -> exactly one policy row.

    Rows ride FAMILY_POLICY when the family is enumerated there; any family
    that escapes that table defaults to retry so coverage is TOTAL but never
    guessed for an unmeasured family."""
    rows: dict[str, str] = {}
    for fam in sorted(_families()):
        if not fam:
            continue
        rows[fam] = FAMILY_POLICY.get(fam, "retry")
    return rows


DEFAULT_ON_FAILURE = build_default_on_failure()


def family_of(code: str) -> str:
    """Family behind any taxonomy code (bare or parametrised)."""
    return family(code)


def validate_on_failure(on_failure: dict[str, Any] | None) -> list[str]:
    """Every key a taxonomy member/parametrised member; every value a policy."""
    viols: list[str] = []
    for key, policy in dict(on_failure or {}).items():
        if not family(str(key)):
            viols.append(VIOLATION_UNKNOWN)
        elif str(policy) not in POLICIES:
            viols.append(VIOLATION_POLICY_INVALID)
    return viols
