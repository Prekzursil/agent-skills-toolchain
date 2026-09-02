#!/usr/bin/env python3
"""Load planted confirmation fixtures and scan the live tree for B09 records.

CLAIM-REGISTRY.json is a lineage input (catalog: 'source lineage edges'), not a
B09 confirmation corpus. Walking command-center/receipts/*.json for nested
claim/verdict/source_probe objects would contaminate the live rank with other
units' evidence rows. B09 catalog membership is currently 0; absence is
reported, not filled with planted rows.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "confirmations.json"

INPUT_PATHS = (
    "command-center/CLAIM-REGISTRY.json",
    "command-center/schema/confirmation-record.schema.json",
    "rules/common/single-signal-verification.md",
)

B09_CANDIDATES = (
    "command-center/confirmations",
    "command-center/confirmation-records",
    "command-center/b09",
    "command-center/B09",
    "command-center/receipts/B09.json",
)

SKIP_PARTS = {
    "CNF-0132",
    ".git",
    "node_modules",
    "__pycache__",
    "p2-wave",
}
SELF_RECEIPT = "command-center/receipts/CNF-0132.json"
CONFIRMED_VERDICTS = {
    "CONFIRMED",
    "REFUTED",
    "PARTIAL",
    "UNVERIFIED",
    "NOT-CHECKED",
}


def load_planted() -> dict:
    return json.loads(PLANTED.read_text(encoding="utf-8"))


def _probe_is_record_shaped(probe: Any) -> bool:
    if not isinstance(probe, dict) or not probe:
        return False
    return any(
        k in probe
        for k in (
            "upstream",
            "upstreams",
            "cached_artifact",
            "cached_artifacts",
            "artifact",
            "fingerprint",
            "shell",
            "tool",
            "field",
            "engine",
            "command",
        )
    )


def _looks_like_b09_confirmation(obj: Any) -> bool:
    """CNF-0129-shaped confirmation, not a CLAIM-REGISTRY claim row."""
    if not isinstance(obj, dict):
        return False
    cid = obj.get("claim_id") or obj.get("target_claim")
    if not cid:
        return False
    verd = str(obj.get("verdict") or "").upper()
    if verd not in CONFIRMED_VERDICTS:
        return False
    src = obj.get("source_probe")
    ver = obj.get("verifier_probe")
    return _probe_is_record_shaped(src) or _probe_is_record_shaped(ver)


def _collect_confirmations(doc: Any) -> list[dict]:
    recs: list[dict] = []

    def consider(obj: Any) -> None:
        if _looks_like_b09_confirmation(obj):
            recs.append(obj)
            return
        if isinstance(obj, dict):
            for val in obj.values():
                if isinstance(val, dict):
                    consider(val)
                elif isinstance(val, list):
                    for item in val:
                        consider(item)
        elif isinstance(obj, list):
            for item in obj:
                consider(item)

    consider(doc)
    return recs


def _catalog_b09_members() -> tuple[int, list[str]]:
    catalog = REPO / "command-center/WORK-UNIT-CATALOG.json"
    if not catalog.is_file():
        return 0, []
    try:
        cat = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, []
    count = 0
    meta = cat.get("work_units_meta") or {}
    for blob in (
        cat.get("catalog_integrity") or {},
        cat.get("remeasured_2026_08_11") or {},
        meta.get("remeasured_2026_08_11") or {},
        meta,
        cat,
    ):
        stats = blob.get("bucket_members") if isinstance(blob, dict) else None
        if isinstance(stats, dict) and "B09" in stats:
            try:
                count = int(stats.get("B09") or 0)
            except (TypeError, ValueError):
                count = 0
            break
    member_ids: list[str] = []
    for unit in cat.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        buckets = unit.get("buckets") or unit.get("bucket") or []
        if buckets == "B09" or (isinstance(buckets, list) and "B09" in buckets):
            uid = unit.get("id")
            if uid:
                member_ids.append(str(uid))
    return count, member_ids


def load_claim_registry_lineage() -> dict:
    rel = "command-center/CLAIM-REGISTRY.json"
    path = REPO / rel
    if not path.is_file():
        return {
            "present": False,
            "path": rel,
            "claim_count": 0,
            "claims": [],
            "note": "CLAIM-REGISTRY.json absent; lineage edges not loaded.",
        }
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "present": True,
            "path": rel,
            "claim_count": 0,
            "claims": [],
            "parse_error": type(exc).__name__,
            "note": "CLAIM-REGISTRY.json present but unparseable.",
        }
    rows = []
    for claim in doc.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        src = claim.get("source_probe")
        ver = claim.get("verifier_probe")
        rows.append(
            {
                "claim_id": claim.get("id"),
                "verdict": claim.get("verdict"),
                "source_probe_kind": type(src).__name__,
                "verifier_probe_kind": type(ver).__name__,
                "source_declared": bool(src),
                "verifier_declared": bool(ver),
                "note": (
                    "CLAIM-REGISTRY lineage edge. Probe fields are prose strings, "
                    "not CNF-0129 fingerprint dicts. Not a B09 confirmation record."
                ),
            }
        )
    return {
        "present": True,
        "path": rel,
        "claim_count": len(rows),
        "claims": rows,
        "note": (
            "Used as source-lineage edges only. Independence rank is computed "
            "over B09 confirmation records, not over these registry rows."
        ),
    }


def scan_live() -> dict:
    presence: dict[str, bool] = {}
    for rel in INPUT_PATHS + B09_CANDIDATES:
        presence[rel] = (REPO / rel).exists()

    found_paths: list[str] = []
    live_records: list[dict] = []
    for rel in B09_CANDIDATES:
        path = REPO / rel
        if path.is_file() and path.suffix == ".json":
            if rel == SELF_RECEIPT:
                continue
            found_paths.append(rel)
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for rec in _collect_confirmations(doc):
                rec = dict(rec)
                rec["_live_path"] = rel
                live_records.append(rec)
        elif path.is_dir():
            for child in path.rglob("*.json"):
                if any(part in SKIP_PARTS for part in child.parts):
                    continue
                rel_c = child.relative_to(REPO).as_posix()
                if rel_c == SELF_RECEIPT:
                    continue
                found_paths.append(rel_c)
                try:
                    doc = json.loads(child.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                for rec in _collect_confirmations(doc):
                    rec = dict(rec)
                    rec["_live_path"] = rel_c
                    live_records.append(rec)

    catalog_b09, member_ids = _catalog_b09_members()
    lineage = load_claim_registry_lineage()
    return {
        "candidate_presence": presence,
        "json_paths_seen": found_paths,
        "live_record_count": len(live_records),
        "live_records": live_records,
        "catalog_b09_members": catalog_b09,
        "catalog_b09_member_ids": member_ids,
        "claim_registry_present": presence.get(
            "command-center/CLAIM-REGISTRY.json", False
        ),
        "confirmation_schema_present": presence.get(
            "command-center/schema/confirmation-record.schema.json", False
        ),
        "single_signal_rule_present": presence.get(
            "rules/common/single-signal-verification.md", False
        ),
        "lineage": lineage,
    }


def load_all() -> dict:
    planted_doc = load_planted()
    planted = list(planted_doc.get("records") or [])
    live = scan_live()
    return {
        "planted_frame_id": planted_doc.get("frame_id"),
        "planted": planted,
        "live": live,
        "combined": planted + list(live.get("live_records") or []),
    }
