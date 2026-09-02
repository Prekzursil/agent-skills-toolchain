#!/usr/bin/env python3
"""Probe 2: git-blob (or LF stand-in) vs worktree; CRLF-only is not a data defect."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import golden as G  # noqa: E402

REPORT = REPO / G.OUT_REL


def main() -> int:
    lf_doc = b'{"id":"enc-control","n":1}\n'
    crlf_doc = lf_doc.replace(b"\n", b"\r\n")
    data_doc = b'{"id":"enc-control","n":2}\n'
    identical = G.classify_surfaces(lf_doc, lf_doc)
    crlf_only = G.classify_surfaces(crlf_doc, lf_doc)
    data = G.classify_surfaces(data_doc, lf_doc)
    if identical != "identical":
        print(f"FAILED:ARC-0112-probe2 identical={identical}")
        return 1
    if crlf_only != "crlf-only":
        print(f"FAILED:ARC-0112-probe2 crlf misclassified as {crlf_only}")
        return 1
    if data != "data-divergence":
        print(f"FAILED:ARC-0112-probe2 data mutation silent kind={data}")
        return 1

    live = G.encoding_pair(G.CATALOG_REL)
    if not live.get("present"):
        print("FAILED:ARC-0112-probe2 catalogue absent")
        return 1
    if live.get("kind") not in {"identical", "crlf-only", "data-divergence"}:
        print(f"FAILED:ARC-0112-probe2 live kind={live.get('kind')}")
        return 1
    if live.get("kind") == "crlf-only":
        # Encoding-only: must not be treated as a catalogue data defect.
        print("live_catalog_crlf_only=True (not a data defect)")

    # Worktree CRLF mutant of the real catalogue must not be a data defect.
    raw = (REPO / G.CATALOG_REL).read_bytes()
    blob = G.lf(raw)
    mutant = raw.replace(b"\n", b"\r\n") if b"\r\n" not in raw else raw
    mutant_kind = G.classify_surfaces(mutant, blob)
    if mutant_kind != "crlf-only" and mutant != raw:
        print(f"FAILED:ARC-0112-probe2 catalogue CRLF mutant kind={mutant_kind}")
        return 1
    if mutant == raw:
        # Already CRLF: flipping to LF must be encoding-only, not data.
        lf_kind = G.classify_surfaces(blob, mutant)
        if lf_kind != "crlf-only":
            print(f"FAILED:ARC-0112-probe2 already-CRLF flip kind={lf_kind}")
            return 1

    # A real data mutant (one byte in a JSON string) must fire as data.
    flipped = bytearray(blob)
    try:
        idx = flipped.index(ord("A"))
    except ValueError:
        idx = 0
        while idx < len(flipped) and flipped[idx] in b" \n\r\t{}[]:,\"":
            idx += 1
    flipped[idx] = flipped[idx] ^ 0x01
    data_kind = G.classify_surfaces(bytes(flipped), blob)
    if data_kind != "data-divergence":
        print(f"FAILED:ARC-0112-probe2 one-byte mutant kind={data_kind}")
        return 1

    enc = G.encoding_control()
    if not enc.get("crlf_not_misread_as_data"):
        print("FAILED:ARC-0112-probe2 encoding_control.crlf_not_misread_as_data=false")
        return 1
    if len(enc.get("surfaces") or []) < 2:
        print("FAILED:ARC-0112-probe2 need worktree and blob surfaces")
        return 1

    if REPORT.is_file():
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        reported = doc.get("encoding_control") or {}
        if reported.get("crlf_not_misread_as_data") is not True:
            print("FAILED:ARC-0112-probe2 report encoding flag false")
            return 1
        if "SUCCESS:ARC-0112" not in json.dumps(doc):
            print("FAILED:ARC-0112-probe2 sentinel absent from report")
            return 1

    print(
        f"git_available={enc.get('git_available')} blob_source={live.get('blob_source')} "
        f"live_kind={live.get('kind')} planted identical={identical} "
        f"crlf_only={crlf_only} data={data} mutant={mutant_kind} "
        f"one_byte={data_kind}"
    )
    print("SUCCESS:ARC-0112-probe2 encoding control git-blob-or-lf vs worktree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
