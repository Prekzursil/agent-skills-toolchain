#!/usr/bin/env python3
"""Probe 1: re-run every case probe; require decisive output matching the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adjudicate import adjudicate_all  # noqa: E402
from check import SENTINEL, check_artifact  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0119-disagreement-adjudication.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0119-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0119":
        print("FAILED:CNF-0119-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0119-probe1 sentinel absent")
        return 1
    ok, why = check_artifact(doc)
    if not ok:
        print(f"FAILED:CNF-0119-probe1 check {why}")
        return 1
    live = {row["id"]: row for row in adjudicate_all()}
    stored = {row["id"]: row for row in doc.get("cases") or []}
    if set(live) != set(stored):
        print(f"FAILED:CNF-0119-probe1 case-id mismatch live={sorted(live)} stored={sorted(stored)}")
        return 1
    for cid, row in live.items():
        got = stored[cid]
        if not str(row["decisive_probe"].get("output") or "").strip():
            print(f"FAILED:CNF-0119-probe1 {cid} empty live probe output")
            return 1
        if row["decisive_probe"]["supports"] != got["decisive_probe"]["supports"]:
            print(f"FAILED:CNF-0119-probe1 {cid} supports drift")
            return 1
        if row["classification"] != got["classification"]:
            print(f"FAILED:CNF-0119-probe1 {cid} classification drift")
            return 1
        if row["original_wording"] != got["original_wording"]:
            print(f"FAILED:CNF-0119-probe1 {cid} original_wording drift")
            return 1
        if row["classification"] == "overclaim":
            if not got.get("correctly_scoped_statement"):
                print(f"FAILED:CNF-0119-probe1 {cid} missing scoped sentence")
                return 1
        print(
            f"{cid} classification={row['classification']} "
            f"supports={row['decisive_probe']['supports']} "
            f"code_was_fine={row['code_was_fine']}"
        )
    print(f"cases={len(live)} {why}")
    print("SUCCESS:CNF-0119-probe1 decisive probes re-ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
