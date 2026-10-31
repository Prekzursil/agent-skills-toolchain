"""Disposition rules for WFA-0065 transfers."""

from __future__ import annotations

from typing import Any

from transfers import TRANSFERS, unknown_kinds

ADOPTED = "ADOPTED"
SPECULATIVE = "SPECULATIVE"
ALREADY = "ALREADY-SPECIFIED-IN-CATALOG"
OOS = "OUT-OF-SCOPE"

EVIDENCE_BACKED = frozenset({ADOPTED})
SPECULATIVE_BUCKET = frozenset({SPECULATIVE})


def _blocking_hits(xfer: dict, scan: dict[str, Any]) -> list[dict[str, str]]:
    sig = str(xfer.get("corpus_signature") or "")
    hits = list((scan.get("hits") or {}).get(sig) or [])
    policy = xfer.get("collision_policy")
    if policy == "near-miss-ok":
        return [h for h in hits if h.get("kind") != "near-miss-timeout-readback"]
    if policy == "none":
        return []
    return hits


def classify_one(xfer: dict, scan: dict[str, Any]) -> str:
    forced = xfer.get("force_disposition")
    if forced:
        return str(forced)
    if not xfer.get("ir_expressible") or unknown_kinds(xfer):
        return OOS
    fals = xfer.get("falsification") or {}
    if not fals.get("attempted") or not str(
        fals.get("source_property_that_does_not_hold") or ""
    ).strip():
        return SPECULATIVE
    blocking = _blocking_hits(xfer, scan)
    if xfer.get("collision_policy") == "already" and blocking:
        return ALREADY
    if xfer.get("collision_policy") == "near-miss-ok" and blocking:
        return ALREADY
    return str(xfer.get("intended_if_novel") or SPECULATIVE)


def classify_all(scan: dict[str, Any]) -> dict[str, str]:
    return {t["id"]: classify_one(t, scan) for t in TRANSFERS}


def bucket(disp: str) -> str:
    if disp == ADOPTED:
        return "evidence_backed_transfers"
    if disp == SPECULATIVE:
        return "speculative_transfers"
    if disp == ALREADY:
        return "already_specified_in_catalog"
    return "out_of_scope"
