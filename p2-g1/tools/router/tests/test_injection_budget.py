#!/usr/bin/env python3
"""Tests for tools/router/injection_budget.py (IMP-0392).

Run from the repo root:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -B tools/router/tests/test_injection_budget.py
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from router import injection_budget as ib

BUDGET_SH = Path(__file__).resolve().parents[1] / "budget_count_main.sh"


def _bash(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )


class TestInjectionBudget(unittest.TestCase):
    def test_k40_all_above_threshold(self) -> None:
        caps = ib.adversarial_k40()
        self.assertEqual(len(caps), ib.K_ADVERSARIAL)
        self.assertTrue(all(float(c.score) >= ib.SCORE_THRESHOLD for c in caps))

    def test_naive_overflows_and_is_not_estimate(self) -> None:
        naive = ib.naive_inject(ib.adversarial_k40())
        self.assertGreater(naive.measured_tokens, ib.HARD_CEILING_TOKENS)
        # measured tokens come from the tokenizer, not the len//4 estimate
        self.assertNotEqual(naive.measured_tokens, len(naive.payload) // 4)
        self.assertFalse(naive.overflow_prevented)

    def test_budget_caps_k40(self) -> None:
        decision = ib.budget_inject(ib.adversarial_k40())
        self.assertLessEqual(decision.measured_tokens, ib.HARD_CEILING_TOKENS)
        self.assertTrue(decision.refused)
        self.assertTrue(decision.overflow_prevented)
        self.assertEqual(decision.counter_scope, "main-process")
        self.assertEqual(decision.running_tokens, decision.measured_tokens)

    def test_ceiling_mutation_turns_red(self) -> None:
        caps = ib.adversarial_k40()
        original = ib.HARD_CEILING_TOKENS
        naive = ib.naive_inject(caps)
        saved = ib.HARD_CEILING_TOKENS
        try:
            ib.HARD_CEILING_TOKENS = naive.measured_tokens + 64
            mutated = ib.budget_inject(caps)
        finally:
            ib.HARD_CEILING_TOKENS = saved
        self.assertEqual(ib.HARD_CEILING_TOKENS, original)
        # with the raised ceiling the original cap assertion goes red
        self.assertGreater(mutated.measured_tokens, original)

    def test_main_shell_counter_not_subshell(self) -> None:
        lost = _bash(
            "counter=0; _=$(counter=$((counter + 10))); printf '%s\\n' \"$counter\""
        )
        self.assertEqual(lost.returncode, 0, lost.stderr)
        self.assertEqual(lost.stdout.strip(), "0")

        sourced = _bash(
            f"source {BUDGET_SH.as_posix()}; BUDGET_COUNTER=0; "
            "budget_add 7; budget_add 5; printf '%s\\n' \"$BUDGET_COUNTER\""
        )
        self.assertEqual(sourced.returncode, 0, sourced.stderr)
        self.assertEqual(sourced.stdout.strip(), "12")

    def test_packer_hot_path_has_no_subprocess(self) -> None:
        self.assertEqual(ib.pack_hot_path_uses_subprocess(), [])


def main() -> int:
    prog = unittest.main(module=sys.modules[__name__], exit=False, verbosity=2)
    result = prog.result
    if result.wasSuccessful():
        print(f"SUCCESS:test_injection_budget {result.testsRun}/{result.testsRun}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
