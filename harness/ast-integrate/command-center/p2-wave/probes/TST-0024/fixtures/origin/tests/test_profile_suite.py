"""Fixture suite mixed of profile-independent and ~/.claude-dependent tests.

This is the suite the clean-room lane clones and runs. A test that reads
$HOME/.claude/settings.json will pass only when that file is planted in the
profile the runner actually uses.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path


def _home() -> Path:
    raw = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
    return Path(raw)


def _claude_settings() -> Path:
    return _home() / ".claude" / "settings.json"


class ProfileSuite(unittest.TestCase):
    def test_independent_pass(self) -> None:
        self.assertEqual(1 + 1, 2)

    def test_requires_claude_settings(self) -> None:
        path = _claude_settings()
        self.assertTrue(path.is_file(), "missing ~/.claude/settings.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data.get("tst0024_marker"), "ambient-profile")

    def test_fails_if_profile_polluted(self) -> None:
        """Passes only with an empty profile; fails when ~/.claude exists."""
        self.assertFalse(
            _claude_settings().is_file(),
            "HOME still contains ~/.claude/settings.json",
        )

    def test_independent_fail(self) -> None:
        self.fail("fixture: fails in every profile")
