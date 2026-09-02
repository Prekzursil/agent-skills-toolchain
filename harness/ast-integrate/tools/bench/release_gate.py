"""B07 release gate: "without material regression" as a number (TST-0301).

A candidate that wins on the primary metric is released only if every
secondary metric the gate reads stays within its pre-decided non-inferiority
margin.  The rule is inclusive: ``worse_delta <= margin`` resolves
``NON_INFERIOR``.  Margins are frozen by content address: a comparison binds
the sha256 of the table it was scored against, and any later edit to the table
is ``POST_HOC_MARGIN_CHANGE`` rather than a silent re-score.  A comparison that
started before the margins were decided is ``POST_HOC_MARGIN_DECISION``.
"""
from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from tools.bench import margins, paths, serialize

__all__ = [
    "AT_MARGIN_RESOLVES",
    "AT_MARGIN_RULE",
    "EQUAL",
    "IMPROVED",
    "INVENTORY_GAP",
    "MATERIAL_REGRESSION",
    "NON_INFERIOR",
    "NO_PRIMARY_WIN",
    "PASS",
    "POST_HOC_MARGIN_CHANGE",
    "POST_HOC_MARGIN_DECISION",
    "REFUSE",
    "UNBOUND",
    "UNDEFINED_MARGIN",
    "VERDICTS",
    "bind_table",
    "evaluate",
    "metric_status",
    "parse_timestamp",
    "schema_rejects_garbage",
    "worse_delta",
]

# Per-metric statuses.
IMPROVED = "IMPROVED"
EQUAL = "EQUAL"
NON_INFERIOR = "NON_INFERIOR"
MATERIAL_REGRESSION = "MATERIAL_REGRESSION"

# Overall verdicts, in precedence order (first applicable wins).
UNBOUND = "UNBOUND"
POST_HOC_MARGIN_CHANGE = "POST_HOC_MARGIN_CHANGE"
POST_HOC_MARGIN_DECISION = "POST_HOC_MARGIN_DECISION"
INVENTORY_GAP = "INVENTORY_GAP"
UNDEFINED_MARGIN = "UNDEFINED_MARGIN"
REFUSE = "REFUSE"
NO_PRIMARY_WIN = "NO_PRIMARY_WIN"
PASS = "PASS"
VERDICTS = (
    UNBOUND,
    POST_HOC_MARGIN_CHANGE,
    POST_HOC_MARGIN_DECISION,
    INVENTORY_GAP,
    UNDEFINED_MARGIN,
    REFUSE,
    NO_PRIMARY_WIN,
    PASS,
)

AT_MARGIN_RESOLVES = NON_INFERIOR
AT_MARGIN_RULE = "worse_delta <= margin"
_HIGHER = "higher_is_better"
_LOWER = "lower_is_better"


# --------------------------------------------------------------------------- binding
def bind_table(table: dict) -> str:
    """Content address (sha256) of a margin table as it is scored against.

    The digest is over the canonical serialization (``serialize.canonical_bytes``),
    so a table written with ``serialize.write_json`` digests identically on disk
    and in memory.
    """
    return serialize.digest_document(table)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse ``YYYY-MM-DDTHH:MM:SSZ`` (UTC); ``None`` when absent or malformed."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# --------------------------------------------------------------------------- inequality
def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None


def worse_delta(polarity: str, baseline: Any, candidate: Any) -> Decimal:
    """How much worse the candidate is than the baseline (negative = better)."""
    base, cand = _decimal(baseline), _decimal(candidate)
    if base is None or cand is None:
        raise ValueError(f"non-numeric value baseline={baseline!r} candidate={candidate!r}")
    if polarity == _HIGHER:
        return base - cand
    if polarity == _LOWER:
        return cand - base
    raise ValueError(f"unknown polarity {polarity!r}")


def metric_status(polarity: str, baseline: Any, candidate: Any, margin: Any) -> str:
    """Classify one metric with exact decimal arithmetic.

    ``worse_delta < 0`` -> IMPROVED; ``== 0`` -> EQUAL; ``<= margin`` ->
    NON_INFERIOR (inclusive bound); otherwise MATERIAL_REGRESSION.
    """
    worse = worse_delta(polarity, baseline, candidate)
    bound = _decimal(margin)
    if bound is None:
        raise ValueError(f"non-numeric margin {margin!r}")
    if worse < 0:
        return IMPROVED
    if worse == 0:
        return EQUAL
    if worse <= bound:
        return NON_INFERIOR
    return MATERIAL_REGRESSION


# --------------------------------------------------------------------------- evaluation
def _record(comparison: dict, table: dict, inventory: dict, bound: Any, live: str) -> dict:
    return {
        "comparison_id": comparison.get("id"),
        "started_at": comparison.get("started_at"),
        "table_path": paths.MARGIN_TABLE_REL,
        "decided_at": table.get("decided_at"),
        "bound_sha256": bound,
        "live_sha256": live,
        "at_margin_resolves": AT_MARGIN_RESOLVES,
        "at_margin_rule": AT_MARGIN_RULE,
        "gate_metrics": margins.gate_metric_ids(inventory),
        "metrics": [],
        "alarms": [],
        "verdict": None,
    }


def _finish(record: dict, verdict: str, alarms: list[str]) -> dict:
    record["verdict"] = verdict
    record["alarms"] = list(alarms)
    return record


def evaluate(
    comparison: dict,
    *,
    table: dict,
    inventory: dict,
    root: str | os.PathLike[str] | None = None,
) -> dict:
    """Score ``comparison`` against the live ``table`` it claims to be bound to.

    ``comparison`` carries ``id``, ``started_at``, ``baseline``, ``candidate``
    (metric id -> value) and ``margin_table_sha256`` (the digest bound when the
    comparison ran).  ``root`` is accepted for callers that resolve paths; the
    verdict depends only on the documents passed in.
    """
    del root  # path resolution is the loader's job; evaluation is pure
    bound = comparison.get("margin_table_sha256")
    live = bind_table(table)
    record = _record(comparison, table, inventory, bound, live)

    if not isinstance(bound, str) or not bound:
        return _finish(record, UNBOUND, ["comparison carries no margin_table_sha256"])
    if bound != live:
        return _finish(
            record,
            POST_HOC_MARGIN_CHANGE,
            [f"live margin table sha256 {live} != bound {bound}: margins changed after scoring"],
        )

    started = parse_timestamp(comparison.get("started_at"))
    decided = parse_timestamp(table.get("decided_at"))
    if started is None or decided is None:
        return _finish(
            record,
            UNBOUND,
            [
                f"cannot order comparison started_at={comparison.get('started_at')!r} "
                f"against decided_at={table.get('decided_at')!r}"
            ],
        )
    if started < decided:
        return _finish(
            record,
            POST_HOC_MARGIN_DECISION,
            [
                f"comparison started {comparison['started_at']} before margins were "
                f"decided {table['decided_at']}"
            ],
        )

    gaps = margins.coverage_gaps(inventory, table)
    if gaps:
        return _finish(record, INVENTORY_GAP, gaps)

    rows_by_id = margins.table_by_id(table)
    baseline = comparison.get("baseline") or {}
    candidate = comparison.get("candidate") or {}
    undefined: list[str] = []
    rows: list[dict] = []
    for metric_id in margins.gate_metric_ids(inventory):
        row = rows_by_id[metric_id]
        base_value = baseline.get(metric_id)
        cand_value = candidate.get(metric_id)
        if _decimal(base_value) is None or _decimal(cand_value) is None:
            undefined.append(
                f"{metric_id}: baseline={base_value!r} candidate={cand_value!r} "
                "(no numeric value to compare against its margin)"
            )
            continue
        worse = worse_delta(row["polarity"], base_value, cand_value)
        status = metric_status(row["polarity"], base_value, cand_value, row["margin"])
        rows.append(
            {
                "id": metric_id,
                "role": row.get("role"),
                "polarity": row["polarity"],
                "unit": row.get("unit"),
                "baseline": base_value,
                "candidate": cand_value,
                "margin": row["margin"],
                "worse_delta": float(worse),
                "status": status,
                "at_margin": status == NON_INFERIOR and worse == _decimal(row["margin"]),
            }
        )
    record["metrics"] = rows
    if undefined:
        return _finish(record, UNDEFINED_MARGIN, undefined)

    regressions = [r for r in rows if r["status"] == MATERIAL_REGRESSION]
    if regressions:
        return _finish(
            record,
            REFUSE,
            [
                f"{r['id']}: worse_delta {r['worse_delta']} > margin {r['margin']} "
                f"({MATERIAL_REGRESSION})"
                for r in regressions
            ],
        )
    primaries = [r for r in rows if r["role"] == "primary"]
    not_won = [r for r in primaries if r["status"] != IMPROVED]
    if not_won:
        return _finish(
            record,
            NO_PRIMARY_WIN,
            [f"{r['id']}: primary status {r['status']}, nothing to release" for r in not_won],
        )
    return _finish(record, PASS, [])


# --------------------------------------------------------------------------- schema control
def _garbage_tables(good: dict) -> list[tuple[str, Any]]:
    cases: list[tuple[str, Any]] = [("empty-object", {}), ("not-an-object", [])]

    def variant(name: str, mutate) -> None:
        doc = deepcopy(good)
        mutate(doc)
        cases.append((name, doc))

    variant("wrong-kind", lambda d: d.__setitem__("kind", "margin-table"))
    variant("schema-version-2", lambda d: d.__setitem__("schema_version", 2))
    variant("missing-decided-at", lambda d: d.pop("decided_at"))
    variant("decided-at-date-only", lambda d: d.__setitem__("decided_at", "2026-08-01"))
    variant("at-margin-inferior", lambda d: d.__setitem__("at_margin_resolves", "INFERIOR"))
    variant("rule-strict", lambda d: d.__setitem__("at_margin_rule", "worse_delta < margin"))
    variant("extra-top-level", lambda d: d.__setitem__("notes", "x"))
    variant("metrics-empty", lambda d: d.__setitem__("metrics", []))
    variant("metric-missing-margin", lambda d: d["metrics"][0].pop("margin"))
    variant("metric-negative-margin", lambda d: d["metrics"][0].__setitem__("margin", -0.01))
    variant("metric-string-margin", lambda d: d["metrics"][0].__setitem__("margin", "0.02"))
    variant("metric-bad-polarity", lambda d: d["metrics"][0].__setitem__("polarity", "up"))
    variant("metric-bad-role", lambda d: d["metrics"][0].__setitem__("role", "tertiary"))
    variant("metric-extra-key", lambda d: d["metrics"][0].__setitem__("weight", 1))
    return cases


def _garbage_inventories(good: dict) -> list[tuple[str, Any]]:
    cases: list[tuple[str, Any]] = [("inv-empty-object", {})]

    def variant(name: str, mutate) -> None:
        doc = deepcopy(good)
        mutate(doc)
        cases.append((name, doc))

    variant("inv-wrong-kind", lambda d: d.__setitem__("kind", "inventory"))
    variant("inv-no-receipts", lambda d: d.__setitem__("b01_b10_receipts", []))
    variant("inv-metric-missing-gate", lambda d: d["metrics"][0].pop("gate"))
    variant("inv-metric-gate-string", lambda d: d["metrics"][0].__setitem__("gate", "yes"))
    variant("inv-metric-bad-bucket", lambda d: d["metrics"][0].__setitem__("bucket", "B99"))
    variant("inv-extra-top-level", lambda d: d.__setitem__("owner", "x"))
    return cases


def schema_rejects_garbage(root: str | os.PathLike[str] | None = None) -> list[str]:
    """Names of malformed documents the schemas ACCEPTED (empty = all rejected).

    Includes a positive control: a minimal well-formed table and inventory must
    validate, otherwise the check is vacuous and the control name is returned.
    """
    table_schema = margins.load_schema(paths.MARGIN_TABLE_SCHEMA_REL, root)
    inventory_schema = margins.load_schema(paths.INVENTORY_SCHEMA_REL, root)
    good_table = {
        "schema_version": 1,
        "kind": "b07-margin-table",
        "decided_at": "2026-08-01T00:00:00Z",
        "git_state": "NOT-A-GIT-REPO",
        "at_margin_resolves": AT_MARGIN_RESOLVES,
        "at_margin_rule": AT_MARGIN_RULE,
        "metrics": [
            {
                "id": "oracle_pass_rate",
                "role": "primary",
                "polarity": _HIGHER,
                "margin": 0.0,
                "rationale": "primary must improve",
            },
            {
                "id": "outcome_check_rate",
                "role": "secondary",
                "polarity": _HIGHER,
                "margin": 0.02,
                "rationale": "two points of outcome-check rate",
            },
        ],
    }
    good_inventory = {
        "schema_version": 1,
        "kind": "metric-inventory",
        "derivation": "B01 quality metrics plus B10 cost metrics",
        "b01_b10_receipts": ["command-center/receipts/B01.json"],
        "metrics": [
            {
                "id": "oracle_pass_rate",
                "polarity": _HIGHER,
                "gate": True,
                "bucket": "B01",
                "description": "share of cases passing the oracle",
            }
        ],
    }
    accepted: list[str] = []
    if margins.schema_errors(good_table, table_schema):
        accepted.append("CONTROL-REJECTED:good-table")
    if margins.schema_errors(good_inventory, inventory_schema):
        accepted.append("CONTROL-REJECTED:good-inventory")
    for name, doc in _garbage_tables(good_table):
        if not margins.schema_errors(doc, table_schema):
            accepted.append(name)
    for name, doc in _garbage_inventories(good_inventory):
        if not margins.schema_errors(doc, inventory_schema):
            accepted.append(name)
    return accepted
