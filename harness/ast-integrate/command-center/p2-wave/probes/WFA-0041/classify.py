"""Classify benchmark evidence: CITABLE, CLAIMED-NOT-FOUND, or HONEST-NULL.

Never emits a numeric quality score. An empty benchmark column is the correct
output when there is no citable run record.
"""
from __future__ import annotations

from typing import Any

from run_records import locate

CITABLE = "CITABLE"
CLAIMED_NOT_FOUND = "CLAIMED-NOT-FOUND"
HONEST_NULL = "HONEST-NULL"

CLAIM_KEYS = frozenset(
    {
        "bench",
        "benchmark",
        "benchmarks",
        "benchmark_evidence",
        "bench_path",
        "run_record",
        "run_receipt",
        "run_id",
        "benchmark_receipt",
    }
)
CLAIM_NEEDLES = (
    "benchmark-receipt",
    "benchmark_receipt",
    "bench-run",
    "bench_run",
    "run-record",
    "run_record",
    "citable benchmark",
)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _walk_claim_payload(value: Any, acc: list[Any]) -> None:
    if _is_empty(value):
        return
    if isinstance(value, dict):
        hit_key = False
        for key, item in value.items():
            lk = str(key).lower()
            if lk in CLAIM_KEYS and not _is_empty(item):
                acc.append({key: item})
                hit_key = True
            else:
                _walk_claim_payload(item, acc)
        if not hit_key:
            text = " ".join(str(k) for k in value.keys()).lower()
            blob = str(value).lower()
            if any(n in text or n in blob for n in CLAIM_NEEDLES):
                acc.append(value)
        return
    if isinstance(value, list):
        for item in value:
            _walk_claim_payload(item, acc)
        return
    if isinstance(value, str):
        low = value.lower()
        if any(n in low for n in CLAIM_NEEDLES) or any(
            n in low for n in ("benchmark",)
        ):
            # Bare "score"/"quality" prose is not a named benchmark.
            if "benchmark" in low or any(n in low for n in CLAIM_NEEDLES):
                acc.append(value)


def extract_claims(evidence: Any, bench: Any) -> list[Any]:
    claims: list[Any] = []
    if not _is_empty(bench):
        claims.append(bench)
    _walk_claim_payload(evidence, claims)
    return claims


def classify_row(
    *,
    candidate_id: str,
    evidence: Any,
    bench: Any = None,
    roots: list | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claims = extract_claims(evidence, bench)
    locations = [locate(c, roots) for c in claims]
    found = [loc for loc in locations if loc.get("found")]
    row: dict[str, Any] = {
        "id": candidate_id,
        "claims": len(claims),
        "benchmark": None,
        "score": None,
        "quality_score": None,
        "inferred_score": None,
    }
    if extra:
        row.update(extra)
    if found:
        rec = found[0]["record"]
        row["status"] = CITABLE
        row["benchmark"] = {
            "run_record_path": rec["path"],
            "sha256": rec["sha256"],
            "bytes": rec["bytes"],
        }
        return row
    if claims:
        row["status"] = CLAIMED_NOT_FOUND
        row["benchmark"] = {
            "claimed": True,
            "run_record_path": None,
            "reason": "named-benchmark-has-no-locatable-run-record",
        }
        return row
    row["status"] = HONEST_NULL
    row["benchmark"] = None
    return row


SCORE_KEYS = ("score", "quality_score", "inferred_score", "rating")


def manufactured_score(row: dict[str, Any]) -> bool:
    """True if a numeric quality score was invented for the candidate."""
    for key in SCORE_KEYS:
        val = row.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return True
    bench = row.get("benchmark")
    if isinstance(bench, dict):
        for key in SCORE_KEYS:
            val = bench.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return True
    return False
