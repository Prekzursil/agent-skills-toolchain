#!/usr/bin/env python3
"""Probe 1: live detector control, both-states, and 127-vs-1 exit discipline.

Re-queries api.osv.dev. Does not treat a missing osv-scanner binary as clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scanner as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0153.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0153-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0153":
        print("FAILED:CNF-0153-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0153-probe1 self-declared", doc.get("state"))
        return 1

    rc127 = S.missing_osv_scanner_exit()
    class127 = S.classify_exit(rc127)
    if class127 != "tool-not-installed":
        print(f"FAILED:CNF-0153-probe1 expected 127 tool-not-installed, got rc={rc127} class={class127}")
        return 1

    try:
        vuln, vmeta = S.query_osv_one("lodash", "4.17.11")
        clean, cmeta = S.query_osv_one("bytes", "3.1.2")
    except S.BlockedExternal as exc:
        print(f"FAILED:CNF-0153-probe1 blocked prerequisite={exc.prerequisite}")
        return 1

    v_exit = S.findings_to_exit(len(vuln))
    c_exit = S.findings_to_exit(len(clean))
    if not vuln:
        print("FAILED:CNF-0153-probe1 detector-failure: lodash@4.17.11 silent (offline-empty)")
        return 1
    if clean:
        print("FAILED:CNF-0153-probe1 both-states: bytes@3.1.2 not clean", [f["id"] for f in clean])
        return 1
    if S.classify_exit(v_exit) != "findings":
        print("FAILED:CNF-0153-probe1 findings not mapped to exit 1")
        return 1
    if S.classify_exit(c_exit) != "clean":
        print("FAILED:CNF-0153-probe1 clean not mapped to exit 0")
        return 1
    if class127 == S.classify_exit(v_exit) or class127 == S.classify_exit(c_exit):
        print("FAILED:CNF-0153-probe1 conflated 127 with findings or clean")
        return 1

    dc = doc.get("detector_control") or {}
    if not (dc.get("known_vulnerable") or {}).get("n_advisories"):
        print("FAILED:CNF-0153-probe1 artifact detector n_advisories missing")
        return 1
    if (dc.get("known_clean") or {}).get("n_advisories") != 0:
        print("FAILED:CNF-0153-probe1 artifact known-clean not 0")
        return 1
    snap = ((doc.get("evidence") or {}).get("snapshot") or {})
    if not snap.get("identifier") or not snap.get("query_timestamp_utc"):
        print("FAILED:CNF-0153-probe1 snapshot identifier/timestamp missing")
        return 1
    if doc.get("stored_green_is_control_for_today") is True:
        print("FAILED:CNF-0153-probe1 stored green claimed as today's control")
        return 1

    summary = {
        "probe": "probe1-detector-both-states-exitcodes",
        "unit_id": "CNF-0153",
        "osv_scanner_rc": rc127,
        "osv_scanner_class": class127,
        "lodash_n": len(vuln),
        "lodash_ids": [f["id"] for f in vuln],
        "bytes_n": len(clean),
        "lodash_http_date": vmeta.get("http_date"),
        "bytes_http_date": cmeta.get("http_date"),
        "exit_classes_distinct": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0153-probe1 detector both-states and 127-vs-1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
