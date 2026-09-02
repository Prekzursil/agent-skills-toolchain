#!/usr/bin/env python3
"""Probe 2: both-states control — flip unknown_field_policy, verdict flips.

Independent of probe 1: re-runs the suite and checks the flip on the future-field
instance, and that a clean instance does NOT flip (the flag is not a tautology).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0100.json"


def main() -> int:
    report = S.run_all()
    failed = []
    for row in report["contracts"]:
        uid = row["contract_id"]
        bs = row["both_states"]
        clean = row["clean_stable"]
        print(
            f"{uid} declared={row['policy']} flipped={row['flipped_policy']} "
            f"future {bs['declared_accepted']}->{bs['flipped_accepted']} "
            f"both_states={bs['ok']} clean_stable={clean['ok']} "
            f"pair={row['producer'][:24]}.../{row['consumer'][:24]}..."
        )
        if not bs["ok"]:
            failed.append(f"{uid}:verdict-did-not-flip")
        if bs["declared_accepted"] is bs["flipped_accepted"]:
            failed.append(f"{uid}:same-boolean-after-flip")
        if not clean["ok"]:
            failed.append(f"{uid}:clean-instance-flipped-or-rejected")
        if not row["pair_named"] or not row["justified_ok"]:
            failed.append(f"{uid}:unjustified-or-unnamed-pair")

    if not ART.is_file():
        print("FAILED:ARC-0100-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0100-probe2 self-declared {doc.get('state')}")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("T2-both-states", {}).get("result") != "PASS":
        failed.append("artifact-T2-not-PASS")
    rev = doc.get("reviewer") or {}
    if not rev.get("independent"):
        failed.append("reviewer-not-independent")
    if "SUCCESS:ARC-0100" not in ART.read_text(encoding="utf-8"):
        failed.append("sentinel-absent")

    if failed:
        print("FAILED:ARC-0100-probe2 " + ",".join(failed))
        return 1
    print("SUCCESS:ARC-0100-probe2 both-states flip clean-stable named-pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
