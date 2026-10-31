#!/usr/bin/env python3
"""Finalize the two receipts after LF normalization: artifacts rows back to
LF-disk truth (bytes = LF size, eol = LF) and replace the disk-truth caveat
with the normalization record. Also reconcile ADV-0117's caveat (it never had
CRLF; remove nothing there)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "command-center"))
import receipt_writer  # noqa: E402

LF_SIZES = {"ADV-0038": 31457, "ADV-0090": 31785}

CAVEAT = (
    "Disk-truth and normalization record (reviewer-verified, content-invariant): the primary "
    "artifacts for ADV-0038 and ADV-0090 were found on disk with CRLF line endings (builder "
    "lane's Windows writer); the unit contract and UNIT-ARTIFACT-MANIFEST hash the CRLF-to-LF "
    "NORMALIZED form, while the program's completion gate (receipt_schema_gate c3) hashes the "
    "RAW on-disk bytes, so the two program instruments could not both agree on a CRLF-on-disk "
    "artifact. The reviewer normalized the two artifacts to LF on disk, verifying before and "
    "after that (1) the normalized sha256 is UNCHANGED (ADV-0038 e18cdc21..., ADV-0090 "
    "ef5e2633...), (2) json.loads content is UNCHANGED, (3) the file is pure LF afterwards. "
    "Content-invariant; the two program instruments now agree. Program-level note surfaced: "
    "the completion gate's raw-bytes sha check (c3) contradicts the unit contract's normalized "
    "hash for any CRLF-on-disk artifact - an instrument inconsistency for the program owner."
)

for uid, size in LF_SIZES.items():
    rpath = REPO / "command-center/receipts" / (uid + ".json")
    with open(rpath, encoding="utf-8") as f:
        receipt = json.load(f)
    for row in receipt.get("artifacts") or []:
        p = REPO / str(row.get("path", ""))
        if not p.is_file():
            continue
        raw = p.read_bytes()
        row["bytes"] = len(raw)
        row["eol"] = "CRLF" if b"\r\n" in raw else "LF"
    closure = receipt["extensions"]["reviewer_closure"]
    closure["caveats"] = [c for c in closure.get("caveats", []) if "Disk-truth labeling" not in c]
    closure["caveats"].append(CAVEAT)
    data = json.dumps(receipt, indent=1, ensure_ascii=False).encode("utf-8")
    receipt_writer.atomic_write_bytes(str(rpath), data)
    print("FINALIZED", uid)
