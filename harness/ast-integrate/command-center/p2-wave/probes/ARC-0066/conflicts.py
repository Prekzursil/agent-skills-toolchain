#!/usr/bin/env python3
"""Mechanical conflict / recusal detector.

A judge is NOT independent of an artifact if any of:
  * judge_id equals the artifact's provenance author_id
  * judge vendor equals the artifact's provenance/produced_by vendor
  * judge vendor equals the catalog assignment vendor (incl. co-assignments)

Self-declaration is ignored. Missing provenance does not invent an author;
catalog assignment still binds. Recusal reasons are for the dispatch layer
and must not be shown to the judge (they would identify the author).
"""
from __future__ import annotations

from census import norm


def _catalog_vendors(row: dict) -> set[str]:
    cat = row.get("catalog") or {}
    out = set()
    for item in cat.get("vendors") or []:
        n = norm(item)
        if n:
            out.add(n)
    single = norm(cat.get("vendor"))
    if single:
        out.add(single)
    return out


def recusal(judge: dict, row: dict) -> dict:
    reasons: list[dict] = []
    jid = str(judge.get("judge_id") or "")
    jv = norm(judge.get("vendor"))
    auth = row.get("authorship") or {}
    aid = str(auth.get("author_id") or "")
    if jid and aid and jid == aid:
        reasons.append({"code": "AUTHOR_ID_MATCH", "judge_id": jid})
    av = norm(auth.get("vendor"))
    if jv and av and jv == av:
        reasons.append(
            {
                "code": "PROVENANCE_VENDOR",
                "vendor": auth.get("vendor"),
                "source_field": auth.get("source_field"),
            }
        )
    if jv:
        for cv in sorted(_catalog_vendors(row)):
            if jv == cv:
                reasons.append({"code": "CATALOG_VENDOR", "vendor": cv})
                break
    recused = bool(reasons)
    return {
        "judge_id": jid or None,
        "artifact_unit_id": row.get("unit_id"),
        "artifact_path": row.get("path"),
        "recused": recused,
        "eligible": not recused,
        "reasons": reasons,
        "provenance_gap": row.get("provenance_gap"),
    }


def matrix(judges: list[dict], rows: list[dict]) -> list[dict]:
    return [recusal(j, r) for r in rows for j in judges]


def eligible_judges(judges: list[dict], row: dict) -> list[dict]:
    return [j for j in judges if recusal(j, row)["eligible"]]


def quorum_check(judges: list[dict], row: dict, minimum: int) -> dict:
    eligible = eligible_judges(judges, row)
    n = len(eligible)
    return {
        "unit_id": row.get("unit_id"),
        "path": row.get("path"),
        "present": bool(row.get("present")),
        "eligible_count": n,
        "minimum": minimum,
        "ok": n >= minimum,
        "void": n < minimum,
        "eligible_judge_ids": [j.get("judge_id") for j in eligible],
    }
