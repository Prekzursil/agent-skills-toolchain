#!/usr/bin/env python3
"""Probe 1: mutation catalogue vs the gate's own suite. Require >=1 KILLED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / E.OUT


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0010-probe1 {msg}")
    return 1


def main() -> int:
    rc = E.main()
    if rc != 0:
        return fail("emit failed")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if E.SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("completion_sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if int(doc.get("killed_count") or 0) < 1:
        return fail("killed_count<1 (suite likely never ran)")
    if doc.get("unit_id") != "ADV-0010":
        return fail(f"unit_id={doc.get('unit_id')}")
    named = doc.get("named_probes") or []
    if len(named) < 2:
        return fail("named_probes < 2")
    hunt = H.hunt()
    print(
        f"re-hunt killed={hunt['killed_count']} survived={hunt['survived_count']} "
        f"baseline_all_pass={hunt['baseline_all_pass']}"
    )
    if hunt["killed_count"] != doc["killed_count"]:
        return fail("re-hunt killed_count drifted from artifact")
    print("SUCCESS:ADV-0010-probe1 mutation hunt (killed>=1, baseline green)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
