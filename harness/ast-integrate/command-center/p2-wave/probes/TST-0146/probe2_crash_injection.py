#!/usr/bin/env python3
"""Probe 2: 100 SIGKILLs at randomized offsets; independent of the AST scan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crash import N_TRIALS, run_both  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0146-probe2 {msg}")
    return 1


def main() -> int:
    result = run_both()
    atomic = result["atomic"]
    control = result["control"]
    if atomic["n"] != N_TRIALS:
        return fail(f"atomic campaign n={atomic['n']} want {N_TRIALS}")
    if not result["atomic_zero_partials"]:
        return fail(
            f"atomic readable partials={atomic['partial_count']} "
            f"classes={atomic['class_counts']} ready={atomic['ready_count']}"
        )
    if not result["control_found_partials"]:
        return fail(
            f"detector control saw no partials classes={control['class_counts']}"
        )
    slim = {
        "pass": True,
        "probe": "probe2-crash-injection",
        "unit_id": "TST-0146",
        "atomic_n": atomic["n"],
        "atomic_partial_count": atomic["partial_count"],
        "atomic_class_counts": atomic["class_counts"],
        "atomic_ready": atomic["ready_count"],
        "control_n": control["n"],
        "control_partial_count": control["partial_count"],
        "control_class_counts": control["class_counts"],
        "control_ready": control["ready_count"],
        "seed": atomic["seed"],
        "payload_len": atomic["payload_len"],
        "offsets_head": atomic["offsets"][:8],
    }
    print(json.dumps(slim, indent=1, sort_keys=True))
    print(
        f"atomic_partials={atomic['partial_count']}/{atomic['n']} "
        f"control_partials={control['partial_count']}/{control['n']} "
        f"classes_atomic={atomic['class_counts']}"
    )
    print("SUCCESS:TST-0146-probe2 crash-injection 100 SIGKILLs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
