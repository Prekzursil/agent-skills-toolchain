#!/usr/bin/env python3
"""Unit tests for the acceptance_review PURE CORE (no repo / no CLI required).

Run:  python test_acceptance_review.py    (stdlib unittest; exits non-zero on fail)
Covers: reward-hack scan, reviewer routing / graceful degradation, verdict parse,
prompt assembly, journey/artifact discovery on a synthetic tree.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import acceptance_review as ar


class TestScanRewardHack(unittest.TestCase):
    def test_flags_added_pragma_and_skip_and_xfail(self):
        diff = (
            "+++ b/test_x.py\n"
            "+    return 1  # pragma: no cover\n"
            "+    @pytest.mark.skip(reason='flaky')\n"
            "+    it.skip('later', () => {})\n"
            "+@pytest.mark.xfail(strict=True)\n"
        )
        kinds = {f["kind"] for f in ar.scan_reward_hack(diff)}
        self.assertIn("pragma_no_cover", kinds)
        self.assertIn("skip_marker", kinds)
        self.assertIn("xfail", kinds)

    def test_ignores_removed_lines_and_hunk_headers(self):
        diff = (
            "-    x  # pragma: no cover\n+++ b/f.py\n context line pragma: no cover\n"
        )
        self.assertEqual(ar.scan_reward_hack(diff), [])

    def test_flags_coverage_and_marker_and_ci_edits(self):
        diff = (
            "+  omit = src/main/*\n"
            "+  addopts = -m 'not e2e'\n"
            "+  continue-on-error: true\n"
        )
        kinds = {f["kind"] for f in ar.scan_reward_hack(diff)}
        self.assertIn("coverage_omit", kinds)
        self.assertIn("marker_deselect", kinds)
        self.assertIn("ci_trigger_edit", kinds)

    def test_clean_diff_no_findings(self):
        self.assertEqual(ar.scan_reward_hack("+    return compute(x)\n"), [])


class TestChooseReviewer(unittest.TestCase):
    def test_auto_prefers_codex_then_gemini(self):
        self.assertEqual(
            ar.choose_reviewer("auto", {"codex": True, "gemini": True})[0], "codex"
        )
        self.assertEqual(
            ar.choose_reviewer("auto", {"codex": False, "gemini": True})[0], "gemini"
        )

    def test_auto_degrades_to_claude_when_no_cli(self):
        r, reason = ar.choose_reviewer("auto", {"codex": False, "gemini": False})
        self.assertEqual(r, "claude")
        self.assertIn("fresh", reason.lower())

    def test_explicit_absent_falls_through_to_other_crossmodel(self):
        r, _ = ar.choose_reviewer("codex", {"codex": False, "gemini": True})
        self.assertEqual(r, "gemini")

    def test_explicit_absent_and_none_falls_to_claude(self):
        r, _ = ar.choose_reviewer("gemini", {"codex": False, "gemini": False})
        self.assertEqual(r, "claude")

    def test_explicit_claude_always_claude(self):
        self.assertEqual(
            ar.choose_reviewer("claude", {"codex": True, "gemini": True})[0], "claude"
        )


class TestParseVerdict(unittest.TestCase):
    def test_ship_and_block(self):
        self.assertEqual(ar.parse_verdict("...\nVERDICT: SHIP\n"), "SHIP")
        self.assertEqual(ar.parse_verdict("VERDICT = **BLOCK**"), "BLOCK")

    def test_missing_verdict_is_none(self):
        self.assertIsNone(ar.parse_verdict("looks fine to me, all tests pass"))
        self.assertIsNone(ar.parse_verdict(""))


class TestBuildPrompt(unittest.TestCase):
    def _evidence(self, journeys, artifacts, hacks):
        return {
            "diff": {
                "base": "abc123",
                "stat": " 1 file changed",
                "changed_files": ["src/app.py"],
                "unified_diff": "+code",
                "diff_truncated": False,
            },
            "journeys": journeys,
            "artifacts": artifacts,
            "reward_hack": hacks,
        }

    def test_contains_adversarial_directives_and_verdict_block(self):
        p = ar.build_prompt(self._evidence(["e2e/golden.spec.ts"], [], []))
        self.assertIn("green-but-broken", p)
        self.assertIn("DEMAND THE ARTIFACT", p)
        self.assertIn("VERDICT: SHIP or BLOCK", p)
        self.assertIn("golden.spec.ts", p)

    def test_flags_no_journeys_and_no_artifacts(self):
        p = ar.build_prompt(self._evidence([], [], []))
        self.assertIn("NONE DECLARED", p)
        self.assertIn("NONE FOUND", p)

    def test_lists_artifacts_and_hacks(self):
        arts = [{"path": "out/x.mp4", "bytes": 1024, "mtime": 111, "fresh": True}]
        hacks = [{"kind": "xfail", "line": "@pytest.mark.xfail"}]
        p = ar.build_prompt(self._evidence(["j"], arts, hacks))
        self.assertIn("out/x.mp4", p)
        self.assertIn("xfail", p)


class TestBuildReviewerCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.pf = self.repo / "review-prompt.md"
        self.pf.write_text("PROMPT BODY", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_codex_is_read_only_and_passes_prompt(self):
        argv = ar.build_reviewer_command("codex", self.pf, self.repo, None)
        self.assertEqual(argv[:2], ["codex", "exec"])
        self.assertIn("read-only", argv)
        self.assertEqual(argv[-1], "PROMPT BODY")

    def test_gemini_plan_mode_and_model(self):
        argv = ar.build_reviewer_command("gemini", self.pf, self.repo, "gemini-2.5-pro")
        self.assertIn("plan", argv)
        self.assertIn("-m", argv)
        self.assertIn("gemini-2.5-pro", argv)
        self.assertEqual(argv[-1], "PROMPT BODY")

    def test_claude_returns_none(self):
        self.assertIsNone(ar.build_reviewer_command("claude", self.pf, self.repo, None))


class TestDiscovery(unittest.TestCase):
    def test_finds_journeys_and_artifacts_skips_node_modules(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "e2e").mkdir()
            (root / "e2e" / "golden.spec.ts").write_text("x", encoding="utf-8")
            (root / "node_modules" / "e2e").mkdir(parents=True)
            (root / "node_modules" / "e2e" / "junk.spec.ts").write_text(
                "x", encoding="utf-8"
            )
            (root / "out").mkdir()
            (root / "out" / "short.mp4").write_text("data", encoding="utf-8")
            journeys = ar.find_journey_specs(root)
            arts = ar.find_artifacts(root)
            self.assertIn("e2e/golden.spec.ts", journeys)
            self.assertNotIn("node_modules/e2e/junk.spec.ts", journeys)
            self.assertTrue(any(a["path"] == "out/short.mp4" for a in arts))


if __name__ == "__main__":
    unittest.main(verbosity=2)
