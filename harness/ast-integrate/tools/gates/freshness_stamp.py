"""Freshness stamp: reuse fresh greens, re-query stale ones (TST-0235).

Every gate whose verdict depends on a live external source (advisory DB,
registry, vendor API, reachability probe) stores its result together with a
``freshness_stamp`` -- the UTC instant the source was actually queried.  A
stored verdict is only a control for *now* while ``age <= max_age_seconds``
for its source class (inclusive bound, see ``freshness_policy.json``).  Past
that bound, or when the stamp is missing, the stored green reads as
``NOT-CHECKED`` and the source must be re-queried before a verdict is issued.

The two ``measure_*`` functions below are the unit's probes' data source.
They use an injected UTC clock (no wall-clock sleep) and an in-process
``AdvisoryFixture`` whose ``query`` call count is the observable that proves
a re-query did or did not happen.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
POLICY_PATH = HERE / "freshness_policy.json"

NOT_CHECKED = "NOT-CHECKED"
FRESH = "FRESH"
STALE = "STALE"
UNDATED_GREEN = "UNDATED-GREEN"

POLICY_ID = "TST-0235-freshness-stamp-v1"
DEFAULT_SOURCE_CLASS = "advisory-database"
INJECTED_NOW = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)

_FALLBACK_POLICY: dict[str, Any] = {
    "policy_id": POLICY_ID,
    "unit_id": "TST-0235",
    "path": "tools/gates/freshness_policy.json",
    "inclusive_bound": (
        "age_seconds <= max_age_seconds is FRESH; "
        "age_seconds > max_age_seconds is STALE"
    ),
    "stale_stored_green": NOT_CHECKED,
    "undated_green": NOT_CHECKED,
    "clock_skew": NOT_CHECKED,
    "unknown_source_class_max_age_seconds": 0,
    "sources": {
        DEFAULT_SOURCE_CLASS: {
            "endpoint": "https://api.osv.dev/v1/query",
            "max_age_seconds": 86400,
            "rationale": "A stored advisory-DB green is not a control for today.",
        }
    },
}


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    """Return the freshness policy (file on disk, else the built-in copy)."""
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and isinstance(doc.get("sources"), dict):
            return doc
    return json.loads(json.dumps(_FALLBACK_POLICY))


def dump_policy() -> dict[str, Any]:
    """Policy as embedded in receipts (sorted, JSON-safe copy)."""
    return json.loads(json.dumps(load_policy(), sort_keys=True))


def max_age_seconds(source_class: str, policy: dict[str, Any] | None = None) -> int:
    """max_age_seconds for a source class; unknown classes get the policy floor (0)."""
    pol = policy or load_policy()
    src = (pol.get("sources") or {}).get(source_class) or {}
    if "max_age_seconds" in src:
        return int(src["max_age_seconds"])
    return int(pol.get("unknown_source_class_max_age_seconds") or 0)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_stamp(stamp: Any) -> datetime | None:
    if stamp is None or stamp == "":
        return None
    if isinstance(stamp, datetime):
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
    text = str(stamp).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def age_seconds(stamp: Any, now: datetime) -> int | None:
    """Whole seconds between the stamp and ``now``; None for a missing/bad stamp."""
    queried_at = _parse_stamp(stamp)
    if queried_at is None:
        return None
    return int((now - queried_at).total_seconds())


def classify(stamp: Any, now: datetime, max_age: int) -> str:
    """FRESH (age <= max_age), STALE (age > max_age) or UNDATED-GREEN (no stamp)."""
    age = age_seconds(stamp, now)
    if age is None:
        return UNDATED_GREEN
    if age < 0:
        # A stamp from the future is a clock-skew symptom; never trust it.
        return STALE
    return FRESH if age <= max_age else STALE


@dataclass
class StoredResult:
    """A gate result persisted with its freshness stamp."""

    verdict: str
    source_class: str = DEFAULT_SOURCE_CLASS
    freshness_stamp: str | None = None
    endpoint: str = ""
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "source_class": self.source_class,
            "freshness_stamp": self.freshness_stamp,
            "endpoint": self.endpoint,
            "findings": list(self.findings),
        }


def gate_verdict(
    stored: StoredResult,
    now: datetime,
    policy: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """(verdict, classification) for a stored result read at ``now``.

    Only a FRESH record keeps its stored verdict.  STALE and UNDATED-GREEN
    records read as NOT-CHECKED -- a stored green is never a pass for today.
    """
    pol = policy or load_policy()
    cls = classify(stored.freshness_stamp, now, max_age_seconds(stored.source_class, pol))
    if cls == FRESH:
        return stored.verdict, cls
    return NOT_CHECKED, cls


def naive_read_gate(stored: StoredResult) -> str:
    """The age-blind control: returns the stored verdict regardless of stamp."""
    return stored.verdict


class AdvisoryFixture:
    """In-process stand-in for an advisory DB; counts every live query."""

    def __init__(self, endpoint: str, findings: list[str] | None = None) -> None:
        self.endpoint = endpoint
        self.findings = list(findings or [])
        self.query_count = 0

    def query(self, now: datetime) -> StoredResult:
        self.query_count += 1
        verdict = "FAIL" if self.findings else "PASS"
        return StoredResult(
            verdict=verdict,
            source_class=DEFAULT_SOURCE_CLASS,
            freshness_stamp=_iso(now),
            endpoint=self.endpoint,
            findings=list(self.findings),
        )


def evaluate(
    stored: StoredResult,
    fixture: AdvisoryFixture,
    now: datetime,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reuse a FRESH stored result; otherwise re-query the live source."""
    before = fixture.query_count
    verdict, cls = gate_verdict(stored, now, policy)
    reused = cls == FRESH
    live = stored if reused else fixture.query(now)
    return {
        "before_requery_verdict": verdict,
        "classification": cls,
        "reused": reused,
        "query_invoked": not reused,
        "query_count_delta": fixture.query_count - before,
        "live_verdict": live.verdict,
        "live_findings": list(live.findings),
        "live": live.to_dict(),
    }


def _stamp_vs_policy(age: int | None, max_age: int) -> str:
    if age is None:
        return "no stamp"
    return "age <= max_age" if age <= max_age else "age > max_age"


def measure_fresh_reuse(now: datetime = INJECTED_NOW) -> dict[str, Any]:
    """Probe 1 data: a fresh stamped PASS is reused; the twin one second past max_age is not."""
    policy = load_policy()
    max_age = max_age_seconds(DEFAULT_SOURCE_CLASS, policy)
    endpoint = str(policy["sources"][DEFAULT_SOURCE_CLASS].get("endpoint") or "")
    fixture = AdvisoryFixture(endpoint, findings=["CVE-2026-0001"])

    queried_at = now - timedelta(seconds=max_age // 2)
    fresh = StoredResult("PASS", DEFAULT_SOURCE_CLASS, _iso(queried_at), endpoint)
    fresh_eval = evaluate(fresh, fixture, now, policy)
    query_count_fresh = fixture.query_count

    # Both-states: the exact inclusive bound is FRESH, one second past it is STALE.
    at_bound = StoredResult(
        "PASS", DEFAULT_SOURCE_CLASS, _iso(now - timedelta(seconds=max_age)), endpoint
    )
    past_bound = StoredResult(
        "PASS", DEFAULT_SOURCE_CLASS, _iso(now - timedelta(seconds=max_age + 1)), endpoint
    )
    inclusive_bound_fresh = gate_verdict(at_bound, now, policy)[1] == FRESH
    inclusive_bound_plus_one_stale = gate_verdict(past_bound, now, policy)[1] == STALE

    twin_eval = evaluate(past_bound, fixture, now, policy)
    stale_twin_requery = twin_eval["query_invoked"] and twin_eval["query_count_delta"] == 1

    reused = fresh_eval["reused"]
    query_invoked = fresh_eval["query_invoked"]
    both_states = (
        reused
        and not query_invoked
        and stale_twin_requery
        and twin_eval["before_requery_verdict"] == NOT_CHECKED
        and inclusive_bound_fresh
        and inclusive_bound_plus_one_stale
    )
    age = age_seconds(fresh.freshness_stamp, now)
    return {
        "probe": "fresh-reuse",
        "pass": bool(both_states and query_count_fresh == 0),
        "reused": reused,
        "query_invoked": query_invoked,
        "query_count_fresh": query_count_fresh,
        "both_states": both_states,
        "stale_twin_requery": stale_twin_requery,
        "stale_twin_before": twin_eval["before_requery_verdict"],
        "stale_twin_classification": twin_eval["classification"],
        "stale_twin_requery_verdict": twin_eval["live_verdict"],
        "query_count_after_stale_twin": fixture.query_count,
        "fresh_classification": fresh_eval["classification"],
        "fresh_gate_verdict": fresh_eval["before_requery_verdict"],
        "inclusive_bound_fresh": inclusive_bound_fresh,
        "inclusive_bound_plus_one_stale": inclusive_bound_plus_one_stale,
        "age_seconds": age,
        "max_age_seconds": max_age,
        "stamp_vs_policy": _stamp_vs_policy(age, max_age),
        "endpoint": endpoint,
        "now": _iso(now),
        "queried_at": fresh.freshness_stamp,
    }


def measure_stale_advisory_green(now: datetime = INJECTED_NOW) -> dict[str, Any]:
    """Probe 2 data: yesterday's advisory PASS is NOT-CHECKED and re-queried today."""
    policy = load_policy()
    max_age = max_age_seconds(DEFAULT_SOURCE_CLASS, policy)
    endpoint = str(policy["sources"][DEFAULT_SOURCE_CLASS].get("endpoint") or "")
    # Today the advisory DB carries a finding the stored green predates.
    fixture = AdvisoryFixture(endpoint, findings=["CVE-2026-0001"])

    queried_at = now - timedelta(seconds=max_age + 3600)
    stored = StoredResult("PASS", DEFAULT_SOURCE_CLASS, _iso(queried_at), endpoint)
    naive_gate_verdict = naive_read_gate(stored)
    result = evaluate(stored, fixture, now, policy)

    undated = StoredResult("PASS", DEFAULT_SOURCE_CLASS, None, endpoint)
    undated_gate_verdict, undated_classification = gate_verdict(undated, now, policy)

    age = age_seconds(stored.freshness_stamp, now)
    naive_still_pass = naive_gate_verdict == "PASS"
    ok = (
        result["before_requery_verdict"] == NOT_CHECKED
        and result["classification"] == STALE
        and naive_still_pass
        and result["query_invoked"]
        and result["query_count_delta"] == 1
        and result["live_verdict"] == "FAIL"
        and undated_gate_verdict == NOT_CHECKED
    )
    return {
        "probe": "stale-advisory-green",
        "pass": bool(ok),
        "before_requery_verdict": result["before_requery_verdict"],
        "classification": result["classification"],
        "stored_verdict": stored.verdict,
        "naive_gate_verdict": naive_gate_verdict,
        "naive_still_pass": naive_still_pass,
        "query_invoked": result["query_invoked"],
        "query_count_delta": result["query_count_delta"],
        "live_verdict": result["live_verdict"],
        "live_findings": result["live_findings"],
        "both_states": bool(naive_still_pass and result["before_requery_verdict"] == NOT_CHECKED),
        "undated_gate_verdict": undated_gate_verdict,
        "undated_classification": undated_classification,
        "age_seconds": age,
        "max_age_seconds": max_age,
        "stamp_vs_policy": _stamp_vs_policy(age, max_age),
        "endpoint": endpoint,
        "now": _iso(now),
        "queried_at": stored.freshness_stamp,
    }


def measure_stale_advisory(now: datetime = INJECTED_NOW) -> dict[str, Any]:
    """Backward-compatible alias for older callers."""
    return measure_stale_advisory_green(now)


__all__ = [
    "AdvisoryFixture",
    "FRESH",
    "NOT_CHECKED",
    "POLICY_ID",
    "STALE",
    "StoredResult",
    "UNDATED_GREEN",
    "age_seconds",
    "classify",
    "dump_policy",
    "evaluate",
    "gate_verdict",
    "load_policy",
    "max_age_seconds",
    "measure_fresh_reuse",
    "measure_stale_advisory",
    "measure_stale_advisory_green",
    "naive_read_gate",
]
