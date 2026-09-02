#!/usr/bin/env python3
"""Unit tests for TST-0308: Goodhart detector, celebrate-refusal, metric retirement."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.goodhart import (  # noqa: E402
    MIN_ITERATIONS,
    correlation_series,
    detect_goodhart,
    evaluate_metric_gain,
)
from bench.ledger import LedgerImmutableError, ResultsLedger  # noqa: E402
from bench.simulate import (  # noqa: E402
    FAITHFUL_METRIC,
    GAMEABLE_METRIC,
    OUTCOME_ID,
    simulate_campaign,
)


def _series(kind: str, metric: str, n_iters: int = 6):
    rows = simulate_campaign(kind, n_cases=32, n_iters=n_iters, seed=308)
    return correlation_series(rows, metric_id=metric, outcome_id=OUTCOME_ID)


class DetectorTests(unittest.TestCase):
    def test_gamed_proxy_raises_p1(self) -> None:
        f = detect_goodhart(_series("goodhart", GAMEABLE_METRIC))
        self.assertTrue(f.fired)
        self.assertEqual(f.severity, "P1")
        self.assertGreater(f.metric_gain, 0)
        self.assertLess(f.outcome_delta, 0)
        self.assertLess(f.corr_delta, 0)

    def test_faithful_proxy_is_silent(self) -> None:
        f = detect_goodhart(_series("faithful", FAITHFUL_METRIC))
        self.assertFalse(f.fired)

    def test_snapshot_is_not_evidence(self) -> None:
        s = _series("goodhart", GAMEABLE_METRIC)
        f = detect_goodhart(s[: MIN_ITERATIONS - 1])
        self.assertFalse(f.fired)
        self.assertEqual(f.rule, "min-iterations")

    def test_finding_as_dict_roundtrips(self) -> None:
        d = detect_goodhart(_series("goodhart", GAMEABLE_METRIC)).as_dict()
        for key in ("fired", "severity", "metric_gain", "outcome_delta", "corr_delta"):
            self.assertIn(key, d)

    def test_series_rows_carry_pearson(self) -> None:
        s = _series("goodhart", GAMEABLE_METRIC)
        self.assertEqual(len(s), 6)
        self.assertTrue(all("pearson_r" in r and "iteration" in r for r in s))
        self.assertGreater(s[0]["pearson_r"], s[-1]["pearson_r"])


class CelebrateTests(unittest.TestCase):
    def test_live_refuses_gamed_gain_but_vacuous_twin_celebrates(self) -> None:
        s = _series("goodhart", GAMEABLE_METRIC)
        self.assertFalse(evaluate_metric_gain(s)["celebrate"])
        self.assertTrue(evaluate_metric_gain(s, ignore_decay=True)["celebrate"])

    def test_faithful_gain_is_celebrable(self) -> None:
        self.assertTrue(evaluate_metric_gain(_series("faithful", FAITHFUL_METRIC))["celebrate"])


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="tst0308-t-"))
        self.ledger = ResultsLedger(self.tmp / "runs.jsonl")
        self.ledger.append_runs(simulate_campaign("goodhart", n_cases=8, n_iters=6, seed=1))

    def test_demotion_appends_and_preserves_history(self) -> None:
        before = self.ledger.snapshot_bytes()
        hist = self.ledger.history(GAMEABLE_METRIC)
        ev = self.ledger.demote_metric(GAMEABLE_METRIC, reason="goodhart-decay", iteration=5)
        after = self.ledger.snapshot_bytes()
        self.assertTrue(after.startswith(before))
        self.assertEqual(ev["status"], "demoted")
        self.assertEqual(self.ledger.history(GAMEABLE_METRIC), hist)
        self.assertNotIn(GAMEABLE_METRIC, self.ledger.active_metric_ids())
        self.assertIn(FAITHFUL_METRIC, self.ledger.active_metric_ids())
        self.assertEqual(self.ledger.scoring_runs(GAMEABLE_METRIC), [])
        self.assertTrue(self.ledger.verify_chain())

    def test_rewrite_is_refused_without_touching_disk(self) -> None:
        before = self.ledger.snapshot_bytes()
        with self.assertRaises(LedgerImmutableError):
            self.ledger.rewrite_run(1, metric_value=0.0)
        self.assertEqual(self.ledger.snapshot_bytes(), before)

    def test_tampered_row_breaks_chain(self) -> None:
        text = self.ledger.path.read_text(encoding="utf-8").splitlines()
        text[0] = text[0].replace('"iteration": 0', '"iteration": 9', 1)
        self.ledger.path.write_text("\n".join(text) + "\n", encoding="utf-8")
        self.assertFalse(self.ledger.verify_chain())


if __name__ == "__main__":
    result = unittest.main(verbosity=1, exit=False).result
    if result.wasSuccessful():
        print(f"SUCCESS:TST-0308-tests ran={result.testsRun}")
        raise SystemExit(0)
    print(f"FAILED:TST-0308-tests failures={len(result.failures)} errors={len(result.errors)}")
    raise SystemExit(1)
