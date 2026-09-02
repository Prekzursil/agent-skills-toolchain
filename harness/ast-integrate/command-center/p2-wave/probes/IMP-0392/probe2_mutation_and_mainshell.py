#!/usr/bin/env python3
"""Probe 2: ceiling-constant mutation goes red; counter lives in the main shell.

Independent of probe 1's scenario objects. Confirms:
  1. Raising HARD_CEILING_TOKENS makes the original cap assertion fail.
  2. A counter mutated inside command substitution is lost; the same
     increment in the main shell persists.
  3. The Python packer does not hide the counter in a subprocess.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from router.injection_budget import (  # noqa: E402
    adversarial_k40,
    pack_hot_path_uses_subprocess,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0392-probe2 {msg}")
    return 1


def bash(script: str) -> str:
    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"bash rc={proc.returncode} err={proc.stderr!r}")
    return proc.stdout.strip()


def main() -> int:
    import router.injection_budget as ib

    caps = adversarial_k40()
    original = ib.HARD_CEILING_TOKENS
    baseline = ib.budget_inject(caps)
    if baseline.measured_tokens > original:
        return fail("baseline already over the shipped ceiling")

    naive = ib.naive_inject(caps)
    saved = ib.HARD_CEILING_TOKENS
    try:
        ib.HARD_CEILING_TOKENS = naive.measured_tokens + 64
        mutated = ib.budget_inject(caps)
    finally:
        ib.HARD_CEILING_TOKENS = saved

    if ib.HARD_CEILING_TOKENS != original:
        return fail("ceiling constant leaked after mutation")
    if mutated.measured_tokens <= original:
        return fail(
            "raising HARD_CEILING_TOKENS did not inject past the original cap "
            f"(mutated={mutated.measured_tokens} original={original})"
        )
    cap_assertion_after_raise = mutated.measured_tokens <= original
    if cap_assertion_after_raise:
        return fail("cap assertion stayed green after raising the ceiling")

    lost = bash("counter=0; _=$(counter=$((counter + 10))); printf '%s\\n' \"$counter\"")
    if lost != "0":
        return fail(f"subshell counter was not lost: {lost!r}")
    held = bash("counter=0; counter=$((counter + 10)); printf '%s\\n' \"$counter\"")
    if held != "10":
        return fail(f"main-shell counter did not persist: {held!r}")

    sh = (TOOLS / "router" / "budget_count_main.sh").as_posix()
    sourced = bash(
        f"source {sh}; BUDGET_COUNTER=0; budget_add 7; budget_add 5; "
        "printf '%s\\n' \"$BUDGET_COUNTER\""
    )
    if sourced != "12":
        return fail(f"sourced budget_add did not mutate caller: {sourced!r}")

    hits = pack_hot_path_uses_subprocess()
    if hits:
        return fail(f"packer hot path uses subprocess: {hits}")

    report = {
        "probe": "probe2-mutation-and-mainshell",
        "unit_id": "IMP-0392",
        "reviewer_id": "IMP-0392-probe2-mainshell-and-ceiling-mutation",
        "original_ceiling": original,
        "baseline_measured": baseline.measured_tokens,
        "naive_measured": naive.measured_tokens,
        "mutated_measured": mutated.measured_tokens,
        "cap_assertion_red_after_raise": True,
        "subshell_counter_lost": True,
        "main_shell_counter_held": True,
        "sourced_budget_add": 12,
        "packer_subprocess_hits": hits,
        "counter_scope": baseline.counter_scope,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:IMP-0392-probe2 ceiling mutation turns cap red; "
        "counter is main-shell / main-process, not a subshell"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
