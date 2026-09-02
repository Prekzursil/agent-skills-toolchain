"""Structural checks for the RES-0120 teardown artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from grade import MEASURED, cited_as_measured, grade_claim, rail_ok

SENTINEL = "SUCCESS:RES-0120"
COMPLETION = (
    "SUCCESS:RES-0120 in the receipt AND a teardown naming >=3 competitor "
    "advantages with evidence plus an overlap list against this program's "
    "planned features"
)
BLOCKED = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
UID = "RES-0120"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check(doc: dict[str, Any], repo: Path) -> tuple[bool, str]:
    if doc.get("unit_id") != UID:
        return False, "unit_id"
    state = str(doc.get("state") or "").upper()
    if state in BLOCKED:
        return False, f"self-declared:{state}"
    if SENTINEL not in str(doc.get("sentinel") or ""):
        return False, "sentinel"
    raw = json.dumps(doc, ensure_ascii=False)
    if COMPLETION not in raw:
        return False, "completion-sentinel-text"

    competitor = doc.get("closest_whole_product_competitor") or {}
    if str(competitor.get("name") or "") != "Claude Code":
        return False, "competitor-name"
    if str(competitor.get("kind") or "") != "shipping-product":
        return False, "competitor-kind"

    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-short"
    by_id = {}
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-type"
        live = grade_claim(row)
        recorded = str(row.get("grade") or "")
        if live != recorded:
            return False, f"claims[{i}]-grade-drift:{recorded}!={live}"
        if cited_as_measured(row) and live != MEASURED:
            return False, f"claims[{i}]-e3-cited-as-fact"
        if live == MEASURED:
            kinds = {str(r.get("kind")) for r in row["rails"] if rail_ok(r)}
            if "structured_api" not in kinds or "prose_source" not in kinds:
                return False, f"claims[{i}]-rail-kinds"
        by_id[row.get("id")] = row

    advantages = doc.get("competitor_advantages")
    if not isinstance(advantages, list) or len(advantages) < 3:
        return False, "advantages-short"
    for i, row in enumerate(advantages):
        if not isinstance(row, dict):
            return False, f"advantages[{i}]-type"
        cid = str(row.get("claim_id") or "")
        claim = by_id.get(cid)
        if not isinstance(claim, dict):
            return False, f"advantages[{i}]-missing-claim"
        if grade_claim(claim) != MEASURED:
            return False, f"advantages[{i}]-not-E1"
        if not cited_as_measured(claim):
            return False, f"advantages[{i}]-not-cited"
        if not str(row.get("does_better") or "").strip():
            return False, f"advantages[{i}]-empty"

    overlap = doc.get("overlap_with_planned_features")
    if not isinstance(overlap, list) or len(overlap) < 5:
        return False, "overlap-short"
    for i, row in enumerate(overlap):
        if not isinstance(row, dict):
            return False, f"overlap[{i}]-type"
        ids = row.get("catalog_unit_ids")
        if not isinstance(ids, list) or not ids:
            return False, f"overlap[{i}]-no-catalog-ids"
        if row.get("competitor_already_has") is not True:
            return False, f"overlap[{i}]-not-already-has"
        if not str(row.get("planned_feature") or "").strip():
            return False, f"overlap[{i}]-feature"

    miss = doc.get("switcher_would_miss")
    if not isinstance(miss, list) or len(miss) < 3:
        return False, "switcher-miss-short"

    captures = doc.get("captures") or []
    if not isinstance(captures, list) or len(captures) < 4:
        return False, "captures-short"
    for i, row in enumerate(captures):
        rel = str(row.get("path") or "")
        path = repo / rel
        if not path.is_file():
            return False, f"captures[{i}]-missing"
        payload = path.read_bytes().replace(b"\r\n", b"\n")
        if file_sha(path) != str(row.get("sha256") or ""):
            return False, f"captures[{i}]-sha"
        if int(row.get("bytes") or -1) != len(payload):
            return False, f"captures[{i}]-bytes"

    tests = doc.get("tests") or []
    if not isinstance(tests, list) or len(tests) < 2:
        return False, "tests-short"
    return True, f"advantages={len(advantages)} overlap={len(overlap)}"
