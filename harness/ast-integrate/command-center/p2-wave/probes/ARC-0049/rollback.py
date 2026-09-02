"""One-step restore of a previous capability grant."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


def grant_digest(grant: list[str]) -> str:
    raw = json.dumps(list(grant), sort_keys=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def snapshot(store: dict[str, list[str]], capability_id: str) -> dict[str, Any]:
    grant = list(store[capability_id])
    return {
        "capability_id": capability_id,
        "grant": grant,
        "sha256": grant_digest(grant),
    }


def restore(store: dict[str, list[str]], snap: dict[str, Any]) -> dict[str, Any]:
    """Single assignment. Must not re-run the forward tighten."""
    uid = snap["capability_id"]
    store[uid] = list(snap["grant"])
    restored = list(store[uid])
    digest = grant_digest(restored)
    return {
        "capability_id": uid,
        "restored": restored,
        "sha256": digest,
        "match": digest == snap["sha256"],
        "one_step": True,
    }


def rehearse(
    capability_id: str,
    current: list[str],
    proposed: list[str],
) -> dict[str, Any]:
    store = {capability_id: list(current)}
    snap = snapshot(store, capability_id)
    store[capability_id] = list(proposed)
    tightened_sha = grant_digest(store[capability_id])
    if tightened_sha == snap["sha256"]:
        return {
            "pass": False,
            "reason": "proposed grant is identical to current; nothing to restore",
            "restored_capability": capability_id,
            "one_step": True,
            "sha256_match": False,
        }
    result = restore(store, snap)
    return {
        "pass": bool(result["match"] and result["one_step"]),
        "restored_capability": capability_id,
        "one_step": True,
        "sha256_match": bool(result["match"]),
        "snapshot_sha256": snap["sha256"],
        "restored_sha256": result["sha256"],
        "tightened_sha256": tightened_sha,
        "store_after": deepcopy(store),
    }
