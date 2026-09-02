#!/usr/bin/env python3
"""Probe 1: recompute snapshot-versus-claim date comparison from stored CDX rows."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from recover import (  # noqa: E402
    AFTER,
    ART,
    BEFORE,
    NONE,
    REPO,
    SENTINEL,
    artifact_errors,
    build_recovery_table,
    hub_capture_errors,
    load_artifact,
    load_corpus,
    unrecoverable_rows,
)


def main() -> int:
    corpus = load_corpus()
    table = build_recovery_table(corpus)
    doc = load_artifact()
    errs = artifact_errors(doc, table)
    errs.extend(hub_capture_errors())

    relations = {str(r.get("snapshot_vs_claim")) for r in table}
    if BEFORE not in relations:
        errs.append("no SNAPSHOT-BEFORE-CLAIM row")
    if NONE not in relations:
        errs.append("no NO-SNAPSHOT row")
    bad_after = [
        r.get("id")
        for r in table
        if r.get("snapshot_vs_claim") == AFTER and r.get("after_claim_mismatch") is not True
    ]
    if bad_after:
        errs.append(f"after-claim not flagged: {bad_after}")

    for row in table:
        if row.get("snapshot_vs_claim") == AFTER and row.get("contemporaneous_read_proof"):
            errs.append(f"{row.get('id')} after-claim treated as contemporaneous")
        if row.get("unrecoverable") and row.get("cdx_row_count"):
            errs.append(f"{row.get('id')} unrecoverable but has CDX rows")

    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        errs.append("sentinel missing")

    rel = ART.relative_to(REPO).as_posix()
    payload = {
        "artifact": rel,
        "rows": len(table),
        "relations": sorted(relations),
        "unrecoverable": len(unrecoverable_rows(table)),
        "errors": errs,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if errs:
        print("FAILED:RES-0117-probe1 " + "; ".join(errs[:8]))
        return 1
    print(
        "SUCCESS:RES-0117-probe1 date-compare "
        f"rows={len(table)} unrecoverable={len(unrecoverable_rows(table))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
