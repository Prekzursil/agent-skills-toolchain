"""Pure unit tests for auth_deeplink URL construction."""

from __future__ import annotations

import unittest

from crcp.auth_deeplink import build_codex_deeplink, run_deeplink_cli


class BuildCodexDeeplinkTests(unittest.TestCase):
    def test_empty_path(self) -> None:
        self.assertEqual(build_codex_deeplink(), "codex://")

    def test_simple_path(self) -> None:
        self.assertEqual(build_codex_deeplink(path="open"), "codex://open")

    def test_leading_slashes_are_normalized(self) -> None:
        self.assertEqual(build_codex_deeplink(path="/open/chat"), "codex://open/chat")

    def test_conversation_query(self) -> None:
        self.assertEqual(
            build_codex_deeplink(
                path="chat",
                query={"conversation_id": "abc-123"},
            ),
            "codex://chat?conversation_id=abc-123",
        )

    def test_query_values_are_quoted(self) -> None:
        self.assertEqual(
            build_codex_deeplink(
                path="chat",
                query={"title": "road map & review", "next": "/a?b=c"},
            ),
            "codex://chat?title=road+map+%26+review&next=%2Fa%3Fb%3Dc",
        )

    def test_unicode_and_path_delimiters_are_safe(self) -> None:
        self.assertEqual(
            build_codex_deeplink(path="open/team notes/✓"),
            "codex://open/team%20notes/%E2%9C%93",
        )

    def test_sequence_query_values_use_doseq(self) -> None:
        self.assertEqual(
            build_codex_deeplink(path="open", query={"id": ["one", "two"]}),
            "codex://open?id=one&id=two",
        )

    def test_empty_query_is_omitted(self) -> None:
        self.assertEqual(build_codex_deeplink(path="open", query={}), "codex://open")

    def test_build_cli(self) -> None:
        self.assertEqual(
            run_deeplink_cli("build", path="chat", query={"conversation_id": "42"}),
            {
                "ok": True,
                "action": "build",
                "url": "codex://chat?conversation_id=42",
                "method": "build",
            },
        )


if __name__ == "__main__":
    unittest.main()
