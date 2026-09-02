#!/usr/bin/env python3
"""Executable rapid vs systematic protocols over harvested snapshots.

Declared parameter diffs (not labels):
  databases, grey_literature, contradiction_search, dual_screen, max_records.

Rapid: pubmed only, quota 2 newest, no grey, no contradiction search,
single-screen (prose phrase only).

Systematic: all listed databases, no quota, grey allowed, contradiction
search includes dissenting sources, dual-screen (prose phrase AND paired
Crossref JSON phrase).
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from catalog import CLAIMS, RAPID_PARAMS, SOURCES, SYSTEMATIC_PARAMS
from capture import body_text, load_index


def params_fingerprint(params: dict[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def rail_map(index: dict | None = None) -> dict[str, dict]:
    idx = index if index is not None else load_index()
    return {row["id"]: row for row in (idx.get("rails") or [])}


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def select_sources(
    question_id: str,
    params: dict[str, Any],
    *,
    kinds: set[str] | None = None,
) -> list[dict[str, Any]]:
    dbs = set(params["databases"])
    allowed_kinds = kinds or {"prose-source", "structured-api"}
    rows = []
    for src in SOURCES:
        if src["kind"] not in allowed_kinds:
            continue
        if question_id not in src["questions"]:
            continue
        if not dbs.intersection(src["databases"]):
            continue
        if not params["grey_literature"] and src["grey"]:
            continue
        if not params["contradiction_search"] and src["dissenting"]:
            continue
        if params.get("year_min") is not None and src["year"] < params["year_min"]:
            continue
        rows.append(src)
    rows.sort(key=lambda s: (-int(s["year"]), s["id"]))
    quota = params.get("max_records")
    if quota is not None:
        if "prose-source" in allowed_kinds and "structured-api" not in allowed_kinds:
            rows = rows[: int(quota)]
        elif allowed_kinds == {"prose-source", "structured-api"}:
            prose = [r for r in rows if r["kind"] == "prose-source"][: int(quota)]
            keep = {r["id"] for r in prose}
            for r in rows:
                if r["kind"] == "structured-api" and r.get("pairs_with") in keep:
                    keep.add(r["id"])
            rows = [r for r in rows if r["id"] in keep]
    return rows


def extract_claims(
    question_id: str,
    params: dict[str, Any],
    index: dict | None = None,
) -> list[dict[str, Any]]:
    rails = rail_map(index)
    selected = {s["id"] for s in select_sources(question_id, params)}
    out: list[dict[str, Any]] = []
    for spec in CLAIMS:
        if spec["question_id"] != question_id:
            continue
        sid = spec["source_id"]
        if sid not in selected:
            continue
        prose = body_text(sid)
        if not _contains(prose, spec["phrase"]):
            continue
        structured_ok = None
        struct_id = spec.get("structured_source_id")
        struct_phrase = spec.get("structured_phrase")
        if struct_id and struct_phrase:
            structured_ok = _contains(body_text(struct_id), struct_phrase)
        if params["dual_screen"]:
            if struct_id is None or not structured_ok:
                continue
        rail = rails.get(sid) or {}
        struct_rail = rails.get(struct_id) if struct_id else None
        signals = [
            {
                "id": f"{spec['id']}-prose",
                "kind": "prose-source",
                "source_id": sid,
                "permalink": rail.get("final_url") or rail.get("permalink"),
                "fetch_timestamp": rail.get("fetched_at"),
                "http_status": rail.get("http_status"),
                "sha256": rail.get("sha256"),
                "observation": f"phrase {spec['phrase']!r} present in snapshot",
            }
        ]
        if struct_id and struct_rail:
            signals.append(
                {
                    "id": f"{spec['id']}-structured-api",
                    "kind": "structured-api",
                    "source_id": struct_id,
                    "permalink": struct_rail.get("final_url")
                    or struct_rail.get("permalink"),
                    "fetch_timestamp": struct_rail.get("fetched_at"),
                    "http_status": struct_rail.get("http_status"),
                    "sha256": struct_rail.get("sha256"),
                    "observation": (
                        f"phrase {struct_phrase!r} present in Crossref JSON"
                        if structured_ok
                        else "paired Crossref JSON lacked structured_phrase"
                    ),
                }
            )
        out.append(
            {
                "id": spec["id"],
                "question_id": question_id,
                "text": spec["text"],
                "would_change_decision": bool(spec["would_change_decision"]),
                "sherman_kent_band": spec["sherman_kent_band"],
                "independent_verification_path": (
                    "command-center/p2-wave/probes/RES-0192/probe2_parameter_and_lineage.py"
                ),
                "source_id": sid,
                "structured_source_id": struct_id,
                "phrase": spec["phrase"],
                "dual_screen_passed": bool(structured_ok)
                if params["dual_screen"]
                else None,
                "lineage": {
                    "resolved_url": rail.get("final_url") or rail.get("permalink"),
                    "fetch_timestamp": rail.get("fetched_at"),
                    "sha256": rail.get("sha256"),
                    "http_status": rail.get("http_status"),
                    "snapshot": rail.get("snapshot"),
                },
                "signals": signals,
            }
        )
    out.sort(key=lambda c: c["id"])
    return out


def diff_claims(
    rapid: list[dict[str, Any]],
    systematic: list[dict[str, Any]],
) -> dict[str, Any]:
    r_ids = {c["id"] for c in rapid}
    s_ids = {c["id"] for c in systematic}
    missed_ids = sorted(s_ids - r_ids)
    extra_rapid = sorted(r_ids - s_ids)
    by_id = {c["id"]: c for c in systematic}
    missed = []
    for cid in missed_ids:
        row = by_id[cid]
        missed.append(
            {
                "id": cid,
                "text": row["text"],
                "would_change_decision": row["would_change_decision"],
                "source_id": row["source_id"],
                "sherman_kent_band": row["sherman_kent_band"],
            }
        )
    decision_relevant = [m for m in missed if m["would_change_decision"]]
    return {
        "rapid_claim_ids": sorted(r_ids),
        "systematic_claim_ids": sorted(s_ids),
        "missed_by_rapid": missed,
        "decision_relevant_misses": decision_relevant,
        "n_missed": len(missed),
        "n_decision_relevant_misses": len(decision_relevant),
        "extra_in_rapid_not_systematic": extra_rapid,
        "negative_control_rapid_complete": len(decision_relevant) == 0,
    }


def run_question(question: dict[str, Any], index: dict | None = None) -> dict[str, Any]:
    qid = question["id"]
    rapid = extract_claims(qid, RAPID_PARAMS, index)
    systematic = extract_claims(qid, SYSTEMATIC_PARAMS, index)
    return {
        "question_id": qid,
        "question": question["text"],
        "decision": question["decision"],
        "factors": dict(question["factors"]),
        "rapid_params": deepcopy(RAPID_PARAMS),
        "systematic_params": deepcopy(SYSTEMATIC_PARAMS),
        "rapid_fingerprint": params_fingerprint(RAPID_PARAMS),
        "systematic_fingerprint": params_fingerprint(SYSTEMATIC_PARAMS),
        "rapid_claims": rapid,
        "systematic_claims": systematic,
        "diff": diff_claims(rapid, systematic),
        "selected_rapid_sources": [
            s["id"]
            for s in select_sources(qid, RAPID_PARAMS, kinds={"prose-source"})
        ],
        "selected_systematic_sources": [
            s["id"]
            for s in select_sources(qid, SYSTEMATIC_PARAMS, kinds={"prose-source"})
        ],
    }


params_fingerprint = params_fingerprint
extract_claims = extract_claims
run_question = run_question
params_fingerprint = params_fingerprint
extract_claims = extract_claims
