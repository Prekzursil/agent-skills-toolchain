#!/usr/bin/env python3
"""Named downstream consumers of the research claim record.

These are executable, not JSON-Schema `required`. A field is kept only if at
least one consumer here goes red when the field is deleted.
"""
from __future__ import annotations

from typing import Any

SHA_LEN = 64
TIERS = {"E1", "E2", "E3", "E4"}
BANDS = {"HIGH", "MEDIUM", "LOW", "NONE"}
BINDING_TIERS = {"E1", "E2", "E3"}
BINDING_BANDS = {"HIGH", "MEDIUM"}


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == SHA_LEN and all(c in "0123456789abcdef" for c in value)


def phase1_dedup(claims: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Phase-1 dedup: identity, mechanism clustering, edge graph."""
    reasons: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    if not claims:
        return False, ["dedup: empty claim set"]
    for claim in claims:
        cid = claim.get("claim_id")
        if not isinstance(cid, str) or len(cid) < 6:
            reasons.append("dedup: missing claim_id")
            continue
        if cid in seen:
            reasons.append(f"dedup: duplicate claim_id {cid}")
        seen[cid] = claim
        mech = claim.get("canonical_mechanism")
        if not isinstance(mech, str) or len(mech) < 8:
            reasons.append(f"dedup: {cid} missing canonical_mechanism")
        if "support_edges" not in claim:
            reasons.append(f"dedup: {cid} missing support_edges")
        elif not isinstance(claim.get("support_edges"), list):
            reasons.append(f"dedup: {cid} support_edges not a list")
        if "contradiction_edges" not in claim:
            reasons.append(f"dedup: {cid} missing contradiction_edges")
        elif not isinstance(claim.get("contradiction_edges"), list):
            reasons.append(f"dedup: {cid} contradiction_edges not a list")
        else:
            for other in claim.get("contradiction_edges") or []:
                if other == cid:
                    reasons.append(f"dedup: {cid} contradicts itself")
    ids = set(seen)
    for cid, claim in seen.items():
        for other in claim.get("support_edges") or []:
            if other in ids:
                peer = seen[other]
                if cid in (peer.get("contradiction_edges") or []):
                    reasons.append(
                        f"dedup: {cid} supports {other} but {other} contradicts {cid}"
                    )
    return len(reasons) == 0, reasons


def phase4_contract(claim: dict[str, Any]) -> tuple[bool, list[str]]:
    """Phase-4 contract authoring: refuse to bind a contract on an untyped claim."""
    reasons: list[str] = []
    cid = claim.get("claim_id") or "<unknown>"
    mech = claim.get("canonical_mechanism")
    if not isinstance(mech, str) or len(mech) < 8:
        reasons.append(f"contract: {cid} missing canonical_mechanism")
    tier = claim.get("evidence_tier")
    if tier not in TIERS:
        reasons.append(f"contract: {cid} missing/invalid evidence_tier")
    band = claim.get("confidence_band")
    if band not in BANDS:
        reasons.append(f"contract: {cid} missing/invalid confidence_band")
    stamp = claim.get("freshness_stamp")
    if not isinstance(stamp, str) or len(stamp) < 20:
        reasons.append(f"contract: {cid} missing freshness_stamp")
    probe = claim.get("settling_probe")
    if not isinstance(probe, str) or len(probe) < 8:
        reasons.append(f"contract: {cid} missing settling_probe")
    if tier == "E4":
        reasons.append(f"contract: {cid} E4 may not author a binding contract")
    if band in {"LOW", "NONE"}:
        reasons.append(f"contract: {cid} {band} confidence may not author a binding contract")
    if tier in BINDING_TIERS and band in BINDING_BANDS:
        pass
    return len(reasons) == 0, reasons


def phase12_refutation(claim: dict[str, Any]) -> tuple[bool, list[str]]:
    """Phase-12 refutation: re-open lineage, re-hash snapshot, re-run settling probe.

    Missing source_lineage is a FAIL, never a warning.
    """
    reasons: list[str] = []
    cid = claim.get("claim_id")
    if not isinstance(cid, str) or len(cid) < 6:
        reasons.append("refute: missing claim_id")
        cid = "<unknown>"
    if "source_lineage" not in claim:
        reasons.append("refute: missing source_lineage")
    else:
        lin = claim.get("source_lineage")
        if not isinstance(lin, list) or len(lin) < 1:
            reasons.append("refute: source_lineage empty")
        else:
            for i, row in enumerate(lin):
                if not isinstance(row, dict):
                    reasons.append(f"refute: lineage[{i}] not an object")
                    continue
                if not row.get("locator"):
                    reasons.append(f"refute: lineage[{i}] missing locator")
                if not _sha(row.get("snapshot_sha256")):
                    reasons.append(f"refute: lineage[{i}] missing snapshot_sha256")
    if not _sha(claim.get("snapshot_sha256")):
        reasons.append("refute: missing snapshot_sha256")
    probe = claim.get("settling_probe")
    if not isinstance(probe, str) or len(probe) < 8:
        reasons.append("refute: missing settling_probe")
    if "contradiction_edges" not in claim:
        reasons.append("refute: missing contradiction_edges")
    return len(reasons) == 0, reasons


CONSUMERS = {
    "phase1_dedup": phase1_dedup,
    "phase4_contract": phase4_contract,
    "phase12_refutation": phase12_refutation,
}

FIELD_CONSUMERS = {
    "claim_id": ["phase1_dedup", "phase12_refutation"],
    "canonical_mechanism": ["phase1_dedup", "phase4_contract"],
    "source_lineage": ["phase12_refutation"],
    "evidence_tier": ["phase4_contract"],
    "confidence_band": ["phase4_contract"],
    "settling_probe": ["phase4_contract", "phase12_refutation"],
    "contradiction_edges": ["phase1_dedup", "phase12_refutation"],
    "support_edges": ["phase1_dedup"],
    "freshness_stamp": ["phase4_contract"],
    "snapshot_sha256": ["phase12_refutation"],
}


def run_all(claim: dict[str, Any], peers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    group = [claim]
    if peers:
        group = [claim] + [p for p in peers if p.get("claim_id") != claim.get("claim_id")]
    d_ok, d_why = phase1_dedup(group)
    c_ok, c_why = phase4_contract(claim)
    r_ok, r_why = phase12_refutation(claim)
    return {
        "ok": d_ok and c_ok and r_ok,
        "phase1_dedup": {"ok": d_ok, "reasons": d_why},
        "phase4_contract": {"ok": c_ok, "reasons": c_why},
        "phase12_refutation": {"ok": r_ok, "reasons": r_why},
    }
