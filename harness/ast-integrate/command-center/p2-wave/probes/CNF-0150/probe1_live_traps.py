#!/usr/bin/env python3
"""Probe 1: re-run the four named traps live and match the receipt fingerprints."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0150.json"
REQUIRED_DIVERGENT = {
    "cmd-shim-presence",
    "msys-sdcard-intact",
    "crlf-agent-sh",
    "ps-caret-git-ref",
}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0150-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0150-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0150" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0150-probe1 sentinel absent")
        return 1
    live = M.run_live()
    payload = M.payload_of(doc)
    recorded = M.cell_map(doc)
    fresh = M.cell_map(live)
    mismatches = []
    for key, cell in fresh.items():
        rec = recorded.get(key)
        if rec is None:
            mismatches.append(f"missing {key}")
            continue
        if rec.get("verdict") != cell["verdict"]:
            mismatches.append(f"{key} verdict {rec.get('verdict')} != live {cell['verdict']}")
        if rec.get("fingerprint") != cell["fingerprint"]:
            mismatches.append(
                f"{key} fingerprint {rec.get('fingerprint')!r} != live {cell['fingerprint']!r}"
            )
        if rec.get("verdict") == "FAIL" and len(str(rec.get("message") or "")) < 8:
            mismatches.append(f"{key} FAIL without verbatim message")
    if mismatches:
        print("FAILED:CNF-0150-probe1 live/receipt mismatch")
        print("\n".join(mismatches[:20]))
        return 1
    live_div = set(live["divergent_claims"])
    rec_div = set(payload.get("divergent_claims") or doc.get("divergent_claims") or [])
    if not REQUIRED_DIVERGENT.issubset(live_div):
        print(f"FAILED:CNF-0150-probe1 traps not divergent: {sorted(live_div)}")
        return 1
    if live_div != rec_div:
        print(f"FAILED:CNF-0150-probe1 divergent set drift live={live_div} rec={rec_div}")
        return 1
    shim_ps = fresh[("cmd-shim-presence", "powershell-7")]
    shim_gb = fresh[("cmd-shim-presence", "git-bash-msys")]
    if shim_ps["fingerprint"] != "shim-found" or shim_gb["fingerprint"] != "shim-missed":
        print("FAILED:CNF-0150-probe1 cmd-shim both-states dead")
        return 1
    sd_gb = fresh[("msys-sdcard-intact", "git-bash-msys")]
    sd_wsl = fresh[("msys-sdcard-intact", "wsl-gnu-bash")]
    if sd_gb["fingerprint"] != "rewritten:/sdcard" or sd_wsl["fingerprint"] != "intact:/sdcard":
        print("FAILED:CNF-0150-probe1 msys sdcard both-states dead")
        return 1
    data_gb = fresh[("msys-data-nopathconv", "git-bash-msys")]
    if data_gb["fingerprint"] != "intact:/data" or data_gb["verdict"] != "PASS":
        print("FAILED:CNF-0150-probe1 MSYS_NO_PATHCONV scoped call did not preserve /data")
        return 1
    cr_wsl = fresh[("crlf-agent-sh", "wsl-gnu-bash")]
    cr_gb = fresh[("crlf-agent-sh", "git-bash-msys")]
    if cr_wsl["fingerprint"] != "crlf-gnu-rejected" or cr_gb["fingerprint"] != "crlf-igncr-accepted":
        print("FAILED:CNF-0150-probe1 CRLF detector not discriminating")
        return 1
    caret_ps = fresh[("ps-caret-git-ref", "powershell-7")]
    caret_wsl = fresh[("ps-caret-git-ref", "wsl-gnu-bash")]
    if caret_ps["fingerprint"] != "caret-ate-parent" or caret_wsl["fingerprint"] != "caret-kept-parent":
        print("FAILED:CNF-0150-probe1 caret trap not live")
        return 1
    out = {
        "probe": "probe1-live-traps",
        "unit_id": "CNF-0150",
        "cells": len(fresh),
        "divergent": sorted(live_div),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0150-probe1 live traps match receipt fingerprints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
