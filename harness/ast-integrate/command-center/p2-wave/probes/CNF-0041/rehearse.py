"""Live three-manifest rollback rehearsal used by emit and named probes."""
from __future__ import annotations

import json
from pathlib import Path

from rollback import restore, snapshot_bytes
from scenario import (
    PLANTED_REL,
    RESERVED_REL,
    apply_change,
    build_pre_state,
    manifest_path,
    plant_residue,
)
from walker import (
    fingerprint,
    hash_trees,
    manifest_rows,
    naive_hash_swallowed,
    parse_affected_trees,
    residue_rows,
    symmetric_difference,
)


def load_trees() -> list[str]:
    return parse_affected_trees(manifest_path().read_text(encoding="utf-8"))


def run_clean(root: Path) -> dict:
    trees = load_trees()
    build_pre_state(root)
    pre = hash_trees(root, trees, extended=True)
    if RESERVED_REL not in pre:
        raise RuntimeError(f"reserved path missing from pre walk: {RESERVED_REL}")
    snap = snapshot_bytes(root, trees)
    apply_change(root)
    post = hash_trees(root, trees, extended=True)
    post_fp = fingerprint(post)
    pre_fp = fingerprint(pre)
    if symmetric_difference(pre_fp, post_fp)["empty"]:
        raise RuntimeError("change did not alter the hash set")
    restore(root, trees, snap, delete_extras=True)
    post_rb = hash_trees(root, trees, extended=True)
    diff = symmetric_difference(pre_fp, fingerprint(post_rb))
    return {
        "trees": trees,
        "pre": pre,
        "post": post,
        "post_rollback": post_rb,
        "symmetric_difference": diff,
        "residue": residue_rows(diff),
        "pre_rows": manifest_rows(pre),
        "post_rows": manifest_rows(post),
        "post_rollback_rows": manifest_rows(post_rb),
    }


def run_planted_control(root: Path) -> dict:
    trees = load_trees()
    build_pre_state(root)
    pre = hash_trees(root, trees, extended=True)
    snap = snapshot_bytes(root, trees)
    apply_change(root)
    planted = plant_residue(root)
    restore(root, trees, snap, delete_extras=False)
    post_rb = hash_trees(root, trees, extended=True)
    diff = symmetric_difference(fingerprint(pre), fingerprint(post_rb))
    detected = planted in diff["only_in_post"] and not diff["empty"]
    return {
        "planted_path": planted,
        "detected": detected,
        "when": "planted extra file after the change, then incomplete rollback",
        "symmetric_difference": diff,
        "expected_plant": PLANTED_REL,
    }


def run_walker_control(root: Path) -> dict:
    trees = load_trees()
    build_pre_state(root)
    safe = hash_trees(root, trees, extended=True)
    naive, err = naive_hash_swallowed(root, trees)
    reserved = safe.get(RESERVED_REL)
    return {
        "reserved_path": RESERVED_REL,
        "extended_length_prefix_applied": True,
        "extended_length_path": (reserved or {}).get("extended_length_path"),
        "safe_count": len(safe),
        "naive_count": len(naive),
        "naive_swallowed_to_zero": len(naive) == 0 and bool(err),
        "naive_error": err,
        "reserved_in_safe": RESERVED_REL in safe,
    }


def as_jsonable(rec: dict) -> dict:
    return json.loads(json.dumps(rec, default=str))


def report_payload(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties is false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged = dict(doc)
    merged.update(report)
    return merged
