#!/usr/bin/env python3
"""IMP-0125 probe 2: independent provenance walk catches a planted reference.

Reviewer requirement: construct a reference the implementer's index/lockfile
scan does not know about and confirm the second walk catches it (GC keeps).

Also AST-checks that gc_provenance.py does not import gc_index_lockfile.py
and vice versa — the two walks are independently written.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from blob_gc import collect  # noqa: E402
from gc_index_lockfile import scan_index_and_lockfiles  # noqa: E402
from gc_provenance import walk_deploy_provenance  # noqa: E402
from gc_store import (  # noqa: E402
    append_deploy_record,
    list_blob_hexes,
    put_blob,
    set_owner_token,
    write_index,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0125-probe2 {msg}")
    return 1


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    idx_src = MKT / "gc_index_lockfile.py"
    prov_src = MKT / "gc_provenance.py"
    if not idx_src.is_file() or not prov_src.is_file():
        return fail("scanner source missing")
    idx_imps = _imported_modules(idx_src)
    prov_imps = _imported_modules(prov_src)
    if "gc_provenance" in idx_imps:
        return fail(f"index scanner imports provenance walker: {idx_imps}")
    if "gc_index_lockfile" in prov_imps:
        return fail(f"provenance walker imports index scanner: {prov_imps}")
    if "blob_gc" in idx_imps or "blob_gc" in prov_imps:
        return fail("a scanner imports the collector (not independent)")

    with tempfile.TemporaryDirectory(prefix="imp0125-p2-") as tmp:
        root = Path(tmp)
        set_owner_token(root, "probe2-owner")
        planted = put_blob(root, b"IMP-0125-reviewer-planted-provenance-only")
        decoy = put_blob(root, b"IMP-0125-reviewer-true-orphan")
        write_index(root, [])
        append_deploy_record(
            root,
            {
                "live_path": str(root / "reviewer-missing-target"),
                "source_blob_sha": "sha256:" + planted,
                "source_path": "reviewer/planted.md",
                "plugin_version": "reviewer",
                "deployed_at": "2026-08-24T18:00:00Z",
            },
        )

        index_scan = scan_index_and_lockfiles(root)
        prov_scan = walk_deploy_provenance(root)
        index_refs = index_scan.refs_for(planted)
        prov_refs = prov_scan.refs_for(planted)
        if index_refs:
            return fail(
                f"index/lockfile scan saw the planted provenance-only blob: {index_refs}"
            )
        if not prov_refs:
            return fail("provenance walk missed the planted reference")
        if not any("source_blob_sha" in r or "deploy-ledger.jsonl" in r for r in prov_refs):
            return fail(f"provenance refs did not name the ledger: {prov_refs}")

        report = collect(root, execute=True, owner_token="probe2-owner")
        remaining = set(list_blob_hexes(root))
        if planted not in remaining:
            return fail("GC deleted the provenance-only planted blob")
        if decoy in remaining:
            return fail("true orphan was not collected (GC inert)")
        row = next(r for r in report["kept"] if r["digest_hex"] == planted)
        if row["keep_reason"] != "disagreement":
            return fail(f"expected disagreement keep, got {row['keep_reason']}")
        if row["proof"]["agreement"] is True:
            return fail("agreement true on a one-sided reference")
        if not report["dangling_deploy_targets"]:
            return fail("dangling deploy target not listed")

    out = {
        "probe": "probe2-independent-walk",
        "unit_id": "IMP-0125",
        "scanners_do_not_import_each_other": True,
        "index_scanner_imports": sorted(idx_imps),
        "provenance_walker_imports": sorted(prov_imps),
        "planted_blob_index_lockfile_refs": [],
        "planted_blob_provenance_refs_nonempty": True,
        "gc_kept_planted_on_disagreement": True,
        "true_orphan_collected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "independent=True planted_kept=True index_missed=True "
        "provenance_caught=True orphan_deleted=True"
    )
    print("SUCCESS:IMP-0125-probe2 independent walk caught reviewer-planted ref")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
