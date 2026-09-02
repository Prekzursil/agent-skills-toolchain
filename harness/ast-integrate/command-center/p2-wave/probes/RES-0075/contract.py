"""Mechanical graders for RES-0075 Delphi claim records.

Grading rule (stated before any promotion): a mechanism may be labelled
empirically-supported only when evidence_tier is E1 or E2 AND the row
carries a reported effect_size AND a reported baseline. A headline number
without its baseline is recorded as E3 and cannot promote a mechanism.
Failure modes are held to the same four-field bar (doi_or_arxiv, locator,
effect_size, baseline). Claims that fail the bar default to REFUTED as
design inputs.
"""
from __future__ import annotations

from typing import Any, Mapping

GRADING_RULE = (
    "a mechanism may be labelled empirically-supported only when "
    "evidence_tier is E1 or E2 AND the row carries a reported effect_size "
    "AND a reported baseline; a headline number without its baseline is "
    "recorded as E3 and cannot promote a mechanism"
)

PROMOTING_TIERS = frozenset({"E1", "E2"})
NOT_PROMOTING = frozenset({"E3", "E4"})
RULE_CLASSES = frozenset({"empirically-supported", "conventional"})
REQUIRED_CLAIM = (
    "id",
    "text",
    "canonical_mechanism",
    "source_lineage",
    "evidence_tier",
    "confidence_band",
    "settling_probe",
    "effect_size",
    "baseline",
    "locator",
    "verdict",
    "strongest_caveat",
    "freshness_stamp",
    "snapshot_sha256",
)
REQUIRED_LINEAGE = ("doi_or_arxiv", "title", "year", "url")
SENTINEL = "SUCCESS:RES-0075"
SPLIT_PHRASE = (
    "rule list split into empirically-supported and conventional"
)


ABSENT_METRIC_PREFIXES = (
    "not reported",
    "none isolated",
    "none (",
    "n/a",
    "na",
    "null",
    "unknown",
)


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return bool(value)
    return True


def _metric_present(value: Any) -> bool:
    if not _nonempty(value):
        return False
    text = str(value).strip().lower()
    if text in {"none", "n/a", "na", "null", "unknown", "-"}:
        return False
    return not any(text.startswith(p) for p in ABSENT_METRIC_PREFIXES)


def citation_complete(row: Mapping[str, Any]) -> bool:
    lineage = row.get("source_lineage") or {}
    doi = ""
    if isinstance(lineage, Mapping):
        doi = str(lineage.get("doi_or_arxiv") or "").strip()
    else:
        doi = str(row.get("doi_or_arxiv") or "").strip()
    locator = str(row.get("locator") or "").strip()
    return bool(doi) and bool(locator)


def has_effect_and_baseline(row: Mapping[str, Any]) -> bool:
    return _metric_present(row.get("effect_size")) and _metric_present(
        row.get("baseline")
    )


def demote_headline_without_baseline(row: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a row; missing baseline forces E3 and blocks promotion."""
    out = dict(row)
    lineage = out.get("source_lineage")
    if isinstance(lineage, Mapping):
        out["source_lineage"] = dict(lineage)
    if not has_effect_and_baseline(out):
        out["evidence_tier"] = "E3"
        out["verdict"] = "REFUTED"
        out["promotable"] = False
        out["promotion_block"] = "headline-without-baseline"
    return out


def can_promote(row: Mapping[str, Any]) -> bool:
    if str(row.get("verdict") or "").upper() == "REFUTED":
        return False
    tier = str(row.get("evidence_tier") or "").upper()
    if tier not in PROMOTING_TIERS:
        return False
    if not citation_complete(row):
        return False
    if not has_effect_and_baseline(row):
        return False
    return True


def classify_rule(row: Mapping[str, Any]) -> str:
    declared = str(row.get("rule_class") or "").strip()
    if declared == "conventional":
        return "conventional"
    if can_promote(row):
        return "empirically-supported"
    return "conventional" if declared == "conventional" else "not-promoted"


def failure_mode_ok(row: Mapping[str, Any]) -> bool:
    if not citation_complete(row):
        return False
    if not has_effect_and_baseline(row):
        return False
    tier = str(row.get("evidence_tier") or "").upper()
    if tier not in PROMOTING_TIERS:
        return False
    return True


def required_fields_ok(row: Mapping[str, Any]) -> list[str]:
    missing = [k for k in REQUIRED_CLAIM if k not in row]
    lineage = row.get("source_lineage")
    if not isinstance(lineage, Mapping):
        missing.append("source_lineage")
        return missing
    for k in REQUIRED_LINEAGE:
        if not _nonempty(lineage.get(k)):
            missing.append(f"source_lineage.{k}")
    return missing
