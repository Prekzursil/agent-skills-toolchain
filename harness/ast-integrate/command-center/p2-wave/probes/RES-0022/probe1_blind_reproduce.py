#!/usr/bin/env python3
"""Probe 1: re-measure every row from raw docs/commands; ignore sibling prose."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from measure import measure_one  # noqa: E402
from overclaim import hunt_view  # noqa: E402
from statements import STATEMENTS  # noqa: E402

ART = REPO / "command-center/research/RES-0022.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0022-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:RES-0022" not in text:
        print("FAILED:RES-0022-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    view = hunt_view(doc)
    table = {
        r["id"]: r
        for r in view.get("contradiction_table") or []
        if isinstance(r, dict) and r.get("id")
    }
    if len(table) < 20:
        print(f"FAILED:RES-0022-probe1 table size {len(table)}")
        return 1

    mismatches = 0
    for stmt in STATEMENTS:
        sid = stmt["id"]
        fresh = measure_one(sid)
        prior = table.get(sid) or {}
        # Blind: do not read prior rationale/prose; only compare verdict + sha pin.
        same = fresh.get("verdict") == prior.get("verdict")
        sha_ok = len(str(prior.get("doc_sha256") or "")) == 64
        cmd_ok = len(str(prior.get("reproducing_command") or "")) >= 16
        print(
            f"{sid} fresh={fresh.get('verdict')} artifact={prior.get('verdict')} "
            f"same={same} sha_ok={sha_ok} cmd_ok={cmd_ok}"
        )
        if not same or not sha_ok or not cmd_ok:
            mismatches += 1
        if prior.get("verdict") == "CONTRADICTED":
            if fresh.get("verdict") != "CONTRADICTED":
                print(f"FAILED:RES-0022-probe1 {sid} contradiction not reproducible")
                return 1
            if not str(fresh.get("command_output") or "").strip():
                print(f"FAILED:RES-0022-probe1 {sid} empty reproduce output")
                return 1

    if mismatches:
        print(f"FAILED:RES-0022-probe1 verdict drift mismatches={mismatches}")
        return 1
    print("SUCCESS:RES-0022-probe1 blind reproduce")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
