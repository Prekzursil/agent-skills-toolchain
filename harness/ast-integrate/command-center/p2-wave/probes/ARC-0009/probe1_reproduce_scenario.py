#!/usr/bin/env python3
"""Probe 1: reproduce the silent-loss scenario as an executable procedure.

Both-states: A1 omits the unlisted orphan with no error; after listing,
both skills load. A2 generated-SSOT completeness fires only on the unlisted
state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A1/REFUTATION.json"


def main() -> int:
    run = S.run_scenario()
    print(json.dumps({k: run[k] for k in sorted(run) if k != "pass"}, sort_keys=True))
    if not run.get("pass"):
        print("FAILED:ARC-0009-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0009-probe1 REFUTATION.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0009-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("silent_loss_under_a1") or rec.get("silent_loss_under_a1")
    ) and (
        rec.get("a2_generated_ssot_catches") or rec.get("a2_generated_ssot_catches")
    ) and (
        rec.get("repaired_both_load") or rec.get("repaired_both_load")
    )
    if not rec_ok:
        print("FAILED:ARC-0009-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0009-probe1 procedure too short")
        return 1
    a1u = run["a1_unlisted"]
    if a1u["errors"] or a1u["warnings"]:
        print("FAILED:ARC-0009-probe1 A1 was not silent")
        return 1
    if "skill.listed" not in a1u["loaded_ids"]:
        print("FAILED:ARC-0009-probe1 listed skill not loaded")
        return 1
    print(
        "fired_on_unlisted="
        f"{bool(run.get('silent_loss_under_a1') or run.get('silent_loss_under_a1'))} "
        f"a2={bool(run.get('a2_generated_ssot_catches') or run.get('a2_generated_ssot_catches'))} "
        f"silent_on_listed={bool(run.get('repaired_both_load') or run.get('repaired_both_load'))}"
    )
    print("SUCCESS:ARC-0009-probe1 silent-loss scenario reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
