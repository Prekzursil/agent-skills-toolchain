#!/usr/bin/env python3
"""Probe 1: syntactic reducer verdicts on >=6 adversarial envelopes + control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
from reducer import reduce_file  # noqa: E402

def fail(msg: str) -> int:
    print(f"FAILED:ADV-0001-probe1 {msg}")
    return 1


def main() -> int:
    cases = F.dump()
    if len(cases) < 7:
        return fail(f"need 6 attacks + control, got {len(cases)}")
    attacks = [c for c in cases if not c["is_control"]]
    controls = [c for c in cases if c["is_control"]]
    if len(attacks) < 6 or len(controls) != 1:
        return fail(f"attacks={len(attacks)} controls={len(controls)}")

    matrix = []
    for case in cases:
        path = HERE.parents[3] / case["path"]
        verdict = reduce_file(path)
        failing = verdict.get("failing") or []
        line = (
            f"fixture={case['id']} class={case['class']} "
            f"reducer={verdict['verdict']} failing={failing} "
            f"c12={verdict.get('c12_mechanism')}"
        )
        print(line)
        matrix.append(
            {
                "id": case["id"],
                "class": case["class"],
                "is_control": case["is_control"],
                "verdict": verdict["verdict"],
                "failing": failing,
            }
        )
        if verdict["verdict"] != "PASS":
            print(json.dumps(verdict["conditions"], indent=1)[:2000])
            return fail(f"reducer did not PASS {case['id']}")

    print(f"attack_reducer_pass={len(attacks)}/{len(attacks)}")
    print("control_reducer_pass=True")
    print("SUCCESS:ADV-0001-probe1 reducer PASS on six attacks and the readable control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
