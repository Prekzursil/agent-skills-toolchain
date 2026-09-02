#!/usr/bin/env python3
"""Probe 2: hard-gate both-states control, independently re-run.

Does not trust the author's prose answer. Recomputes the gate checker on:
  * the canonical table (must be silent)
  * a mutant that recommends IETF rough consensus as a gate (must fire)
  * a mutant that keeps W3C FO as a gate but clears the named field (must fire)

Second signal (different from probe1's capture-needle / rail-sha walk):
independent recount of recommended_as_gate rows versus structurally-enforced
preservation rows on the artifact table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

OUT = REPO / "command-center/research/RES-0086.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0086-probe2 {msg}")
    return 1


def main() -> int:
    live = C.both_states()
    print(f"check={live['check']}")
    print(f"fired_on_bad={live['fired_on_bad']} silent_on_good={live['silent_on_good']}")
    print(f"hard_gate_field={live['hard_gate_field']}")
    print(f"norm_as_gate_violations={live['mutant_norm_as_gate']['violations']}")
    print(f"empty_field_violations={live['mutant_empty_field']['violations']}")
    print(f"good_violations={live['good']['violations']}")
    print(f"negative_control_on_reject_state={live['negative_control']['on_that_state']}")

    if not live["discriminates"]:
        return fail("both-states-did-not-discriminate")

    if not OUT.is_file():
        return fail("artifact-missing")
    art = json.loads(OUT.read_text(encoding="utf-8"))
    rec = art.get("both_states") or {}
    if rec.get("fired_on_bad") is not True or rec.get("silent_on_good") is not True:
        return fail("artifact-both-states-drift")
    if rec.get("bad_reason") != live["negative_control"]["on_that_state"]:
        return fail(
            f"bad_reason-drift artifact={rec.get('bad_reason')!r} "
            f"live={live['negative_control']['on_that_state']!r}"
        )

    table = art.get("mechanism_table") or []
    rec_ids = [r["id"] for r in table if r.get("recommended_as_gate")]
    structural_preserve = [
        r["id"]
        for r in table
        if r.get("enforcement_classification") == "structurally-enforced"
        and r.get("preserves_minority") is True
    ]
    print(f"recount recommended={rec_ids}")
    print(f"recount structural_preserve={structural_preserve}")
    if not rec_ids:
        return fail("no-recommended-gates")
    extra = [i for i in rec_ids if i not in structural_preserve]
    if extra:
        return fail(f"recommended-not-structural {extra}")
    for rid in rec_ids:
        row = next(r for r in table if r["id"] == rid)
        if not C.field_named(row.get("checkable_artifact_field")):
            return fail(f"recommended-unnamed-field {rid}")

    hg = (art.get("hard_gate") or {}).get("artifact_field")
    if hg != C.HARD_GATE_FIELD:
        return fail(f"hard-gate-field {hg}")

    neg = (art.get("negative_controls") or [{}])[0]
    if not neg.get("fired_on_bad_state") or not neg.get("silent_on_good_state"):
        return fail("negative-control-flags")
    if "mutant_norm_as_gate" not in str(neg.get("on_the_state_it_rejects") or ""):
        return fail("negative-control-missing-reject-state")

    print("SUCCESS:RES-0086-probe2 gate both-states and named-field control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
