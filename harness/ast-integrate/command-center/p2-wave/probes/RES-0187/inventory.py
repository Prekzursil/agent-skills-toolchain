"""Extract major conclusions from on-disk research claim arrays."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from classify import classify
from contract import RESEARCH_ROOT, SKIP_NAMES


def research_json_files(repo: Path) -> list[Path]:
    root = repo / RESEARCH_ROOT
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*.json")):
        if path.name in SKIP_NAMES:
            continue
        out.append(path)
    return out


def conclusion_text(row: dict) -> str:
    for key in ("canonical_mechanism", "claim", "text", "answer"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def conclusion_id(rel: str, row: dict) -> str:
    cid = str(row.get("claim_id") or row.get("id") or "").strip()
    return f"{rel}::{cid}" if cid else f"{rel}::anon"


def extract_claims_array(doc: Any, rel: str) -> list[dict]:
    rows: list[dict] = []
    claims = doc.get("claims") if isinstance(doc, dict) else None
    if not isinstance(claims, list):
        return rows
    for row in claims:
        if not isinstance(row, dict):
            continue
        text = conclusion_text(row)
        cid = str(row.get("claim_id") or row.get("id") or "").strip()
        if not cid or not text:
            continue
        rows.append(
            {
                "id": conclusion_id(rel, row),
                "claim_id": cid,
                "source_path": rel,
                "text": text,
                "raw": row,
            }
        )
    return rows


def extract_via_id_scan(doc: Any, rel: str) -> list[str]:
    """Second extractor: ids of dicts directly under claims[], no recursion.

    Independent of extract_claims_array's text-field preference: any child
    object with claim_id or id is counted. Used as a confirmatory signal.
    """
    ids: list[str] = []
    claims = doc.get("claims") if isinstance(doc, dict) else None
    if not isinstance(claims, list):
        return ids
    for row in claims:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("claim_id") or row.get("id") or "").strip()
        if cid:
            ids.append(conclusion_id(rel, row))
    return ids


def load_population(repo: Path) -> dict:
    files: list[dict] = []
    conclusions: list[dict] = []
    scan_ids: list[str] = []
    for path in research_json_files(repo):
        rel = path.relative_to(repo).as_posix()
        raw = path.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            files.append(
                {
                    "path": rel,
                    "present": True,
                    "parseable": False,
                    "claim_n": 0,
                }
            )
            continue
        extracted = extract_claims_array(doc, rel)
        scan_ids.extend(extract_via_id_scan(doc, rel))
        files.append(
            {
                "path": rel,
                "present": True,
                "parseable": True,
                "claim_n": len(extracted),
                "duplicate_table": (
                    "mechanisms" if isinstance(doc, dict) and isinstance(doc.get("mechanisms"), list) else None
                ),
            }
        )
        conclusions.extend(extracted)

    audited: list[dict] = []
    for item in conclusions:
        verdict = classify(item["raw"])
        audited.append(
            {
                "id": item["id"],
                "claim_id": item["claim_id"],
                "source_path": item["source_path"],
                "text": item["text"],
                "status": verdict["status"],
                "reason": verdict["reason"],
                "hedge_mention": verdict["hedge_mention"],
                "found_at": verdict["found_at"],
                "record": verdict["record"],
            }
        )

    challenged = [r for r in audited if r["status"] == "CHALLENGED"]
    unchallenged = [r for r in audited if r["status"] == "UNCHALLENGED"]
    n = len(audited)
    coverage = (len(challenged) / n) if n else None
    scan_set = set(scan_ids)
    extract_set = {r["id"] for r in audited}
    return {
        "files": files,
        "conclusions": audited,
        "challenged": challenged,
        "unchallenged": unchallenged,
        "n": n,
        "challenged_n": len(challenged),
        "unchallenged_n": len(unchallenged),
        "coverage_fraction": coverage,
        "extractor_agreement": {
            "claims_array_ids": sorted(extract_set),
            "id_scan_ids": sorted(scan_set),
            "agree": extract_set == scan_set,
            "n_claims_array": len(extract_set),
            "n_id_scan": len(scan_set),
        },
    }
