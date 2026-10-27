#!/usr/bin/env python3
"""Probe 1: gold fixture pair — exact difference set, no misses, no extras."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import differ as D  # noqa: E402
import fixtures as F  # noqa: E402
import jsonschema  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0094-semantic-diff-engine.json"
SCHEMA = HERE / "semantic-diff.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0094-probe1 {msg}")
    return 1


def main() -> int:
    gold = D.diff_irs(F.gold_left(), F.gold_right())
    got = D.signature(gold)
    want = sorted(F.GOLD_SIGNATURE)
    print(f"gold_got={got}")
    print(f"gold_want={want}")
    if got != want:
        extra = [x for x in got if x not in want]
        missing = [x for x in want if x not in got]
        return fail(f"signature mismatch extra={extra} missing={missing}")

    # Role permutation must be silent (set compare). Sequence decoy must fire.
    role = next(d for d in gold["dimensions"] if d["dimension"] == "role")
    print(f"role_empty={role['empty']} comparison={role['comparison']}")
    if not role["empty"]:
        return fail("role permutation reported as a difference")
    decoy = D.sequence_decoy_diff(F.gold_left(), F.gold_right(), "role")
    print(
        f"sequence_decoy_empty={decoy['empty']} "
        f"changed={len(decoy['changed'])} left_only={len(decoy['left_only'])} "
        f"right_only={len(decoy['right_only'])}"
    )
    if decoy["empty"]:
        return fail("sequence decoy did not fire on role permutation")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0094" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    ev = doc.get("evidence_a") or {}
    obs = [tuple(x) for x in ev.get("observed_signature") or []]
    if obs != got:
        return fail("artifact gold signature mismatch")
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    print("schema_valid=True")
    print("SUCCESS:WFA-0094-probe1 gold-pair exact-set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
