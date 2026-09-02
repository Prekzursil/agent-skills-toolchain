"""Refuse overclaim on the RES-0022 contradiction table."""
from __future__ import annotations

from typing import Any


def hunt_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain hunt lives under report on a receipt-shaped artifact."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("contradiction_table"), list):
        view = dict(report)
        for key in ("state", "sentinel", "unit_id"):
            if key in doc:
                view[key] = doc[key]
        return view
    return doc


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "doc-not-object"
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{state}"
    view = hunt_view(doc)
    table = view.get("contradiction_table")
    if not isinstance(table, list) or len(table) < 20:
        return False, "table-short"
    counts = view.get("counts")
    if not isinstance(counts, dict):
        return False, "counts-missing"
    consistent = 0
    contradicted = 0
    not_checked = 0
    ids: list[str] = []
    for i, row in enumerate(table):
        if not isinstance(row, dict):
            return False, f"row[{i}]-not-object"
        sid = str(row.get("id") or "")
        if not sid:
            return False, f"row[{i}]-no-id"
        ids.append(sid)
        verdict = str(row.get("verdict") or "")
        sha = str(row.get("doc_sha256") or "")
        cmd = str(row.get("reproducing_command") or "")
        out = str(row.get("command_output") or "")
        if len(sha) != 64:
            return False, f"{sid}-sha256-missing"
        if len(cmd) < 16:
            return False, f"{sid}-command-missing"
        if len(out) < 8:
            return False, f"{sid}-output-missing"
        if verdict == "CONTRADICTED":
            contradicted += 1
            klass = str(row.get("classification") or "")
            if klass not in {"doc_stale", "behaviour_regression", "reader_wrong"}:
                return False, f"{sid}-contradicted-without-classification"
        elif verdict == "CONSISTENT":
            consistent += 1
        elif verdict == "NOT-CHECKED":
            not_checked += 1
        else:
            return False, f"{sid}-bad-verdict"
    if len(set(ids)) != len(ids):
        return False, "duplicate-ids"
    try:
        if int(counts["consistent_count"]) != consistent:
            return False, "consistent-count-drift"
        if int(counts["contradicted_count"]) != contradicted:
            return False, "contradicted-count-drift"
        if int(counts["not_checked_count"]) != not_checked:
            return False, "not-checked-count-drift"
    except (KeyError, TypeError, ValueError):
        return False, "counts-missing-ints"
    if consistent < 3:
        return False, "fewer-than-3-consistent"
    if str(view.get("verdict") or "") == "CONFIRMED" and contradicted:
        return False, "CONFIRMED-with-contradictions"
    if str(view.get("verdict") or "") == "REFUTED" and contradicted == 0:
        return False, "REFUTED-with-zero-contradictions"
    reviewers = view.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        return False, "reviewers-missing"
    parts = []
    for rev in reviewers:
        if not isinstance(rev, dict) or rev.get("independent") is not True:
            return False, "reviewer-not-independent"
        part = list(rev.get("partition") or [])
        if len(part) < 8:
            return False, "reviewer-partition-short"
        parts.append(set(part))
    if parts[0] & parts[1]:
        return False, "reviewer-partitions-overlap"
    if "SUCCESS:RES-0022" not in str(doc.get("sentinel") or "") and "SUCCESS:RES-0022" not in str(
        view.get("answer") or ""
    ):
        return False, "sentinel-absent"
    return True, f"ok consistent={consistent} contradicted={contradicted} not_checked={not_checked}"
