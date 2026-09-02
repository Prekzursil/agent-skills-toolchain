#!/usr/bin/env python3
"""Probe 1: independently re-measure the three byte-acquisition routes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = M.REPO / "command-center/confirmation/CNF-0019-byte-route-audit.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size == 0:
        print("FAILED:CNF-0019-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0019":
        print("FAILED:CNF-0019-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if M.COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0019-probe1 completion sentinel absent")
        return 1
    if "SUCCESS:CNF-0019" not in text:
        print("FAILED:CNF-0019-probe1 short sentinel absent")
        return 1

    body = M.payload(doc)
    live = M.measure_once()
    table = live["byte_table"]
    by_route = {row["route"]: row for row in table}
    for name in M.ROUTES:
        if name not in by_route:
            print(f"FAILED:CNF-0019-probe1 missing route {name}")
            return 1
    arch = by_route["git archive"]
    cat = by_route["git cat-file"]
    tree = by_route["worktree"]
    print(
        f"archive bytes={arch['bytes']} crlf={arch['crlf_count']} "
        f"cat-file bytes={cat['bytes']} crlf={cat['crlf_count']} "
        f"worktree bytes={tree['bytes']} crlf={tree['crlf_count']}"
    )
    if arch["crlf_count"] <= 0:
        print("FAILED:CNF-0019-probe1 git archive did not return CRLF")
        return 1
    if cat["crlf_count"] != 0:
        print("FAILED:CNF-0019-probe1 cat-file blob is not LF")
        return 1
    if not live["eol_normalisation"]["routes_identical_after_lf"]:
        print("FAILED:CNF-0019-probe1 routes differ after LF normalisation")
        return 1
    if arch["sha256_lf"] != cat["sha256_lf"] or tree["sha256_lf"] != cat["sha256_lf"]:
        print("FAILED:CNF-0019-probe1 LF-normalised hashes disagree")
        return 1

    art_table = {row["route"]: row for row in body.get("byte_table") or []}
    for name in M.ROUTES:
        a = art_table.get(name) or {}
        b = by_route[name]
        if a.get("bytes") != b["bytes"] or a.get("crlf_count") != b["crlf_count"]:
            print(f"FAILED:CNF-0019-probe1 artifact table mismatch on {name}")
            print(" artifact", a)
            print(" live", b)
            return 1
        if a.get("sha256") != b["sha256"]:
            print(f"FAILED:CNF-0019-probe1 artifact sha256 mismatch on {name}")
            return 1

    if not body.get("eol_normalisation", {}).get("routes_identical_after_lf"):
        print("FAILED:CNF-0019-probe1 artifact eol flag false")
        return 1
    if not body.get("answers", {}).get("archive_returns_crlf"):
        print("FAILED:CNF-0019-probe1 artifact archive_returns_crlf false")
        return 1

    print("identical_after_lf=True archive_crlf>0 cat_file_crlf=0")
    print("SUCCESS:CNF-0019-probe1 three-route table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
