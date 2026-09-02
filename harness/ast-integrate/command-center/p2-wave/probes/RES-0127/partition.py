#!/usr/bin/env python3
"""Three-way hash partition over two directory listings.

Buckets:
  only_in_a, only_in_b, in_both_identical, in_both_different

Same-name files are compared by sha256 of LF-normalised bytes. Same-bytes
files with different names are two rows (not merged). A path lands in
exactly one bucket.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Iterable

from relevance import is_research_relevant, skip_dir_name

BUCKETS = (
    "only_in_a",
    "only_in_b",
    "in_both_identical",
    "in_both_different",
)
ABSENT_SENTINEL = "ABSENT-SENTINEL-RES-0127.md"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def list_research_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not skip_dir_name(d)]
        base = Path(dirpath)
        for fn in filenames:
            full = base / fn
            try:
                rel = full.relative_to(root).as_posix()
            except ValueError:
                continue
            if not is_research_relevant(rel):
                continue
            if not full.is_file():
                continue
            out[rel] = full
    return out


def hash_tree(root: Path) -> dict[str, dict[str, Any]]:
    files = list_research_files(root)
    hashed: dict[str, dict[str, Any]] = {}
    for rel, path in sorted(files.items()):
        digest, size = sha256_file(path)
        hashed[rel] = {
            "rel": rel,
            "sha256": digest,
            "bytes": size,
            "path": str(path).replace("\\", "/"),
        }
    return hashed


def partition_hashed(
    hashed_a: dict[str, dict[str, Any]],
    hashed_b: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    keys_a = set(hashed_a)
    keys_b = set(hashed_b)
    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)
    both = sorted(keys_a & keys_b)
    identical: list[str] = []
    different: list[str] = []
    for rel in both:
        if hashed_a[rel]["sha256"] == hashed_b[rel]["sha256"]:
            identical.append(rel)
        else:
            different.append(rel)
    return {
        "only_in_a": [_row_one(hashed_a[r], side="a") for r in only_a],
        "only_in_b": [_row_one(hashed_b[r], side="b") for r in only_b],
        "in_both_identical": [
            _row_both(hashed_a[r], hashed_b[r], same=True) for r in identical
        ],
        "in_both_different": [
            _row_both(hashed_a[r], hashed_b[r], same=False) for r in different
        ],
        "counts": {
            "only_in_a": len(only_a),
            "only_in_b": len(only_b),
            "in_both_identical": len(identical),
            "in_both_different": len(different),
            "hashed_a": len(hashed_a),
            "hashed_b": len(hashed_b),
            "union": len(keys_a | keys_b),
        },
        "index": {
            "only_in_a": only_a,
            "only_in_b": only_b,
            "in_both_identical": identical,
            "in_both_different": different,
        },
    }


def _row_one(row: dict[str, Any], side: str) -> dict[str, Any]:
    return {
        "rel": row["rel"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "side": side,
    }


def _row_both(
    a: dict[str, Any], b: dict[str, Any], same: bool
) -> dict[str, Any]:
    return {
        "rel": a["rel"],
        "sha256_a": a["sha256"],
        "sha256_b": b["sha256"],
        "bytes_a": a["bytes"],
        "bytes_b": b["bytes"],
        "identical_bytes": same,
        "sha256": a["sha256"] if same else None,
    }


def rels(bucket: Iterable[dict[str, Any]]) -> set[str]:
    return {str(row["rel"]) for row in bucket}


def proof_of(part: dict[str, Any], hashed_a: dict, hashed_b: dict) -> dict[str, Any]:
    idx = part["index"]
    sets = {name: set(idx[name]) for name in BUCKETS}
    pairwise = True
    names = list(BUCKETS)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            if sets[left] & sets[right]:
                pairwise = False
    union_buckets = set().union(*sets.values())
    union_keys = set(hashed_a) | set(hashed_b)
    coverage = union_buckets == union_keys
    # identical-bytes same-name files occupy exactly the identical bucket
    identical_ok = True
    for rel in set(hashed_a) & set(hashed_b):
        same = hashed_a[rel]["sha256"] == hashed_b[rel]["sha256"]
        n = sum(1 for name in BUCKETS if rel in sets[name])
        if n != 1:
            identical_ok = False
        if same and rel not in sets["in_both_identical"]:
            identical_ok = False
        if same and rel in sets["in_both_different"]:
            identical_ok = False
        if (not same) and rel not in sets["in_both_different"]:
            identical_ok = False
    sentinel_absent = ABSENT_SENTINEL not in union_buckets
    renamed_not_merged = _renamed_same_bytes_not_merged(hashed_a, hashed_b, sets)
    identical_disjoint = not (
        sets["in_both_identical"] & sets["in_both_different"]
    )
    return {
        "pairwise_disjoint": pairwise,
        "identical_disjoint_from_different": identical_disjoint,
        "coverage_ok": coverage,
        "identical_bytes_exactly_one_bucket": identical_ok,
        "renamed_same_bytes_not_merged": renamed_not_merged,
        "absent_sentinel_in_no_bucket": sentinel_absent,
        "union_n": len(union_keys),
        "bucket_union_n": len(union_buckets),
        "ok": all(
            [
                pairwise,
                identical_disjoint,
                coverage,
                identical_ok,
                renamed_not_merged,
                sentinel_absent,
            ]
        ),
    }


def _renamed_same_bytes_not_merged(
    hashed_a: dict, hashed_b: dict, sets: dict[str, set[str]]
) -> bool:
    """Same content under two names is two only-in rows, never one identical row."""
    a_by_hash: dict[str, list[str]] = {}
    b_by_hash: dict[str, list[str]] = {}
    for rel, row in hashed_a.items():
        a_by_hash.setdefault(row["sha256"], []).append(rel)
    for rel, row in hashed_b.items():
        b_by_hash.setdefault(row["sha256"], []).append(rel)
    for digest, a_rels in a_by_hash.items():
        b_rels = b_by_hash.get(digest) or []
        for ar in a_rels:
            for br in b_rels:
                if ar == br:
                    continue
                # different names, same bytes: must not be treated as one
                if ar in sets["in_both_identical"] or br in sets["in_both_identical"]:
                    return False
                if ar not in sets["only_in_a"]:
                    return False
                if br not in sets["only_in_b"]:
                    return False
    return True


def mutate_identical_into_different(part: dict[str, Any]) -> dict[str, Any]:
    """Known-bad partition: copy first identical rel into the different bucket."""
    import copy

    bad = copy.deepcopy(part)
    ident = bad["index"]["in_both_identical"]
    if not ident:
        return bad
    rel = ident[0]
    bad["index"]["in_both_different"] = list(bad["index"]["in_both_different"]) + [rel]
    # keep published rows inconsistent with index so the detector has something to catch
    return bad


def partition_trees(root_a: Path | None, root_b: Path | None) -> dict[str, Any]:
    hashed_a = hash_tree(root_a) if root_a is not None else {}
    hashed_b = hash_tree(root_b) if root_b is not None else {}
    part = partition_hashed(hashed_a, hashed_b)
    proof = proof_of(part, hashed_a, hashed_b)
    part["proof"] = proof
    part["hashed_a"] = hashed_a
    part["hashed_b"] = hashed_b
    return part
