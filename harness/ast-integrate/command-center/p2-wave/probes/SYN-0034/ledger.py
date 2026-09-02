#!/usr/bin/env python3
"""Improvement-ledger core: classify rows and derive the net from the table.

A missing baseline is UNMEASURED, never NEUTRAL. Net polarity is
IMPROVED-count minus REGRESSED-count; UNMEASURED rows do not vote as
success. REGRESSED change_ids are always listed, including when net is
IMPROVED.
"""
from __future__ import annotations

from typing import Any

VERDICTS = ("IMPROVED", "NEUTRAL", "REGRESSED", "UNMEASURED")
NOISE_ABS_DEFAULT = 0.0
MIN_N_FOR_INTERVAL = 2

# Explicit statement used whenever a CI is not computed. Never invent one.
N_TOO_SMALL = (
    "n is too small for a confidence interval: only a single point estimate "
    "per arm is recorded (replicate_n < {min_n})"
)

DERIVATION = (
    "net_verdict = IMPROVED if (IMPROVED - REGRESSED) > 0; "
    "REGRESSED if (IMPROVED - REGRESSED) < 0; "
    "else if every published row is UNMEASURED then UNMEASURED; "
    "else NEUTRAL. UNMEASURED rows do not vote as NEUTRAL or IMPROVED. "
    "REGRESSED change_ids are listed even when net_verdict is IMPROVED."
)

# Planted tables. Not mixed into the live join.
FIXTURES: dict[str, list[dict[str, Any]]] = {
    "missing_baseline": [
        {
            "change_id": "ctrl.missing-baseline",
            "title": "Change whose Phase-0 baseline was never captured",
            "metric_id": "latency_ms",
            "higher_is_better": False,
            "baseline_value": None,
            "baseline_anchor": "fixtures/missing_baseline (baseline absent)",
            "post_value": 12.0,
            "post_anchor": "fixtures/missing_baseline (post present)",
            "n": 3,
            "source": "fixture.missing_baseline",
        }
    ],
    "planted_regression": [
        {
            "change_id": "ctrl.planted-worse-latency",
            "title": "Planted latency increase (lower-is-better metric)",
            "metric_id": "latency_ms",
            "higher_is_better": False,
            "baseline_value": 10.0,
            "baseline_anchor": "fixtures/planted_regression baseline",
            "post_value": 25.0,
            "post_anchor": "fixtures/planted_regression post",
            "n": 8,
            "source": "fixture.planted_regression",
        }
    ],
    "positive_net_with_regression": [
        {
            "change_id": "ctrl.faster-latency",
            "title": "Latency halved",
            "metric_id": "latency_ms",
            "higher_is_better": False,
            "baseline_value": 100.0,
            "baseline_anchor": "fixtures/positive_net baseline/latency",
            "post_value": 50.0,
            "post_anchor": "fixtures/positive_net post/latency",
            "n": 5,
            "source": "fixture.positive_net_with_regression",
        },
        {
            "change_id": "ctrl.higher-accuracy",
            "title": "Accuracy rose",
            "metric_id": "accuracy",
            "higher_is_better": True,
            "baseline_value": 0.70,
            "baseline_anchor": "fixtures/positive_net baseline/accuracy",
            "post_value": 0.90,
            "post_anchor": "fixtures/positive_net post/accuracy",
            "n": 5,
            "source": "fixture.positive_net_with_regression",
        },
        {
            "change_id": "ctrl.more-errors",
            "title": "Error rate worsened (must remain listed)",
            "metric_id": "error_rate",
            "higher_is_better": False,
            "baseline_value": 0.02,
            "baseline_anchor": "fixtures/positive_net baseline/error_rate",
            "post_value": 0.08,
            "post_anchor": "fixtures/positive_net post/error_rate",
            "n": 5,
            "source": "fixture.positive_net_with_regression",
        },
    ],
}


def interval_or_statement(n: int | None) -> str:
    nn = 0 if n is None else int(n)
    if nn < MIN_N_FOR_INTERVAL:
        return (
            f"n is too small for a confidence interval (n={nn}; "
            f"need n>={MIN_N_FOR_INTERVAL} independent replicates)"
        )
    return N_TOO_SMALL.format(min_n=MIN_N_FOR_INTERVAL)


def classify_raw(
    *,
    baseline_value: float | None,
    post_value: float | None,
    higher_is_better: bool,
    n: int | None,
    noise_abs: float = NOISE_ABS_DEFAULT,
) -> dict[str, Any]:
    """Return verdict, delta, interval statement, captured flags.

    Missing baseline => UNMEASURED, even when a post value exists.
    Missing post => UNMEASURED. Never fold either hole into NEUTRAL.
    """
    baseline_captured = baseline_value is not None
    post_captured = post_value is not None
    stmt = interval_or_statement(n)
    if not baseline_captured:
        return {
            "verdict": "UNMEASURED",
            "delta": None,
            "interval_or_statement": (
                "n is too small for a confidence interval: baseline was never "
                "captured (n=0 on the pre-change arm). UNMEASURED, not NEUTRAL."
            ),
            "baseline_captured": False,
            "post_captured": post_captured,
        }
    if not post_captured:
        return {
            "verdict": "UNMEASURED",
            "delta": None,
            "interval_or_statement": (
                "n is too small for a confidence interval: post value was never "
                "captured (n=0 on the post-change arm). UNMEASURED, not NEUTRAL."
            ),
            "baseline_captured": True,
            "post_captured": False,
        }
    delta = float(post_value) - float(baseline_value)
    signed = delta if higher_is_better else -delta
    if abs(signed) <= float(noise_abs):
        verdict = "NEUTRAL"
    elif signed > 0:
        verdict = "IMPROVED"
    else:
        verdict = "REGRESSED"
    return {
        "verdict": verdict,
        "delta": delta,
        "interval_or_statement": stmt,
        "baseline_captured": True,
        "post_captured": True,
    }


def empty_counts() -> dict[str, int]:
    return {
        "IMPROVED": 0,
        "NEUTRAL": 0,
        "REGRESSED": 0,
        "UNMEASURED": 0,
        "total": 0,
    }


def verdict_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = empty_counts()
    for row in rows:
        v = str(row.get("verdict") or "")
        if v not in VERDICTS:
            raise ValueError(f"row missing a legal verdict: {row.get('change_id')} {v!r}")
        counts[v] += 1
    counts["total"] = len(rows)
    if (
        counts["IMPROVED"]
        + counts["NEUTRAL"]
        + counts["REGRESSED"]
        + counts["UNMEASURED"]
        != counts["total"]
    ):
        raise ValueError("verdict counts do not sum to total")
    return counts


def derive_net(counts: dict[str, int]) -> str:
    total = int(counts.get("total") or 0)
    improved = int(counts.get("IMPROVED") or 0)
    regressed = int(counts.get("REGRESSED") or 0)
    unmeasured = int(counts.get("UNMEASURED") or 0)
    if total == 0:
        return "UNMEASURED"
    polarity = improved - regressed
    if polarity > 0:
        return "IMPROVED"
    if polarity < 0:
        return "REGRESSED"
    if unmeasured == total:
        return "UNMEASURED"
    if unmeasured > 0 and improved == 0 and regressed == 0:
        return "UNMEASURED"
    return "NEUTRAL"


def regressions_listed(rows: list[dict[str, Any]]) -> list[str]:
    return [str(r["change_id"]) for r in rows if r.get("verdict") == "REGRESSED"]


def publish_row(raw: dict[str, Any]) -> dict[str, Any]:
    classified = classify_raw(
        baseline_value=raw.get("baseline_value"),
        post_value=raw.get("post_value"),
        higher_is_better=bool(raw.get("higher_is_better")),
        n=raw.get("n"),
        noise_abs=float(raw.get("noise_abs") or NOISE_ABS_DEFAULT),
    )
    n = int(raw.get("n") or 0)
    return {
        "change_id": str(raw["change_id"]),
        "title": str(raw.get("title") or raw["change_id"]),
        "metric_id": str(raw.get("metric_id") or "unspecified-metric"),
        "higher_is_better": bool(raw.get("higher_is_better")),
        "baseline": {
            "value": raw.get("baseline_value"),
            "anchor": str(raw.get("baseline_anchor") or "unspecified"),
            "captured": classified["baseline_captured"],
        },
        "post": {
            "value": raw.get("post_value"),
            "anchor": str(raw.get("post_anchor") or "unspecified"),
            "captured": classified["post_captured"],
        },
        "delta": classified["delta"],
        "n": n,
        "interval_or_statement": classified["interval_or_statement"],
        "verdict": classified["verdict"],
        "source": str(raw.get("source") or "unspecified"),
    }


def evaluate(raw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not raw_rows:
        raise ValueError("evaluate requires at least one change row")
    changes = [publish_row(r) for r in raw_rows]
    counts = verdict_counts(changes)
    net_verdict = derive_net(counts)
    recomputed = derive_net(verdict_counts(changes))
    if recomputed != net_verdict:
        raise RuntimeError("net derivation is not a function of the published rows")
    listed = regressions_listed(changes)
    return {
        "changes": changes,
        "verdict_counts": counts,
        "net": {
            "verdict": net_verdict,
            "derivation": DERIVATION,
            "recomputes_from_published_rows": True,
            "counts": counts,
        },
        "regressions_listed": listed,
    }


def recompute_net_from_published(changes: list[dict[str, Any]]) -> str:
    """Net from the published table only (the reviewer recomputation)."""
    return derive_net(verdict_counts(changes))


def recompute_row_verdict_from_published(row: dict[str, Any]) -> str:
    """Re-classify a published row from its baseline/post arms."""
    baseline = row.get("baseline") or {}
    post = row.get("post") or {}
    bval = baseline.get("value") if baseline.get("captured") else None
    pval = post.get("value") if post.get("captured") else None
    classified = classify_raw(
        baseline_value=bval,
        post_value=pval,
        higher_is_better=bool(row.get("higher_is_better")),
        n=row.get("n"),
    )
    return str(classified["verdict"])


def assert_table_internally_consistent(bundle: dict[str, Any]) -> None:
    changes = bundle["changes"]
    for row in changes:
        expected = recompute_row_verdict_from_published(row)
        if row.get("verdict") != expected:
            raise AssertionError(
                f"{row.get('change_id')} published {row.get('verdict')} "
                f"but recomputes to {expected}"
            )
        if not row.get("verdict"):
            raise AssertionError(f"{row.get('change_id')} has empty verdict")
    counts = verdict_counts(changes)
    if counts != bundle["verdict_counts"]:
        raise AssertionError("published verdict_counts disagree with the rows")
    net = recompute_net_from_published(changes)
    if net != bundle["net"]["verdict"]:
        raise AssertionError(
            f"published net {bundle['net']['verdict']} recomputes to {net}"
        )
    expected_listed = regressions_listed(changes)
    if list(bundle.get("regressions_listed") or []) != expected_listed:
        raise AssertionError("regressions_listed disagrees with REGRESSED rows")
