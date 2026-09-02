"""Load P0/P1 claims from live CNF-0140 / CLAIM-REGISTRY, else fixture census."""
from __future__ import annotations

from pathlib import Path

from common import FIXTURES, REPO, load_json


def _claims_from_0140(doc: dict) -> list[dict]:
    for key in ("claims", "p0_p1_claims", "census", "rows"):
        rows = doc.get(key)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            out = []
            for row in rows:
                sev = str(row.get("severity") or "").upper()
                cid = row.get("claim_id") or row.get("id")
                if cid and sev in {"P0", "P1"}:
                    out.append(row)
            if out:
                return out
    return []


def _claims_from_registry(doc) -> list[dict]:
    rows = doc
    if isinstance(doc, dict):
        for key in ("claims", "entries", "records"):
            if isinstance(doc.get(key), list):
                rows = doc[key]
                break
        else:
            return []
    out = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        sev = str(row.get("severity") or "").upper()
        cid = row.get("claim_id") or row.get("id")
        if cid and sev in {"P0", "P1"}:
            out.append(row)
    return out


def load_census() -> dict:
    p140 = REPO / "command-center" / "receipts" / "CNF-0140.json"
    reg = REPO / "command-center" / "CLAIM-REGISTRY.json"
    live_0140 = "PRESENT" if p140.is_file() else "ABSENT"
    live_reg = "PRESENT" if reg.is_file() else "ABSENT"
    if p140.is_file():
        claims = _claims_from_0140(load_json(p140))
        if claims:
            return {
                "source": "CNF-0140",
                "live_cnf0140": live_0140,
                "live_registry": live_reg,
                "claim_count": len(claims),
                "claims": claims,
            }
        live_0140 = "PRESENT-NO-P0P1-ROWS"
    if reg.is_file():
        claims = _claims_from_registry(load_json(reg))
        if claims:
            return {
                "source": "CLAIM-REGISTRY",
                "live_cnf0140": live_0140,
                "live_registry": live_reg,
                "claim_count": len(claims),
                "claims": claims,
            }
        live_reg = "PRESENT-NO-P0P1-ROWS"
    fixture = load_json(FIXTURES / "census.json")
    claims = list(fixture["claims"])
    return {
        "source": "fixture-census-live-registry-absent",
        "live_cnf0140": live_0140,
        "live_registry": live_reg,
        "claim_count": len(claims),
        "claims": claims,
        "fixture_note": fixture.get("note"),
    }
