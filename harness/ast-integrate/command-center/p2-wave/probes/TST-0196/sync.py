#!/usr/bin/env python3
"""Deploy/sync that carries case-only renames on a case-insensitive destination.

PASS contract (TST-0196): after a tracked file is renamed case-only, the
destination holds exactly one file with the *new* casing and the same content
hash as the source blob. A copy loop keyed on lowercased names must fail that
check. A content-changing rename must also land.
"""
from __future__ import annotations

import hashlib
from typing import Any

from casefs import CaseInsensitiveFS, fold, posix

BLOB_A = b"TST-0196-blob-A:case-only-rename-payload\n"
BLOB_B = b"TST-0196-blob-B:content-changing-rename-payload\n"
PLUGIN = b'{"id":"demo.plugin","version":"1.0.0"}\n'
OLD_REL = "docs/ReadMe.md"
NEW_REL = "docs/README.md"
SIBLING = "plugin.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_old() -> dict[str, bytes]:
    return {OLD_REL: BLOB_A, SIBLING: PLUGIN}


def source_case_only() -> dict[str, bytes]:
    return {NEW_REL: BLOB_A, SIBLING: PLUGIN}


def source_content_change() -> dict[str, bytes]:
    return {NEW_REL: BLOB_B, SIBLING: PLUGIN}


def _tmp_rel(rel: str) -> str:
    rel = posix(rel)
    parent, _, _name = rel.rpartition("/")
    token = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16]
    tmp = f".ast-case-{token}.tmp"
    return f"{parent}/{tmp}" if parent else tmp


def deploy_sync(source: dict[str, bytes], dest: CaseInsensitiveFS) -> dict[str, Any]:
    """Sync source (exact casings) onto a case-insensitive dest without dropping.

    Case-only partners are retitled via a temporary name so a later delete of
    the old spelling cannot unlink the only inode (the write-then-delete drop).
    """
    src_fold: dict[str, str] = {}
    for rel in source:
        key = fold(rel)
        if key in src_fold:
            raise ValueError(f"source case collision {src_fold[key]!r} vs {rel!r}")
        src_fold[key] = rel

    before = dest.list_exact()
    ops: list[dict[str, str]] = []

    for drel in list(before):
        if fold(drel) not in src_fold:
            dest.delete(drel)
            ops.append({"op": "delete", "rel": drel})

    for rel, data in sorted(source.items()):
        existing = dest.exact_name(rel)
        if existing is None:
            dest.write(rel, data)
            ops.append({"op": "create", "rel": rel})
            continue
        if existing != rel:
            tmp = _tmp_rel(rel)
            dest.rename(existing, tmp)
            dest.rename(tmp, rel)
            dest.write(rel, data)
            ops.append({"op": "case-rename", "from": existing, "to": rel})
            continue
        dest.write(rel, data)
        ops.append({"op": "update", "rel": rel})

    listing = dest.list_exact()
    return {
        "ops": ops,
        "listing": listing,
        "hashes": {p: dest.sha256(p) for p in listing},
        "before": before,
    }


def lowercase_keyed_copy(source: dict[str, bytes]) -> dict[str, bytes]:
    """Known-broken: identity and dest names are the lowercased path."""
    out: dict[str, bytes] = {}
    for rel, data in source.items():
        out[posix(rel).lower()] = data
    return out


def naive_write_then_delete(source: dict[str, bytes], dest: CaseInsensitiveFS) -> dict[str, Any]:
    """Known-broken order: write new casing (hits old inode), then delete old name."""
    for rel, data in source.items():
        dest.write(rel, data)
    after_write = dest.list_exact()
    for drel in list(after_write):
        if drel not in source:
            dest.delete(drel)
    listing = dest.list_exact()
    return {
        "after_write_listing": after_write,
        "listing": listing,
        "hashes": {p: dest.sha256(p) for p in listing},
        "dropped": True if not any(fold(p) == fold(NEW_REL) for p in listing) else False,
    }


def pass_new_casing(
    dest: CaseInsensitiveFS,
    expected_rel: str,
    expected_sha: str,
    sibling: str = SIBLING,
) -> dict[str, Any]:
    listing = dest.list_exact()
    pair = [p for p in listing if fold(p) == fold(expected_rel)]
    exact_one = pair == [expected_rel]
    got_sha = dest.sha256(expected_rel)
    hash_ok = got_sha == expected_sha
    sibling_ok = sibling in listing
    return {
        "ok": bool(exact_one and hash_ok and sibling_ok),
        "listing": listing,
        "pair": pair,
        "expected_rel": expected_rel,
        "expected_sha256": expected_sha,
        "dest_sha256": got_sha,
        "exact_one_new_casing": exact_one,
        "hash_matches_source": hash_ok,
        "sibling_present": sibling_ok,
    }


def seed_old(dest: CaseInsensitiveFS | None = None) -> CaseInsensitiveFS:
    dest = dest or CaseInsensitiveFS()
    deploy_sync(source_old(), dest)
    return dest


def run_case_only() -> dict[str, Any]:
    dest = seed_old()
    report = deploy_sync(source_case_only(), dest)
    check = pass_new_casing(dest, NEW_REL, sha256_bytes(BLOB_A))
    return {
        "scenario": "case-only-rename-same-content",
        "source_sha256": sha256_bytes(BLOB_A),
        "sync": report,
        "check": check,
        "ok": check["ok"],
    }


def run_content_change() -> dict[str, Any]:
    dest = seed_old()
    report = deploy_sync(source_content_change(), dest)
    check = pass_new_casing(dest, NEW_REL, sha256_bytes(BLOB_B))
    old_content_absent = dest.get(NEW_REL) != BLOB_A
    return {
        "scenario": "content-changing-rename",
        "source_sha256": sha256_bytes(BLOB_B),
        "sync": report,
        "check": check,
        "old_content_absent": old_content_absent,
        "ok": bool(check["ok"] and old_content_absent),
    }


def run_lowercase_copy_must_fail() -> dict[str, Any]:
    copied = lowercase_keyed_copy(source_case_only())
    dest = CaseInsensitiveFS()
    for rel, data in copied.items():
        dest.write(rel, data)
    check = pass_new_casing(dest, NEW_REL, sha256_bytes(BLOB_A))
    listing = dest.list_exact()
    new_casing_absent = NEW_REL not in listing
    return {
        "scenario": "negative-lowercase-keyed-copy",
        "listing": listing,
        "copied_keys": sorted(copied),
        "check": check,
        "pass_criteria_failed": not check["ok"],
        "new_casing_absent": new_casing_absent,
        "ok": (not check["ok"]) and new_casing_absent,
    }


def run_naive_drop() -> dict[str, Any]:
    dest = seed_old()
    report = naive_write_then_delete(source_case_only(), dest)
    pair = [p for p in report["listing"] if fold(p) == fold(NEW_REL)]
    dropped = pair == []
    return {
        "scenario": "naive-write-then-delete-drop",
        "listing": report["listing"],
        "after_write_listing": report["after_write_listing"],
        "pair": pair,
        "dropped": dropped,
        "ok": dropped,
    }
