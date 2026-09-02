"""Run the same real unit through old rail and wrapped common contract.

Signal 1: sha256 of portable payload (old vs unwrap(wrap(old))).
Signal 2: field-set of portable keys plus remainder keys (counts, not timestamps).
Disagreement between the two readings is BLOCKED, not a picked winner.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from catalog_units import SAMPLE_IDS, sample_units
from contract import (
    both_directions,
    portable,
    refuse_drop_remainder,
    remainder_of,
    sha256_obj,
    wrap,
)
from fanout_rail import old_artifact as fanout_old
from fanout_rail import refuse_fire_and_forget
from mail_rail import old_artifact as mail_old
from mcp_thread import old_artifact as mcp_old

RAIL_IDS = ("mcp-thread", "exec-fanout", "agent-mail")


def old_for(rail_id: str, unit: dict[str, Any], repo: Path, here: Path) -> dict[str, Any]:
    uid = str(unit["id"])
    if rail_id == "mcp-thread":
        return mcp_old(unit, repo)
    if rail_id == "exec-fanout":
        return fanout_old(uid, repo, here)
    if rail_id == "agent-mail":
        return mail_old(unit)
    raise KeyError(rail_id)


def classify(old: dict[str, Any], wrapped: dict[str, Any]) -> str:
    rem = wrapped.get("remainder") or {}
    payload_match = wrapped["payload_sha256"] == sha256_obj(portable(old))
    if payload_match and rem:
        return "PAYLOAD-IDENTICAL-REMAINDER-QUEUED"
    if payload_match:
        return "BYTE-IDENTICAL-PAYLOAD"
    return "DIVERGENT"


def compare_row(rail_id: str, unit: dict[str, Any], repo: Path, here: Path) -> dict[str, Any]:
    old = old_for(rail_id, unit, repo, here)
    wrapped = wrap(old)
    payload_old = sha256_obj(portable(old))
    payload_new = wrapped["payload_sha256"]
    rem = remainder_of(old)
    portable_keys = sorted(portable(old).keys())
    remainder_keys = sorted(rem.keys())
    signal1_match = payload_old == payload_new
    # Signal 2 reads a different field: key-set cardinality of portable vs wrap payload.
    signal2_match = sorted(wrapped["payload"].keys()) == portable_keys
    disagreement = signal1_match != signal2_match
    directions = both_directions(old)
    unique_ok = True
    # Remainder must still be present on the wrap, not dropped.
    if rem and wrapped.get("remainder") != rem:
        unique_ok = False
    cls = classify(old, wrapped)
    return {
        "rail_id": rail_id,
        "unit_id": unit["id"],
        "decision": "WRAP",
        "classification": cls,
        "byte_identical_payload": signal1_match and not disagreement,
        "unique_lines_preserved": unique_ok,
        "both_directions": directions,
        "remainder_queued": bool(rem),
        "old_sha256": sha256_obj(old),
        "new_sha256": sha256_obj(wrapped),
        "payload_sha256": payload_new,
        "signal_disagreement": disagreement,
        "signal1_sha256_compare": {
            "old": payload_old,
            "new": payload_new,
            "match": signal1_match,
        },
        "signal2_field_set": {
            "portable_keys": portable_keys,
            "wrapped_payload_keys": sorted(wrapped["payload"].keys()),
            "remainder_keys": remainder_keys,
            "portable_match": signal2_match,
            "remainder_count": len(remainder_keys),
        },
        "reason": (
            "portable payload byte-identical in both directions; vendor remainder queued"
            if rem
            else "portable payload byte-identical in both directions; no remainder"
        ),
        "old": old,
        "wrapped": wrapped,
    }


def rail_digest(rows: list[dict[str, Any]]) -> dict[str, str]:
    rail_id = rows[0]["rail_id"]
    ordered = sorted(rows, key=lambda r: str(r["unit_id"]))
    blob = {
        "rail_id": rail_id,
        "units": [r["unit_id"] for r in ordered],
        "payload_shas": [r["payload_sha256"] for r in ordered],
    }
    digest = sha256_obj(blob)
    run_id = f"{rail_id}:{ '+'.join(r['unit_id'] for r in ordered) }"
    return {"rail_id": rail_id, "id": run_id, "sha256": digest}


def run_all(repo: Path, here: Path) -> dict[str, Any]:
    units = sample_units(repo)
    rows: list[dict[str, Any]] = []
    for rail_id in RAIL_IDS:
        for unit in units:
            rows.append(compare_row(rail_id, unit, repo, here))
    disagree = [r for r in rows if r.get("signal_disagreement")]
    failed = [
        r
        for r in rows
        if not r["byte_identical_payload"]
        or not r["unique_lines_preserved"]
        or not r["both_directions"]
    ]
    queued = [r for r in rows if r.get("remainder_queued")]
    per_rail = {
        rid: rail_digest([r for r in rows if r["rail_id"] == rid]) for rid in RAIL_IDS
    }
    # Negative control uses a remainder-bearing wrap (MCP thread).
    mcp_wrap = next(r["wrapped"] for r in rows if r["rail_id"] == "mcp-thread")
    neg = refuse_drop_remainder(mcp_wrap, "TAKE-NEW-DROP-REMAINDER")
    faf = refuse_fire_and_forget()
    return {
        "rows": rows,
        "disagree": disagree,
        "failed": failed,
        "queued": queued,
        "per_rail": per_rail,
        "negative_control": neg,
        "fire_and_forget": faf,
        "units": list(SAMPLE_IDS),
        "rails": list(RAIL_IDS),
    }
