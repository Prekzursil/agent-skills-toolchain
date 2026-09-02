#!/usr/bin/env python3
"""IMP-0125 probe 1: referenced blob never collected; dry-run lists proofs.

Two independent signals in this process:
  (1) execute with owner token: index-referenced blob remains on disk
  (2) dry-run report names every unreferenced candidate with both zero-ref proofs
Both-states: unreferenced sibling IS collected; referenced is NOT.
Negative control in this run: lockfile-only blob survives execute.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from blob_gc import collect  # noqa: E402
from gc_store import (  # noqa: E402
    append_deploy_record,
    list_blob_hexes,
    put_blob,
    set_owner_token,
    write_index,
    write_lockfile,
)

from tests.test_gc import (  # noqa: E402
    test_dry_run_lists_every_candidate_with_its_proof,
    test_lockfile_only_reference_survives,
    test_referenced_blob_is_never_collected,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0125-probe1 {msg}")
    return 1


def main() -> int:
    test_referenced_blob_is_never_collected()
    test_dry_run_lists_every_candidate_with_its_proof()
    test_lockfile_only_reference_survives()

    with tempfile.TemporaryDirectory(prefix="imp0125-p1-") as tmp:
        root = Path(tmp)
        set_owner_token(root, "probe1-owner")
        indexed = put_blob(root, b"IMP-0125-probe1-indexed")
        locked = put_blob(root, b"IMP-0125-probe1-locked")
        orphan = put_blob(root, b"IMP-0125-probe1-orphan")
        write_index(
            root,
            [{"name": "p1-idx", "version": "1.0.0", "digest": "sha256:" + indexed}],
        )
        write_lockfile(
            root,
            "p1.lock.json",
            [{"name": "p1-lock", "version": "1.0.0", "blob_digest": "sha256:" + locked}],
        )
        append_deploy_record(
            root,
            {
                "live_path": str(root / "live-missing"),
                "source_blob_sha": "sha256:" + indexed,
                "source_path": "x.md",
                "plugin_version": "1.0.0",
                "deployed_at": "2026-08-24T00:00:00Z",
            },
        )
        dry = collect(root, execute=False)
        before = set(list_blob_hexes(root))
        if dry["mode"] != "dry-run" or dry["deleted"]:
            return fail(f"dry-run not idle: {dry['mode']} deleted={dry['deleted']}")
        cand = {c["digest_hex"] for c in dry["candidates"]}
        if cand != {orphan}:
            return fail(f"dry-run candidates {cand} expected only orphan")
        proof = dry["candidates"][0]["proof"]
        if not (
            proof["index_lockfile"]["zero"]
            and proof["provenance"]["zero"]
            and proof["agreement"]
            and proof["index_lockfile"]["examined"]
        ):
            return fail(f"orphan proof incomplete: {proof}")
        kept_hex = {k["digest_hex"] for k in dry["kept"]}
        if indexed not in kept_hex or locked not in kept_hex:
            return fail(f"referenced blobs missing from kept: {kept_hex}")
        if set(list_blob_hexes(root)) != before:
            return fail("dry-run mutated blobs")

        exe = collect(root, execute=True, owner_token="probe1-owner")
        after = set(list_blob_hexes(root))
        if indexed not in after or locked not in after:
            return fail("referenced blob collected on execute")
        if orphan in after or "sha256:" + orphan not in exe["deleted"]:
            return fail("unreferenced blob survived execute")
        if "sha256:" + indexed in exe["deleted"] or "sha256:" + locked in exe["deleted"]:
            return fail("referenced digest listed as deleted")

    out = {
        "probe": "probe1-referenced-and-dry-run",
        "unit_id": "IMP-0125",
        "catalog_tests": [
            "test_referenced_blob_is_never_collected",
            "test_dry_run_lists_every_candidate_with_its_proof",
            "test_lockfile_only_reference_survives",
        ],
        "signal1_referenced_survives_execute": True,
        "signal2_dry_run_lists_orphan_with_both_zero_proofs": True,
        "both_states_orphan_collected_referenced_kept": True,
        "negative_control_lockfile_only_survives": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "referenced_kept=True dry_run_proofs=True both_states=True "
        "lockfile_only_survives=True"
    )
    print("SUCCESS:IMP-0125-probe1 referenced never collected; dry-run proofs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
