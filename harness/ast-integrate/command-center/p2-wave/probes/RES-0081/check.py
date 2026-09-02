"""Mechanical contract for RES-0081 literature extraction.

A headline number without its baseline cannot promote a mechanism (catalog
evidence_requirement). Metric definitions that are identical across studies
are a contract fail because the catalog forbids collapsing them.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parents[3]
ART = REPO / "command-center/research/RES-0081.json"
CATALOG_SENTINEL = (
    "SUCCESS:RES-0081 in the receipt AND a per-study flip-rate table with each "
    "study's metric definition and one failed mitigation"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
FAILED_MITIGATION = frozenset(
    {"FAILED", "DID-NOT-REPLICATE", "INCREASED", "DID-NOT-RESOLVE"}
)
REQUIRED_ROW = (
    "study_id",
    "citation",
    "arxiv_id",
    "locator",
    "metric_definition",
    "effect_size",
    "baseline",
    "evidence_tier",
)


def load_artifact(path: Path | None = None) -> dict[str, Any]:
    p = path or ART
    if not p.is_file() or p.stat().st_size <= 0:
        raise SystemExit("FAILED:RES-0081 artifact missing")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:RES-0081 artifact not an object")
    return doc


def text_of(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=True)


def promotable(row: dict[str, Any] | None) -> bool:
    """Catalog rule: effect size AND baseline; missing baseline is E3 and cannot promote."""
    if not isinstance(row, dict):
        return False
    effect = str(row.get("effect_size") or "").strip()
    baseline = str(row.get("baseline") or "").strip()
    if not effect or not baseline:
        return False
    if str(row.get("evidence_tier") or "").upper() in {"E4"}:
        return False
    if str(row.get("headline_without_baseline") or "").lower() in {"true", "1"}:
        return False
    return True


def classify_missing_baseline(row: dict[str, Any]) -> str:
    """A number with no baseline is recorded as E3 (cannot promote)."""
    effect = str(row.get("effect_size") or "").strip()
    baseline = str(row.get("baseline") or "").strip()
    if effect and not baseline:
        return "E3"
    return str(row.get("evidence_tier") or "E3")


def flip_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows = doc.get("flip_rate_table") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def mitigations(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows = doc.get("mitigations") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def required_fields_ok(row: dict[str, Any]) -> list[str]:
    missing = [k for k in REQUIRED_ROW if not str(row.get(k) or "").strip()]
    return missing


def distinct_metric_definitions(rows: list[dict[str, Any]]) -> set[str]:
    return {str(r.get("metric_definition") or "").strip() for r in rows if str(r.get("metric_definition") or "").strip()}


def failed_mitigations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        status = str(r.get("status") or r.get("outcome") or "").upper()
        if status in FAILED_MITIGATION:
            out.append(r)
            continue
        if r.get("failed") is True:
            out.append(r)
    return out


def reviewer_partitions(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    revs = doc.get("reviewers") or []
    if not isinstance(revs, list) or len(revs) < 2:
        return [], "need two partitioned reviewers"
    usable = [r for r in revs if isinstance(r, dict)]
    if len(usable) < 2:
        return [], "need two reviewer objects"
    sets: list[set[str]] = []
    vendors: list[str] = []
    for r in usable[:2]:
        part = r.get("source_partition") or r.get("partition") or []
        if not isinstance(part, list) or len(part) < 1:
            return [], f"reviewer {r.get('reviewer_id')} empty partition"
        ids = {str(x) for x in part if str(x).strip()}
        if not ids:
            return [], "empty source ids"
        sets.append(ids)
        vendors.append(str(r.get("vendor") or "").strip().lower())
    if sets[0] & sets[1]:
        return [], f"partitions overlap: {sorted(sets[0] & sets[1])}"
    if vendors[0] and vendors[1] and vendors[0] == vendors[1]:
        return [], f"same-vendor reviewers on partitioned evidence: {vendors[0]}"
    return usable[:2], None


def baseline_stripped_mutant(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    for row in flip_rows(mutant):
        row["baseline"] = ""
        row["headline_without_baseline"] = True
        row["evidence_tier"] = classify_missing_baseline(row)
    for mech in mutant.get("mechanisms") or []:
        if isinstance(mech, dict):
            mech["baseline"] = ""
            mech["headline_without_baseline"] = True
            mech["evidence_tier"] = "E3"
            mech["promoted"] = False
    return mutant


def promoted_mechanisms(doc: dict[str, Any]) -> list[dict[str, Any]]:
    mechs = doc.get("mechanisms") or []
    if not isinstance(mechs, list):
        return []
    out = []
    for m in mechs:
        if not isinstance(m, dict):
            continue
        if m.get("promoted") is True and promotable(m):
            out.append(m)
        elif m.get("promoted") is True and not promotable(m):
            raise SystemExit(
                f"FAILED:RES-0081 promoted mechanism missing baseline: {m.get('id')}"
            )
    return out
