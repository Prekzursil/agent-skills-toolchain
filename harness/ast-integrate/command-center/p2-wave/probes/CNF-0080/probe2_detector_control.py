#!/usr/bin/env python3
"""Probe 2: reviewer re-runs DETECTOR CONTROL on the known-broken dry-run.

Does not re-read the conclusion as evidence. Re-executes the omitted-delete
fixture and requires the probe to fire. Honest shared-plan dry-run must stay
silent (exact key match).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0080-dryrun-parity.json"


def main() -> int:
    lying = S.lying_detector()
    honest = S.honest_parity()
    print(
        f"detector_fired={lying['p0_filed']} "
        f"omitted={lying['omitted_destructive']} "
        f"honest_silent={honest['keys_match'] and not honest['omitted_destructive']}"
    )
    checks = [
        ("known-broken fires", lying["p0_filed"] is True),
        ("omitted victim.txt", any(a.get("path") == "victim.txt" for a in lying["omitted_destructive"])),
        ("honest keys match", honest["keys_match"] is True),
        ("honest no omitted delete", honest["omitted_destructive"] == []),
        ("honest dry-run wrote nothing", honest["dry_run_zero_writes"] is True),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:CNF-0080-probe2 {name}")
            return 1
    if not ART.is_file():
        print("FAILED:CNF-0080-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:CNF-0080-probe2 reviewer verdict not PASS")
        return 1
    broken = S.report_field(doc, "known_broken_fixture") or {}
    if broken.get("p0_filed") is not True:
        print("FAILED:CNF-0080-probe2 artifact did not record detector fire")
        return 1
    print("SUCCESS:CNF-0080-probe2 detector-control known-broken omitted delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
