#!/usr/bin/env python3
"""Probe 1: packed-byte inventory excludes .git / caches / transcripts / credentials.

Evidence signal (1): set intersection of packed archive paths with the excluded
class is empty — computed from the packed bytes, not from the source tree.
Evidence signal (2): credential-shaped scan of those packed bytes returns zero
hits. Source tree is deliberately dirty so a tree-side filter cannot fake this.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from fixture import build_certified_tree  # noqa: E402
from marketplace.publication import (  # noqa: E402
    emit_payload,
    inventory_from_packed,
    inventory_gate,
    pack_tree,
    paths_matching_excluded,
    scan_packed_credentials,
)

REQUIRED_FIELDS = (
    "identity",
    "version",
    "permissions",
    "provenance",
    "sbom_entry",
    "licence",
    "benchmark_evidence",
    "lineage",
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0208-p1-") as td:
        root = build_certified_tree(Path(td) / "src", plant_source_junk=True)
        packed = pack_tree(root)
        inventory = inventory_from_packed(packed.archive)
        # Oracle is the archive listing, recomputed independently of PackResult.
        intersection = paths_matching_excluded(inventory)
        creds = scan_packed_credentials(packed.archive)
        gate = inventory_gate(packed.archive)
        payload = emit_payload(root)

    source_had_git = any(p.startswith(".git/") or p == ".git" for p in packed.omitted_excluded)
    source_had_cache = any(
        "__pycache__" in p or p.startswith(".cache/") for p in packed.omitted_excluded
    )
    source_had_transcript = any("transcripts/" in p or p.endswith(".transcript") for p in packed.omitted_excluded)

    missing = [k for k in REQUIRED_FIELDS if k not in payload]
    pub = payload.get("publication") or {}

    report = {
        "probe": "probe1-packed-inventory",
        "unit_id": "IMP-0208",
        "packed_path_count": len(inventory),
        "packed_paths": inventory,
        "excluded_intersection": intersection,
        "excluded_intersection_empty": intersection == [],
        "credential_hit_count": len(creds),
        "credential_hits": [{"path": h.path, "pattern_id": h.pattern_id} for h in creds],
        "gate_ok": gate.ok,
        "source_was_dirty": {
            "git": source_had_git,
            "cache": source_had_cache,
            "transcript": source_had_transcript,
        },
        "payload_fields_present": missing == [],
        "missing_payload_fields": missing,
        "owner_gated": pub.get("owner_gated") is True,
        "published": pub.get("published") is False,
        "publication_state": pub.get("state"),
        "identity": payload.get("identity"),
        "version": payload.get("version"),
        "packed_sha256": (payload.get("packed") or {}).get("sha256"),
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if not source_had_git or not source_had_cache or not source_had_transcript:
        print("FAILED:IMP-0208-probe1 source fixture was not dirty; control is vacuous")
        return 1
    if intersection:
        print(f"FAILED:IMP-0208-probe1 excluded intersection nonempty {intersection}")
        return 1
    if creds:
        print("FAILED:IMP-0208-probe1 credential-shaped hits in packed bytes")
        return 1
    if not gate.ok:
        print("FAILED:IMP-0208-probe1 inventory gate refused a clean pack")
        return 1
    if missing:
        print(f"FAILED:IMP-0208-probe1 payload missing {missing}")
        return 1
    if pub.get("published") is not False or pub.get("owner_gated") is not True:
        print("FAILED:IMP-0208-probe1 emit published without owner gate")
        return 1
    if ".git/config" in inventory or "transcripts/session.transcript" in inventory:
        print("FAILED:IMP-0208-probe1 packed inventory still lists excluded paths")
        return 1
    print(
        "SUCCESS:IMP-0208-probe1 packed inventory ∩ excluded = empty; "
        "credential scan = 0; source was dirty"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
