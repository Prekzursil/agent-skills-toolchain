"""Garbage collection for unreferenced marketplace blobs (IMP-0125)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gc_index_lockfile import scan_index_and_lockfiles
from gc_provenance import walk_deploy_provenance
from gc_store import delete_blob, list_blob_hexes, read_owner_token


class OwnerTokenError(PermissionError):
    pass


def collect(
    root: Path,
    *,
    execute: bool = False,
    owner_token: str | None = None,
) -> dict[str, Any]:
    root = Path(root)
    index_scan = scan_index_and_lockfiles(root)
    prov_scan = walk_deploy_provenance(root)
    index_hexes = index_scan.all_hexes()
    prov_hexes = prov_scan.all_hexes()
    live = list_blob_hexes(root)
    candidates: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    deleted: list[str] = []
    for digest in live:
        idx_refs = index_scan.refs_for(digest)
        prov_refs = prov_scan.refs_for(digest)
        idx_zero = len(idx_refs) == 0
        prov_zero = len(prov_refs) == 0
        neither = idx_zero and prov_zero
        one_sided = (not idx_zero) ^ (not prov_zero)
        proof = {
            "index_lockfile": {
                "zero": idx_zero,
                "examined": True,
                "refs": idx_refs,
            },
            "provenance": {
                "zero": prov_zero,
                "examined": True,
                "refs": prov_refs,
            },
            "agreement": idx_zero == prov_zero,
        }
        row = {
            "digest_hex": digest,
            "digest": "sha256:" + digest,
            "proof": proof,
        }
        if neither:
            row["keep_reason"] = None
            candidates.append(row)
        elif one_sided:
            row["keep_reason"] = "disagreement"
            kept.append(row)
        else:
            row["keep_reason"] = "referenced"
            kept.append(row)
    if execute:
        expected = read_owner_token(root)
        if not owner_token or owner_token != expected:
            raise OwnerTokenError("owner token required for execute")
        for row in candidates:
            delete_blob(root, row["digest_hex"])
            deleted.append("sha256:" + row["digest_hex"])
        mode = "execute"
    else:
        mode = "dry-run"
    return {
        "mode": mode,
        "deleted": deleted,
        "candidates": candidates,
        "kept": kept,
        "dangling_deploy_targets": list(prov_scan.dangling),
        "index_hex_count": len(index_hexes),
        "provenance_hex_count": len(prov_hexes),
    }
