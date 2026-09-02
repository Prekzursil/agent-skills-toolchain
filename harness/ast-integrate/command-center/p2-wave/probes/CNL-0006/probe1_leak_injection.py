#!/usr/bin/env python3
"""Probe 1: inject a partition-violating reference; the checker must catch it.

Signal: canary / paraphrase string search (independent of atom_refs).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from instances import all_instances  # noqa: E402
from leak import check_transcript, inject_violation  # noqa: E402
from scenario import INJECTIONS, dump_fixtures, good_events  # noqa: E402

RAW = HERE / "probe1-leak.raw.json"


def main() -> int:
    dump_fixtures()
    rows = []
    failed = False
    for name, partition in all_instances().items():
        spec = INJECTIONS[name]
        good = good_events(name, partition)
        silent = check_transcript(partition, good)
        bad = inject_violation(good, partition=partition, mode="canary_only", **spec)
        fired = check_transcript(partition, bad)
        canary_hits = [f for f in fired if f.signal == "canary_or_paraphrase"]
        row = {
            "instance": name,
            "silent_on_good": silent == [],
            "good_finding_count": len(silent),
            "injected": spec,
            "fired_on_injected": bool(fired),
            "canary_signal_fired": bool(canary_hits),
            "finding": (canary_hits[0].to_json() if canary_hits else None),
        }
        rows.append(row)
        print(
            f"instance={name} silent_on_good={row['silent_on_good']} "
            f"fired_on_injected={row['fired_on_injected']} "
            f"canary_signal={row['canary_signal_fired']}"
        )
        if silent:
            print(f"  unexpected good findings: {silent}")
            failed = True
        if not canary_hits:
            print("  injection was not caught by canary/paraphrase search")
            failed = True
        else:
            hit = canary_hits[0]
            if hit.atom_id != spec["atom_id"] or hit.seat != spec["seat"]:
                print(f"  finding mismatch {hit.to_json()}")
                failed = True
    RAW.write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:CNL-0006-probe1 leak injection")
        return 1
    print("SUCCESS:CNL-0006-probe1 leak injection caught on all three instances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
