"""Six-hop pipeline that must carry provenance_anchor and licence_class.

Hops match the catalog: acquisition, extraction, translation, dedup collapse,
fusion, certification. Each hop emits a NEW object. Primary carry fields are
copied explicitly; a hop that forgets them is a real loss the gate must catch.
"""
from __future__ import annotations

from typing import Any

from carry import (
    ANCHOR_KEY,
    HOPS,
    LICENCE_KEY,
    SEED_A,
    SEED_B,
    stricter_licence,
)


def _carry_from(src: dict[str, Any], extra_anchors: list[str] | None = None) -> dict[str, Any]:
    anchors = list(src.get("source_anchors") or [])
    if src.get(ANCHOR_KEY) and src[ANCHOR_KEY] not in anchors:
        anchors.insert(0, src[ANCHOR_KEY])
    for a in extra_anchors or []:
        if a not in anchors:
            anchors.append(a)
    lineage = list(src.get("licence_lineage") or [])
    lic = src.get(LICENCE_KEY)
    if lic and lic not in lineage:
        lineage.append(lic)
    return {
        ANCHOR_KEY: src.get(ANCHOR_KEY),
        LICENCE_KEY: src.get(LICENCE_KEY),
        "source_anchors": anchors,
        "licence_lineage": lineage,
        "notes": src.get("notes"),
    }


def acquire(seed: dict[str, Any]) -> dict[str, Any]:
    out = {
        "hop": "acquisition",
        "kind": "acquired-artifact",
        "native_id": seed["id"],
        "native_source": seed["source_uri"],
        "licence_file": seed["licence_file"],
        "payload_bytes": seed["payload_bytes"],
        ANCHOR_KEY: seed[ANCHOR_KEY],
        LICENCE_KEY: seed[LICENCE_KEY],
        "source_anchors": [seed[ANCHOR_KEY]],
        "licence_lineage": [seed[LICENCE_KEY]],
        "notes": seed.get("notes"),
    }
    return out


def extract(acquired: dict[str, Any]) -> dict[str, Any]:
    out = {
        "hop": "extraction",
        "kind": "extraction-report",
        "constructs": [
            {"id": "c-stage", "kind": "stage", "from": acquired.get("native_id")}
        ],
        **_carry_from(acquired),
    }
    return out


def translate(extracted: dict[str, Any]) -> dict[str, Any]:
    out = {
        "hop": "translation",
        "kind": "workflow-ir",
        "nodes": list(extracted.get("constructs") or []),
        **_carry_from(extracted),
    }
    return out


def collapse(ir: dict[str, Any], partner_ir: dict[str, Any]) -> dict[str, Any]:
    """Union-preserving collapse (WFA-0095). Stricter licence governs."""
    partner_anchor = partner_ir.get(ANCHOR_KEY)
    partner_lic = partner_ir.get(LICENCE_KEY)
    carry = _carry_from(
        ir,
        extra_anchors=[partner_anchor] if partner_anchor else None,
    )
    licences = list(carry["licence_lineage"])
    if partner_lic and partner_lic not in licences:
        licences.append(partner_lic)
    carry["licence_lineage"] = licences
    a = carry.get(LICENCE_KEY)
    b = partner_lic
    if a and b:
        carry[LICENCE_KEY] = stricter_licence(a, b)
    carry[ANCHOR_KEY] = "lineage://wfa-0122/dedup-collapse"
    out = {
        "hop": "dedup collapse",
        "kind": "collapsed-ir",
        "nodes": list(ir.get("nodes") or []) + list(partner_ir.get("nodes") or []),
        "collapsed_from": [ir.get("hop"), partner_ir.get("hop")],
        **carry,
    }
    return out


def fuse(collapsed: dict[str, Any], partner_ir: dict[str, Any]) -> dict[str, Any]:
    """Fusion records lineage; most-restrictive licence wins (WFA-0110)."""
    partner_anchor = partner_ir.get(ANCHOR_KEY)
    partner_lic = partner_ir.get(LICENCE_KEY)
    carry = _carry_from(
        collapsed,
        extra_anchors=[partner_anchor] if partner_anchor else None,
    )
    licences = list(carry["licence_lineage"])
    if partner_lic and partner_lic not in licences:
        licences.append(partner_lic)
    carry["licence_lineage"] = licences
    a = carry.get(LICENCE_KEY)
    b = partner_lic
    if a and b:
        carry[LICENCE_KEY] = stricter_licence(a, b)
    carry[ANCHOR_KEY] = "lineage://wfa-0122/fusion"
    out = {
        "hop": "fusion",
        "kind": "fusion-result",
        "operator": "union-preserve",
        "source_hops": [collapsed.get("hop"), partner_ir.get("hop")],
        **carry,
    }
    return out


def certify(fused: dict[str, Any]) -> dict[str, Any]:
    out = {
        "hop": "certification",
        "kind": "certified-workflow",
        "certified": True,
        "final": True,
        **_carry_from(fused),
    }
    out[ANCHOR_KEY] = fused.get(ANCHOR_KEY)
    out[LICENCE_KEY] = fused.get(LICENCE_KEY)
    return out


def partner_ir() -> dict[str, Any]:
    return translate(extract(acquire(SEED_B)))


def apply_hop(hop: str, prev: dict[str, Any] | None) -> dict[str, Any]:
    if hop == "acquisition":
        return acquire(SEED_A)
    if prev is None:
        raise ValueError(f"hop {hop!r} requires prior output")
    if hop == "extraction":
        return extract(prev)
    if hop == "translation":
        return translate(prev)
    if hop == "dedup collapse":
        return collapse(prev, partner_ir())
    if hop == "fusion":
        return fuse(prev, partner_ir())
    if hop == "certification":
        return certify(prev)
    raise ValueError(f"unknown hop {hop!r}")


def run_to(target_hop: str) -> dict[str, Any]:
    if target_hop not in HOPS:
        raise ValueError(f"unknown hop {target_hop!r}")
    art: dict[str, Any] | None = None
    for hop in HOPS:
        art = apply_hop(hop, art)
        if hop == target_hop:
            return art
    raise RuntimeError("unreachable")


def run_all() -> list[dict[str, Any]]:
    snaps: list[dict[str, Any]] = []
    art: dict[str, Any] | None = None
    for hop in HOPS:
        art = apply_hop(hop, art)
        snaps.append(art)
    return snaps
