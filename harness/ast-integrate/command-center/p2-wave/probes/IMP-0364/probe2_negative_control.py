#!/usr/bin/env python3
"""Named probe 2: deterministic fixture must be 100 percent stable.

Negative control: the harness does not inject noise. Both-states: flipping one
recorded decision turns the 100 percent check red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "council"))

import stability as S  # noqa: E402

UNIT = "IMP-0364"
NOISE_DECISION = "HARNESS-NOISE-INJECTED"


def main() -> int:
    pack = S.load_preset_pack()
    spec = next(
        (p for p in pack["presets"] if p.get("id") == S.DETERMINISTIC_PRESET_ID),
        None,
    )
    if spec is None:
        print(f"FAILED:{UNIT}-probe2 missing {S.DETERMINISTIC_PRESET_ID}")
        return 1

    row = S.rerun(spec, n=S.MIN_N)
    silent_good = S.fully_stable(row)
    decisions = [r["decision"] for r in row["runs"]]
    if not silent_good:
        print(f"FAILED:{UNIT}-probe2 deterministic fixture is not 100 percent stable")
        print(json.dumps({"decisions": decisions, "rates": {
            "stability_rate": row["stability_rate"],
            "decision_change_rate": row["decision_change_rate"],
        }}, indent=2))
        return 1
    if len(set(str(d) for d in decisions)) != 1:
        print(f"FAILED:{UNIT}-probe2 decisions not identical: {decisions}")
        return 1
    if float(row["decision_change_rate"]) != 0.0:
        print(f"FAILED:{UNIT}-probe2 change_rate={row['decision_change_rate']} want=0")
        return 1

    mutant = S.mutate_one_decision(row, 3, NOISE_DECISION)
    fired_bad = not S.fully_stable(mutant)
    if not fired_bad:
        print(f"FAILED:{UNIT}-probe2 noise mutation stayed green")
        return 1
    if float(mutant["stability_rate"]) == 1.0:
        print(f"FAILED:{UNIT}-probe2 mutant stability still 1.0")
        return 1
    if NOISE_DECISION not in {str(r["decision"]) for r in mutant["runs"]}:
        print(f"FAILED:{UNIT}-probe2 mutant did not retain injected decision")
        return 1

    # The good-state row must remain untouched by the mutation helper.
    if not S.fully_stable(row):
        print(f"FAILED:{UNIT}-probe2 mutation leaked into the good-state row")
        return 1

    out = {
        "probe": "probe2-negative-control",
        "unit_id": UNIT,
        "preset_id": S.DETERMINISTIC_PRESET_ID,
        "n": row["n"],
        "stability_rate": row["stability_rate"],
        "decision_change_rate": row["decision_change_rate"],
        "silent_on_good_state": silent_good,
        "fired_on_bad_state": fired_bad,
        "mutant_stability_rate": mutant["stability_rate"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"deterministic stability={row['stability_rate']} "
        f"mutant_stability={mutant['stability_rate']} "
        f"fired_bad={fired_bad} silent_good={silent_good}"
    )
    print("SUCCESS:IMP-0364-probe2 deterministic fixture 100 percent stable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
