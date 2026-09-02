"""Unit tests for tools/council/order.py (IMP-0337): strategies, audit, experiment, control."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.council.order import (  # noqa: E402
    EXPERIMENT_N,
    HAND_EXPECTED,
    PRODUCTION_STRATEGY_NAMES,
    Seat,
    audit_against_hand,
    audit_claimed,
    decide_anchored,
    first_speaker_experiment,
    hand_roster,
    list_strategies,
    negative_control_biased_order,
    production_trace_audit,
    speaking_order,
)


class StrategyTests(unittest.TestCase):
    def test_strategy_set(self) -> None:
        self.assertEqual(list_strategies(), PRODUCTION_STRATEGY_NAMES)
        self.assertEqual(len(PRODUCTION_STRATEGY_NAMES), 5)

    def test_hand_cases_match(self) -> None:
        audit = audit_against_hand()
        self.assertTrue(audit["all_match"], audit["rows"])
        self.assertEqual(audit["n"], len(HAND_EXPECTED))

    def test_round_robin_rotates(self) -> None:
        roster = hand_roster()
        self.assertEqual(speaking_order("round-robin", roster, round_index=1)[0], "bob")
        self.assertEqual(speaking_order("round-robin", roster, round_index=4), speaking_order("round-robin", roster))

    def test_chair_recognition_respects_list(self) -> None:
        roster = hand_roster()
        order = speaking_order("chair-recognition", roster, recognition=["drew", "cara"])
        self.assertEqual(order, ["alice", "drew", "cara", "bob"])

    def test_audit_claimed_detects_mismatch(self) -> None:
        roster = (Seat("a", 1, 1), Seat("b", 2, 2))
        self.assertFalse(audit_claimed("priority", roster, ["a", "b"])["match"])
        self.assertTrue(audit_claimed("priority", roster, ["b", "a"])["match"])

    def test_production_traces(self) -> None:
        traces = production_trace_audit(rounds=2)
        self.assertEqual(traces["n_traces"], 10)
        self.assertTrue(traces["all_match"])


class ExperimentTests(unittest.TestCase):
    def test_decide_anchored(self) -> None:
        prefs = {"W": "adopt", "X": "adopt", "Y": "adopt", "Z": "reject"}
        self.assertEqual(decide_anchored(["W", "X", "Y", "Z"], prefs, 3)["winner"], "adopt")
        self.assertEqual(decide_anchored(["Z", "W", "X", "Y"], prefs, 3)["winner"], "reject")
        self.assertEqual(decide_anchored(["Z", "W", "X", "Y"], prefs, 0)["winner"], "adopt")

    def test_experiment_shape(self) -> None:
        exp = first_speaker_experiment()
        self.assertEqual(exp["n_matched_pairs"], EXPERIMENT_N)
        self.assertTrue(exp["all_prefs_matched"])
        self.assertTrue(exp["all_first_speakers_differ"])
        self.assertEqual(exp["counts"]["seat_runs"], 2 * EXPERIMENT_N * 4)
        self.assertGreaterEqual(exp["flip_count"], 1)

    def test_experiment_is_deterministic(self) -> None:
        self.assertEqual(first_speaker_experiment()["pairs"], first_speaker_experiment()["pairs"])

    def test_negative_control(self) -> None:
        neg = negative_control_biased_order()
        self.assertTrue(neg["fired_on_biased_order"])
        self.assertTrue(neg["silent_on_order_blind"])
        self.assertEqual(neg["winner_round_robin"], "adopt")
        self.assertEqual(neg["winner_biased"], "reject")
        self.assertEqual(neg["winner_round_robin_order_blind"], "adopt")


if __name__ == "__main__":
    unittest.main()
