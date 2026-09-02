"""Two independent tree diffs: raw bytes vs declared-mask normalized.

The mask is imported from mask.py (declared up front). This module never
feeds diffs back into the mask list.
"""
from __future__ import annotations

from typing import Any

from engine import (
    artifact_names,
    canonical,
    mask_artifact_bytes,
    parse_artifact,
    sha256_bytes,
)
from mask import DECLARED_NONDETERMINISTIC_FIELDS, MASK_PLACEHOLDER, apply_declared_mask


def first_byte_diff(a: bytes, b: bytes) -> int | None:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    if len(a) != len(b):
        return n
    return None


def tree_concat(files: dict[str, bytes]) -> bytes:
    parts = []
    for name in sorted(files):
        parts.append(name.encode("utf-8"))
        parts.append(b"\0")
        parts.append(files[name].replace(b"\r\n", b"\n"))
        parts.append(b"\0")
    return b"".join(parts)


def per_file_sha(files: dict[str, bytes]) -> dict[str, str]:
    return {name: sha256_bytes(files[name]) for name in sorted(files)}


def tree_sha(files: dict[str, bytes]) -> str:
    return sha256_bytes(tree_concat(files))


def file_diffs(a: dict[str, bytes], b: dict[str, bytes]) -> list[dict[str, Any]]:
    names = sorted(set(a) | set(b))
    rows = []
    for name in names:
        if name not in a:
            rows.append(
                {
                    "path": name,
                    "kind": "missing-in-a",
                    "first_byte_diff": 0,
                    "sha_a": None,
                    "sha_b": sha256_bytes(b[name]),
                }
            )
            continue
        if name not in b:
            rows.append(
                {
                    "path": name,
                    "kind": "missing-in-b",
                    "first_byte_diff": 0,
                    "sha_a": sha256_bytes(a[name]),
                    "sha_b": None,
                }
            )
            continue
        off = first_byte_diff(a[name], b[name])
        if off is not None:
            rows.append(
                {
                    "path": name,
                    "kind": "bytes",
                    "first_byte_diff": off,
                    "sha_a": sha256_bytes(a[name]),
                    "sha_b": sha256_bytes(b[name]),
                }
            )
    return rows


def normalize_tree(files: dict[str, bytes]) -> dict[str, bytes]:
    return {name: mask_artifact_bytes(name, raw) for name, raw in files.items()}


def byte_diff_report(a: dict[str, bytes], b: dict[str, bytes]) -> dict[str, Any]:
    diffs = file_diffs(a, b)
    return {
        "identical": not diffs,
        "tree_sha_a": tree_sha(a),
        "tree_sha_b": tree_sha(b),
        "per_file_a": per_file_sha(a),
        "per_file_b": per_file_sha(b),
        "file_diffs": diffs,
        "first_file": diffs[0]["path"] if diffs else None,
        "first_byte_diff": diffs[0]["first_byte_diff"] if diffs else None,
        "mechanism": "concatenated-path-nul-bytes-sha256",
    }


def normalized_diff_report(a: dict[str, bytes], b: dict[str, bytes]) -> dict[str, Any]:
    na = normalize_tree(a)
    nb = normalize_tree(b)
    report = byte_diff_report(na, nb)
    report["mechanism"] = "declared-mask-then-concatenated-sha256"
    report["mask"] = list(DECLARED_NONDETERMINISTIC_FIELDS)
    report["placeholder"] = MASK_PLACEHOLDER
    return report


def masked_placeholder_present(files: dict[str, bytes]) -> bool:
    for name, raw in normalize_tree(files).items():
        if MASK_PLACEHOLDER.encode("ascii") in raw:
            return True
        del name
    return False


def semantic_payloads_equal(a: dict[str, bytes], b: dict[str, bytes]) -> bool:
    """Independent of the mask: compare payload/records/downstream only."""
    for name in artifact_names():
        if name == "ledger.jsonl":
            la = parse_artifact(name, a[name])
            lb = parse_artifact(name, b[name])
            if len(la) != len(lb):
                return False
            for ra, rb in zip(la, lb):
                if ra.get("id") != rb.get("id"):
                    return False
                if ra.get("seq") != rb.get("seq"):
                    return False
                if ra.get("byte_count") != rb.get("byte_count"):
                    return False
            continue
        pa = parse_artifact(name, a[name])
        pb = parse_artifact(name, b[name])
        for key in ("payload", "records", "downstream", "digest", "seed", "stage"):
            if key in pa or key in pb:
                if canonical(pa.get(key)) != canonical(pb.get(key)):
                    return False
    return True


def apply_declared_mask_public(obj: Any) -> Any:
    return apply_declared_mask(obj)
