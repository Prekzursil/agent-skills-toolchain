"""Subject tests. TestPredicateWeak is a known-broken suite, not in baseline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import completion_predicate as pred
import detector as det
import helper_util as helper

GOOD_PRED_SENTINEL = "SUCCESS:MODULE"
GOOD_DET_SENTINEL = "DETECTOR-HIT"
PAD = {"pad": "x" * 80}


def _pred_good() -> str:
    return json.dumps({"state": "SUCCESS", **PAD}, indent=1) + "\n" + GOOD_PRED_SENTINEL + "\n"


def _pred_mention() -> str:
    return (
        json.dumps(
            {"state": "SUCCESS", "note": f"see {GOOD_PRED_SENTINEL} in docs", **PAD},
            indent=1,
        )
        + "\n"
    )


class TestPredicate(unittest.TestCase):
    def test_good_own_line(self) -> None:
        got = pred.check_artifact(_pred_good())
        self.assertTrue(got["ok"], got)

    def test_quoted_mention_is_not_use(self) -> None:
        got = pred.check_artifact(_pred_mention())
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["reason"], "sentinel-missing-or-mention-only")

    def test_missing_sentinel(self) -> None:
        text = json.dumps({"state": "SUCCESS", **PAD}, indent=1) + "\n"
        self.assertFalse(pred.check_artifact(text)["ok"])

    def test_state_key_is_literal_lowercase(self) -> None:
        self.assertEqual(pred.read_state({"state": "SUCCESS"}), "SUCCESS")
        with self.assertRaises(KeyError):
            pred.read_state({"State": "SUCCESS"})

    def test_join_under_posix_nested_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "a" / "b.json"
            nested.parent.mkdir(parents=True)
            nested.write_text("{}", encoding="utf-8")
            found = pred.join_under(root, "a", "b.json")
            self.assertTrue(found.is_file(), found)
            self.assertEqual(found.resolve(), nested.resolve())

    def test_write_lf_and_full_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.json"
            pred.write_document(path, {"state": "SUCCESS", **PAD})
            raw = path.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            json.loads(raw.decode("utf-8"))
            self.assertGreater(len(raw), 40)


class TestDetector(unittest.TestCase):
    def test_known_present_own_line_fires(self) -> None:
        text = "header\n" + GOOD_DET_SENTINEL + "\ntrailer\n"
        got = det.detect(text)
        self.assertTrue(got["fired"], got)

    def test_known_broken_mention_is_silent(self) -> None:
        text = f"see {GOOD_DET_SENTINEL} in documentation\n"
        got = det.detect(text)
        self.assertFalse(got["fired"], got)
        self.assertEqual(got["reason"], "absent-or-mention-only")

    def test_verdict_key_is_literal_lowercase(self) -> None:
        self.assertEqual(det.read_verdict({"verdict": "FIRE"}), "FIRE")
        with self.assertRaises(KeyError):
            det.read_verdict({"Verdict": "FIRE"})

    def test_join_under_posix_nested_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "k" / "hit.json"
            nested.parent.mkdir(parents=True)
            nested.write_text("{}", encoding="utf-8")
            found = det.join_under(root, "k", "hit.json")
            self.assertTrue(found.is_file(), found)
            self.assertEqual(found.resolve(), nested.resolve())

    def test_write_lf_and_full_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rep.json"
            det.write_document(path, {"verdict": "FIRE", **PAD})
            raw = path.read_bytes()
            self.assertNotIn(b"\r\n", raw)
            json.loads(raw.decode("utf-8"))
            self.assertGreater(len(raw), 40)

    def test_default_enabled_fires_on_known_present(self) -> None:
        text = GOOD_DET_SENTINEL + "\n"
        self.assertTrue(det.detect(text)["fired"])


class TestHelper(unittest.TestCase):
    def test_explicit_scale(self) -> None:
        self.assertEqual(helper.scale_count(3, scale=2), 6)
        self.assertEqual(helper.scale_count(0, scale=5), 0)
        self.assertEqual(helper.scale_count(4, scale=1), 4)


class TestPredicateWeak(unittest.TestCase):
    """Known-broken suite: no sentinel assertion. sentinel-deletion survives."""

    def test_state_key_roundtrip_via_module_constant(self) -> None:
        doc = {pred.STATE_KEY: "SUCCESS"}
        self.assertEqual(pred.read_state(doc), "SUCCESS")

    def test_join_under_still_finds_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "a" / "b.json"
            nested.parent.mkdir(parents=True)
            nested.write_text("{}", encoding="utf-8")
            found = pred.join_under(root, "a", "b.json")
            self.assertTrue(found.is_file())
