#!/usr/bin/env python3
"""Named probe 1: live writer + personal field; erasure vs append-only.

Re-runs the isolated write/erase conflict. Independent of probe 2 (prototype
reconciliations). If the adjudication artifact exists, checks it recorded the
same conflict and the catalog sentinel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from conflict import measure  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0045-append-only-vs-erasure-adjudication.json"
SENTINEL = "SUCCESS:ADV-0045"


def _catalog_sentinel() -> str:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0045":
            return str(unit.get("completion_sentinel") or SENTINEL)
    return SENTINEL


def _section(doc: dict, key: str) -> list:
    """Read a list from the receipt, the privacy-dataflow report, or extensions."""
    if isinstance(doc.get(key), list) and doc.get(key):
        return doc[key]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get(key), list) and report.get(key):
        return report[key]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get(key), list) and ext.get(key):
        return ext[key]
    return []


def main() -> int:
    live = measure()
    print(json.dumps(live, sort_keys=True, ensure_ascii=True))
    if not live.get("pass") or not live.get("conflict_demonstrated"):
        print("FAILED:ADV-0045-probe1 conflict not demonstrated")
        return 1
    if not live.get("pii_written_recoverable"):
        print("FAILED:ADV-0045-probe1 planted personal field not recoverable")
        return 1
    if not live.get("control_token_findable"):
        print("FAILED:ADV-0045-probe1 control token not findable (search broken)")
        return 1
    leave = live["leave_in_place"]
    mutate = live["mutate_to_erase"]
    if leave["erasure_achieved"] or not leave["prefix_preserved"]:
        print("FAILED:ADV-0045-probe1 leave-in-place is not the append-only horn")
        return 1
    if not mutate["erasure_achieved"] or mutate["prefix_preserved"]:
        print("FAILED:ADV-0045-probe1 mutate-to-erase is not the mutation horn")
        return 1
    if live.get("wrote_to_live_events"):
        print("FAILED:ADV-0045-probe1 wrote to live EVENTS.jsonl")
        return 1

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            print("FAILED:ADV-0045-probe1 short sentinel absent from artifact")
            return 1
        completion = _catalog_sentinel()
        if completion not in text:
            print("FAILED:ADV-0045-probe1 catalog completion_sentinel absent")
            return 1
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print("FAILED:ADV-0045-probe1 self-declared", doc.get("state"))
            return 1
        targets = {t.get("id"): t for t in _section(doc, "enumerated_targets") if isinstance(t, dict)}
        conflict_t = targets.get("T-CONFLICT") or {}
        if conflict_t.get("verdict") != "CONFIRMED":
            print("FAILED:ADV-0045-probe1 artifact T-CONFLICT not CONFIRMED")
            return 1
        probes = _section(doc, "named_probes")
        if len(probes) < 2:
            print("FAILED:ADV-0045-probe1 artifact missing named probes")
            return 1
        raw = str(probes[0].get("raw_output") or "")
        if "conflict_demonstrated" not in raw:
            print("FAILED:ADV-0045-probe1 artifact probe1 raw_output missing conflict")
            return 1
        controls = {c.get("id"): c for c in _section(doc, "controls") if isinstance(c, dict)}
        if not controls:
            print("FAILED:ADV-0045-probe1 artifact controls missing")
            return 1

    print(
        "conflict_ok=True pii_recoverable="
        f"{live['pii_written_recoverable']} control_findable="
        f"{live['control_token_findable']} mutate_breaks_prefix="
        f"{not mutate['prefix_preserved']}"
    )
    print("SUCCESS:ADV-0045-probe1 conflict: erase requires mutate or leave-in-place")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
