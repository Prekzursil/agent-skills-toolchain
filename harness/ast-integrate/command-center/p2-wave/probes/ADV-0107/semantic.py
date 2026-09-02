"""Semantic survival: token dropped, qualification still present.

Mechanically different from counter.py (which only counts applied tokens).
This module walks source USE items and asks whether dest still carries the
qualification, even without the literal tag/band/anchor.
"""
from __future__ import annotations

import re
from typing import Any

from counter import extract

UNVERIFIED_PHRASES = (
    "has not been independently verified",
    "has not been verified",
    "not been independently checked",
    "settling experiment still required",
    "still unverified",
    "never been checked",
)
BAND_PHRASES = {
    "almost-certain": ("nearly certain", "95-99 percent", "virtually certain"),
    "likely": ("probable", "greater than even chance"),
    "roughly-even": ("even chance", "about fifty-fifty"),
    "unlikely": ("improbable", "less than even chance"),
    "remote": ("almost no chance", "highly improbable"),
}


def _dest_text(text: str) -> str:
    return text


def _claim_blob(text: str, claim_id: str | None) -> str:
    if not claim_id:
        return text
    chunks: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if claim_id in line:
            lo = max(0, i - 1)
            hi = min(len(lines), i + 3)
            chunks.append("\n".join(lines[lo:hi]))
    return "\n".join(chunks) if chunks else ""


def mechanical_present(src: dict[str, Any], dest_use: list[dict[str, Any]]) -> bool:
    kind = src["kind"]
    if kind == "unverified" and src.get("claim_id"):
        return any(
            d["kind"] == "unverified" and d.get("claim_id") == src["claim_id"] for d in dest_use
        )
    if kind == "band" and src.get("claim_id"):
        return any(
            d["kind"] == "band"
            and d["value"] == src["value"]
            and d.get("claim_id") == src["claim_id"]
            for d in dest_use
        )
    if kind in ("file_line", "url", "band"):
        return any(d["kind"] == kind and d["value"] == src["value"] for d in dest_use)
    if kind == "unverified":
        # no claim id: cannot identity-match; treat as present if dest still has any use tag
        return any(d["kind"] == "unverified" for d in dest_use)
    return False


def semantic_keep(src: dict[str, Any], dest_text: str) -> tuple[bool, str]:
    kind = src["kind"]
    blob = _claim_blob(dest_text, src.get("claim_id")) or dest_text
    low = blob.lower()
    if kind == "unverified":
        if src.get("claim_id") and src["claim_id"] not in dest_text:
            return False, "claim-id-absent"
        for phrase in UNVERIFIED_PHRASES:
            if phrase in low:
                return True, f"phrase:{phrase}"
        return False, "no-qualification-phrase"
    if kind == "band":
        if src["value"] in dest_text and src.get("claim_id") and src["claim_id"] in dest_text:
            return True, "literal-band-near-claim"
        for phrase in BAND_PHRASES.get(src["value"], ()):
            if phrase in low:
                return True, f"phrase:{phrase}"
        return False, "no-band-phrase"
    if kind == "file_line":
        val = src["value"]
        if val in dest_text:
            return True, "literal-file-line"
        if ":" in val:
            path, line = val.rsplit(":", 1)
            alt = f"{path} line {line}"
            if alt in dest_text:
                return True, f"alt:{alt}"
            alt2 = f"{path} at line {line}"
            if alt2 in dest_text:
                return True, f"alt:{alt2}"
        return False, "anchor-absent"
    if kind == "url":
        if src["value"] in dest_text:
            return True, "literal-url"
        host = (src.get("host") or "").lower()
        if host and host in dest_text.lower() and src.get("claim_id") and src["claim_id"] in dest_text:
            return True, "host-near-claim"
        return False, "url-absent"
    return False, "unknown-kind"


def compare_pair(src_text: str, dest_text: str) -> dict[str, Any]:
    src_items = [i for i in extract(src_text) if i["use"]]
    dest_use = [i for i in extract(dest_text) if i["use"]]
    rows = []
    for src in src_items:
        mech = mechanical_present(src, dest_use)
        kept, why = (True, "mechanical") if mech else semantic_keep(src, dest_text)
        rows.append(
            {
                "kind": src["kind"],
                "value": src["value"],
                "claim_id": src.get("claim_id") or src.get("claim_id"),
                "claim_id": src.get("claim_id") or src.get("claim_id"),
                "mechanical": mech,
                "semantic_keep": kept,
                "true_loss": not kept,
                "why": why,
                "source_line": src["line"],
            }
        )
    n = len(rows)
    true_loss = [r for r in rows if r["true_loss"]]
    mech_loss = [r for r in rows if not r["mechanical"]]
    semantic_only = [r for r in rows if (not r["mechanical"]) and r["semantic_keep"]]
    return {
        "source_use_n": n,
        "mechanical_survivors": n - len(mech_loss),
        "mechanical_losses": len(mech_loss),
        "semantic_survivors_among_mech_loss": len(semantic_only),
        "true_losses": len(true_loss),
        "rows": rows,
        "true_loss_rows": true_loss,
        "semantic_only_rows": semantic_only,
    }
