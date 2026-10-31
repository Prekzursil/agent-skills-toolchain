#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKET = HERE.parent
if str(MARKET) not in sys.path:
    sys.path.insert(0, str(MARKET))

import jsonschema

from trust_levels import (  # noqa: E402
    DEFAULT_FIXTURE,
    FORMULA_VERSION,
    LEVEL_HIGH,
    LEVEL_MEDIUM,
    LEVEL_UNRATED,
    compute_publisher_trust,
)

FIXTURE = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
SCHEMA = json.loads(
    (MARKET / "schema" / "trust-levels.schema.json").read_text(encoding="utf-8")
)


def _rec(fid: str) -> dict:
    for item in FIXTURE["publishers"]:
        if item["id"] == fid:
            return dict(item["record"])
    raise KeyError(fid)


class TrustLevelFixtures(unittest.TestCase):
    def test_formula_version_pinned(self) -> None:
        self.assertEqual(FORMULA_VERSION, "tl-v1-millipoints-10000")


class _Oracle:
    @staticmethod
    def load():
        probe = MARKET.parents[1] / "command-center" / "p2-wave" / "probes" / "IMP-0076"
        sys.path.insert(0, str(probe))
        from hand_derive import recompute  # noqa: WPS433

        return recompute


class TrustLevelFixturesReal(unittest.TestCase):
    def test_fixture_three_way_matches_hand_derived(self) -> None:
        recompute = _Oracle.load()
        for item in FIXTURE["publishers"]:
            lib = compute_publisher_trust(item["record"])
            oracle = recompute(item["record"])
            hand = item["hand_derived"]
            self.assertEqual(lib.level, oracle["level"])
            self.assertEqual(lib.level, hand["level"])
            self.assertEqual(lib.score_millipoints, oracle["score_millipoints"])
            self.assertEqual(lib.score_millipoints, hand["score_millipoints"])


class NegativeControlUnrated(unittest.TestCase):
    def test_empty_history_is_unrated_never_default_trusted(self) -> None:
        t = compute_publisher_trust(_rec("unrated-empty"))
        self.assertEqual(t.level, LEVEL_UNRATED)
        self.assertNotEqual(t.level, "DEFAULT-TRUSTED")

    def test_empty_plus_popularity_and_self_asserted_trust_stays_unrated(self) -> None:
        rec = _rec("unrated-empty")
        rec["downloads"] = 10**9
        rec["stars"] = 50000
        rec["default_trusted"] = True
        rec["trust_level"] = "DEFAULT-TRUSTED"
        t = compute_publisher_trust(rec)
        self.assertEqual(t.level, LEVEL_UNRATED)

    def test_output_schema_accepts_library_dict(self) -> None:
        t = compute_publisher_trust(_rec("alice"))
        jsonschema.validate(t.as_dict(), SCHEMA)


class GamingControl(unittest.TestCase):
    def test_popularity_inputs_move_nothing(self) -> None:
        clean = compute_publisher_trust(_rec("alice"))
        rec = _rec("alice")
        rec["downloads"] = 10**12
        rec["stars"] = 999999
        rec["ratings"] = 5
        dirty = compute_publisher_trust(rec)
        self.assertEqual(clean.level, dirty.level)
        self.assertEqual(clean.score_millipoints, dirty.score_millipoints)

    def test_scoring_sha_excludes_popularity_keys(self) -> None:
        clean = compute_publisher_trust(_rec("alice"))
        rec = _rec("alice")
        rec["downloads"] = 10**12
        rec["stars"] = 1
        dirty = compute_publisher_trust(rec)
        self.assertEqual(clean.scoring_input_sha256, dirty.scoring_input_sha256)
        self.assertTrue(dirty.ignored_popularity_fields)


class DirectionalInputs(unittest.TestCase):
    def test_signed_releases_up_moves_low_to_medium(self) -> None:
        rec = _rec("near-low")
        low = compute_publisher_trust(rec)
        self.assertEqual(low.level, "LOW")
        rec["releases_signed"] = 20
        rec["releases_unsigned"] = 0
        rec["published_version_count"] = 20
        rec["provenance_complete_versions"] = 20
        rec["conformance_passes"] = 20
        rec["conformance_runs"] = 20
        rec["advisory_median_response_hours"] = 0
        moved = compute_publisher_trust(rec)
        self.assertIn(moved.level, {LEVEL_MEDIUM, LEVEL_HIGH})

    def test_skip_conformance_then_add_runs_moves_medium_to_high(self) -> None:
        rec = _rec("skip-conformance")
        mid = compute_publisher_trust(rec)
        self.assertEqual(mid.level, LEVEL_MEDIUM)
        rec["conformance_passes"] = 5
        rec["conformance_runs"] = 5
        high = compute_publisher_trust(rec)
        self.assertEqual(high.level, LEVEL_HIGH)

    def test_zero_conformance_runs_scores_zero_and_stays_in_average(self) -> None:
        rec = _rec("skip-conformance")
        t = compute_publisher_trust(rec)
        conf = [c for c in t.components if c.name == "conformance_pass_rate"][0]
        self.assertEqual(conf.millipoints, 0)
        self.assertTrue(conf.included)


class FixturePath(unittest.TestCase):
    def test_default_fixture_is_repo_file(self) -> None:
        self.assertTrue(DEFAULT_FIXTURE.is_file())


if __name__ == "__main__":
    unittest.main()
