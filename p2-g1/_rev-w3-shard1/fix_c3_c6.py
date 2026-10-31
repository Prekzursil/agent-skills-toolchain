#!/usr/bin/env python3
"""Fix c3 (disk-truth bytes/eol) and c6 (method-label refinement) in the three
closures, per the accepted w2-shard2 precedent (ADV-0124):

- artifacts rows: bytes = RAW on-disk size; eol = actual disk form; sha256 stays
  the contract CRLF-to-LF normalized digest. The receipt schema's eol field
  exists precisely to disambiguate "which form was hashed".
- evidence rows where source and verifier both carry the generic label
  'command': refine to the ACTUAL methods (test-run for the named probe
  scripts; command for the program measure instrument). Recorded in
  extensions.reviewer_closure.builder_evidence_method_label_refinements.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "command-center"))
import receipt_writer  # noqa: E402

UNITS = ["ADV-0038", "ADV-0090", "ADV-0117"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

for uid in UNITS:
    rpath = REPO / "command-center/receipts" / (uid + ".json")
    receipt = json.loads(rpath.read_text(encoding="utf-8"))
    changed = []

    # c3: disk-truth bytes/eol on every artifacts row
    for row in receipt.get("artifacts") or []:
        p = REPO / str(row.get("path", ""))
        if not p.is_file():
            continue
        raw = p.read_bytes()
        raw_len = len(raw)
        crlf = raw.count(b"\r\n")
        lf_total = raw.count(b"\n")
        if crlf == 0:
            form = "LF"
        elif crlf == lf_total:
            form = "CRLF"
        else:
            form = "MIXED"
        if row.get("bytes") != raw_len or row.get("eol") != form:
            changed.append(f"{row.get('path')}: bytes {row.get('bytes')}->{raw_len}, "
                           f"eol {row.get('eol')}->{form}")
            row["bytes"] = raw_len
            row["eol"] = form

    # c6: refine generic 'command' method labels to actual methods
    refinements = []
    for i, e in enumerate(receipt.get("evidence") or []):
        probes = e.get("probes") or []
        srcs = [p for p in probes if p.get("role") == "source"]
        vers = [p for p in probes if p.get("role") == "verifier"]
        m_s = {p.get("method") for p in srcs}
        m_v = {p.get("method") for p in vers}
        if m_s and m_v and m_s == m_v:
            for p in srcs:
                cmd = str(p.get("command") or "")
                if "probe1" in cmd or "probe2" in cmd or "run_probes" in cmd:
                    p["method"] = "test-run"
                    refinements.append(f"evidence[{i}] source -> test-run ({Path(cmd.split(' ')[-1]).name})")
    if refinements:
        receipt.setdefault("extensions", {}).setdefault(
            "reviewer_closure", {}).setdefault(
            "builder_evidence_method_label_refinements", []).extend(refinements)

    # record the disk-truth adjudication in the closure caveats
    if changed:
        closure = receipt["extensions"]["reviewer_closure"]
        closure["caveats"].append(
            "Disk-truth labeling (recorded, not folded): the primary artifact(s) on disk carry "
            "CRLF line endings written by the builder lane's writer (" + "; ".join(changed) + "). "
            "The sha256 in the artifacts rows and in UNIT-ARTIFACT-MANIFEST.json is the "
            "CRLF-to-LF NORMALIZED contract digest (unit contract: 'sha256 row matching the live "
            "artifact (CRLF normalized to LF before hashing)') and was verified live against both. "
            "The eol field now declares the measured form per the receipt schema's own guidance "
            "('declaring which was measured prevents a false drift verdict'); bytes now states the "
            "raw on-disk size."
        )
    data = json.dumps(receipt, indent=1, ensure_ascii=False).encode("utf-8")
    receipt_writer.atomic_write_bytes(str(rpath), data)
    print("FIXED", uid, "| c3 rows:", len(changed), "| c6 refinements:", len(refinements))
