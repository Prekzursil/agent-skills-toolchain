#!/usr/bin/env python3
"""Probe 1: enumerate size/count gates by reading the rule (AST), not the docs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0089-volume-as-quality-gate-rejection.json"
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def main() -> int:
    live = I.enumerate_gates()
    print(json.dumps(live, sort_keys=True))
    if live["volume_sensitive_count"] < 1:
        print("FAILED:ADV-0089-probe1 no volume-sensitive rules found in source")
        return 1
    if live["named_probe_size_floor_200_count"] < 1:
        print("FAILED:ADV-0089-probe1 expected live ART.stat().st_size < 200 hits")
        return 1
    if not live["p2lib_write_if_valid_size_lt_floor"]:
        print("FAILED:ADV-0089-probe1 _p2lib.write_if_valid size<floor missing")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0089-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0089":
        print("FAILED:ADV-0089-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0089-probe1 self-declared {doc.get('state')}")
        return 1
    if I.CATALOG_SENTINEL not in text:
        print("FAILED:ADV-0089-probe1 catalog sentinel absent")
        return 1
    recorded = doc.get("probe1_live") or {}
    if int(recorded.get("volume_sensitive_count") or -1) != live["volume_sensitive_count"]:
        print(
            "FAILED:ADV-0089-probe1 artifact volume_sensitive_count "
            f"{recorded.get('volume_sensitive_count')} != live {live['volume_sensitive_count']}"
        )
        return 1
    if int(recorded.get("named_probe_size_floor_200_count") or -1) != live[
        "named_probe_size_floor_200_count"
    ]:
        print("FAILED:ADV-0089-probe1 artifact 200-byte floor count drifted")
        return 1
    targets = doc.get("targets") or []
    if len(targets) < 2:
        print("FAILED:ADV-0089-probe1 targets missing")
        return 1
    seen = []
    for t in targets:
        v = t.get("verdict")
        tid = t.get("target_id")
        if v not in ALLOWED:
            print(f"FAILED:ADV-0089-probe1 illegal verdict {tid}={v}")
            return 1
        if tid in seen:
            print(f"FAILED:ADV-0089-probe1 duplicate target {tid}")
            return 1
        seen.append(tid)
    print("SUCCESS:ADV-0089-probe1 enumerated volume-sensitive gates from source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
