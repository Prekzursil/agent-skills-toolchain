#!/usr/bin/env python3
"""Probe 1: classification table has one citation per row; captures re-hash."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import evidence as E  # noqa: E402


def main() -> int:
    path = E.REPO / E.ARTIFACT_REL
    if not path.is_file():
        print("FAILED:RES-0032-probe1 artifact missing")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    if E.SENTINEL not in path.read_text(encoding="utf-8"):
        print("FAILED:RES-0032-probe1 sentinel absent")
        return 1
    rows = doc.get("rows") or doc.get("platform_classification_table") or []
    if not isinstance(rows, list) or len(rows) < 3:
        print("FAILED:RES-0032-probe1 table too small")
        return 1
    ok, why = C.citations_complete(rows)
    print(f"citations_complete={ok} {why}")
    if not ok:
        print("FAILED:RES-0032-probe1 citations")
        return 1
    print("platform\tfamily\tverdict\tpin\tcitation")
    for row in rows:
        cit = row.get("citation") or {}
        url = cit.get("url") or row.get("citation_url")
        pin = row.get("version_or_commit") or ""
        print(
            f"{row.get('label') or row.get('platform')}\t{row.get('family')}\t"
            f"{row.get('verdict')}\t{pin}\t{url}"
        )
        sha = str(cit.get("sha256") or row.get("sha256") or "")
        cap = str(cit.get("capture_path") or "")
        if not cap:
            print("FAILED:RES-0032-probe1 capture_path missing")
            return 1
        live_sha, _ = E.digest_file(E.REPO / cap)
        if live_sha != sha:
            print(f"FAILED:RES-0032-probe1 sha mismatch {cap}")
            return 1
        snippet = str(row.get("snippet") or "")
        blob = (E.REPO / cap).read_bytes()
        if snippet and snippet.encode("utf-8") not in blob and snippet not in blob.decode(
            "utf-8", "replace"
        ):
            print(f"FAILED:RES-0032-probe1 snippet missing in {cap}")
            return 1
        pin_s = str(pin)
        if not pin_s.strip():
            print("FAILED:RES-0032-probe1 unversioned row")
            return 1
    table = doc.get("platform_classification_table") or []
    if len(table) != len(rows):
        print("FAILED:RES-0032-probe1 table/rows length mismatch")
        return 1
    print(f"table_rows={len(rows)} citation_per_row=true")
    print("SUCCESS:RES-0032-probe1 classification table citations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
