#!/usr/bin/env python3
"""Load live claim records if present; otherwise the frozen fixture corpus."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CLAIMS_PATH = HERE / "fixtures" / "claims.json"
SEALED_PATH = HERE / "fixtures" / "sealed_original.json"

LIVE_CANDIDATES = (
    "command-center/CLAIM-REGISTRY.json",
    "command-center/audit/AUD-0068-claim-extraction-canonical.json",
    "command-center/receipts/CC-0019.json",
    "command-center/confirmation/CNF-0005-blind-brief-builder.json",
)


def _as_list(doc) -> list:
    if isinstance(doc, list):
        return doc
    if not isinstance(doc, dict):
        return []
    for key in ("claims", "records", "items", "work_units"):
        val = doc.get(key)
        if isinstance(val, list):
            return val
    return []


def live_inventory() -> dict:
    rows = []
    for rel in LIVE_CANDIDATES:
        path = REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        n = 0
        n_edges = 0
        if present:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
                recs = _as_list(doc)
                n = len(recs)
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    dup = rec.get("duplicate_of") or rec.get("duplicate-of") or []
                    if isinstance(dup, list):
                        n_edges += len(dup)
                    elif dup:
                        n_edges += 1
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                present = False
        rows.append(
            {
                "path": rel,
                "present": present,
                "n_records": n,
                "n_duplicate_of_values": n_edges,
            }
        )
    return {
        "candidates": rows,
        "any_live_claim_registry": any(
            r["present"] and "CLAIM-REGISTRY" in r["path"] for r in rows
        ),
        "any_live_duplicate_of_edges": any(r["n_duplicate_of_values"] > 0 for r in rows),
    }


def live_claim_records() -> list[dict]:
    path = REPO / "command-center/CLAIM-REGISTRY.json"
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    out = []
    for rec in _as_list(doc):
        if not isinstance(rec, dict):
            continue
        cid = rec.get("id")
        mech = rec.get("text") or rec.get("canonical_mechanism") or rec.get("mechanism")
        if not cid or not mech:
            continue
        out.append(
            {
                "id": str(cid),
                "family": "live-claim-registry",
                "source_lineage": {
                    "path": "command-center/CLAIM-REGISTRY.json",
                    "unit_id": rec.get("council_id"),
                },
                "mechanism": str(mech),
            }
        )
    return out


def load_claims() -> list[dict]:
    doc = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    claims = list(doc["claims"])
    seen = {c["id"] for c in claims}
    for rec in live_claim_records():
        if rec["id"] not in seen:
            claims.append(rec)
            seen.add(rec["id"])
    if len(claims) < 8:
        raise SystemExit("FAILED:CNF-0067 fixture corpus too small")
    return claims


def load_sealed() -> dict:
    return json.loads(SEALED_PATH.read_text(encoding="utf-8"))


def claim_map(claims: list[dict]) -> dict[str, dict]:
    return {c["id"]: c for c in claims}


def sample_pairs(claims: list[dict], sealed: dict) -> list[dict]:
    by = claim_map(claims)
    rows = []
    for i, edge in enumerate(sealed["edges"], 1):
        left = by[edge["from_id"]]
        right = by[edge["to_id"]]
        rows.append(
            {
                "edge_id": f"E{i:02d}",
                "from_id": edge["from_id"],
                "to_id": edge["to_id"],
                "original_verdict": edge["original_verdict"],
                "kind": "recorded-edge",
                "left": left,
                "right": right,
            }
        )
    n_sealed_non = 0
    for j, edge in enumerate(sealed.get("non_edges") or [], 1):
        left = by[edge["from_id"]]
        right = by[edge["to_id"]]
        rows.append(
            {
                "edge_id": f"N{j:02d}",
                "from_id": edge["from_id"],
                "to_id": edge["to_id"],
                "original_verdict": edge["original_verdict"],
                "kind": "non-edge-scan",
                "left": left,
                "right": right,
            }
        )
        n_sealed_non += 1
    live = [c for c in claims if c.get("family") == "live-claim-registry"]
    k = 0
    for i, left in enumerate(live):
        for right in live[i + 1 :]:
            k += 1
            rows.append(
                {
                    "edge_id": f"L{k:02d}",
                    "from_id": left["id"],
                    "to_id": right["id"],
                    "original_verdict": "DISTINCT",
                    "kind": "live-non-edge",
                    "left": left,
                    "right": right,
                }
            )
    if n_sealed_non != len(sealed.get("non_edges") or []):
        raise SystemExit("FAILED:CNF-0067 sample construction")
    return rows
