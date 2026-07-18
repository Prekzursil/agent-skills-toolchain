#!/usr/bin/env python3
"""Regression suite for the shared use-vs-mention discriminator.

Every FALSE-POSITIVE case below is a REAL recorded fire from
`~/.claude/harness-sota-2026-07-18/INPUT-known-harness-defects.md` (D1/D1a/D1b).
Every TRUE-POSITIVE case is a known-present control: per D2, a detector that
reports absence is untrustworthy until it is shown to find a known-present item.
If the TP block ever goes silent the discriminator has over-corrected and is
worse than the bug it replaced.

Stdlib + pytest only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))

from use_vs_mention import (  # noqa: E402
    Context,
    find_real,
    is_real_occurrence,
)


def _span(text: str, needle: str) -> tuple[int, int]:
    i = text.index(needle)
    return (i, i + len(needle))


def _judge(text: str, needle: str, ctx: Context, kind: str) -> bool:
    return is_real_occurrence(text, _span(text, needle), ctx, kind=kind)


# --------------------------------------------------------------------------
# FALSE POSITIVES — the 9 recorded fires. Every one MUST be judged a MENTION.
# --------------------------------------------------------------------------


class TestRecordedFalsePositives:
    """D1b roster: destructive-command guard x2, stub-ledger x6, marker scanner x1."""

    def test_fire1_setcontent_writing_markdown_that_quotes_remove_item(self):
        """Fire 1/2: the tool_use VERB was Set-Content; the body merely QUOTED it."""
        body = (
            "# Windows footguns\n\n"
            "A here-string PAYLOAD is scanned as if it were a command: "
            "`Set-Content -Value @'...'@` was blocked because the markdown BODY "
            "quoted Remove-Item -Force.\n"
        )
        ctx = Context(
            tool_name="Write", file_path="docs/MASTER-QUEUE.md", source="tool_input"
        )
        assert not _judge(body, "Remove-Item -Force", ctx, "command")

    def test_fire2_second_setcontent_block_same_shape(self):
        """Fire 2/2: same defect, second occurrence, different document."""
        body = "Never run `rm -rf /` from a hook. Use the Write tool instead.\n"
        ctx = Context(
            tool_name="Write", file_path="rules/common/windows-shell.md",
            source="tool_input",
        )
        assert not _judge(body, "rm -rf /", ctx, "command")

    def test_fire3_word_stub_in_a_markdown_paragraph(self):
        """stub-ledger fire 1/6: prose describing a fixture, not pending work."""
        body = "The fixture is a stub that returns a canned response.\n"
        ctx = Context(tool_name="Write", file_path="docs/design.md",
                      source="tool_input")
        assert not _judge(body, "stub", ctx, "marker")

    def test_fire4_reworded_to_test_double_still_flagged(self):
        """stub-ledger fire 2/6: rewording chased the matcher instead of fixing it."""
        body = "The fixture is a test double, i.e. a placeholder object.\n"
        ctx = Context(tool_name="Write", file_path="docs/design.md",
                      source="tool_input")
        assert not _judge(body, "placeholder", ctx, "marker")

    def test_fire5_negation_nothing_needs_to_be_added(self):
        """stub-ledger fire 3/6: F9-live-control-integration.md:400.

        The matcher hit `to be added` inside a sentence asserting its NEGATION.
        """
        body = (
            "There is no extension point. Fortunately section 3.2 means nothing "
            "needs to be added.\n"
        )
        ctx = Context(
            tool_name="Write",
            file_path="docs/F9-live-control-integration.md",
            source="tool_input",
        )
        assert not _judge(body, "to be added", ctx, "marker")

    def test_fire6_self_amplifying_table_cell(self):
        """stub-ledger fire 4/6 (D1a): documenting the defect manufactured a new one.

        The table row QUOTES the trigger phrase in order to report it.
        """
        body = (
            "| Detector | What it flagged | Reality |\n"
            "|---|---|---|\n"
            "| stub-ledger | the word stub, then placeholder | Prose, not work |\n"
        )
        ctx = Context(
            tool_name="Write",
            file_path="INPUT-known-harness-defects.md",
            source="tool_input",
        )
        assert not _judge(body, "placeholder", ctx, "marker")

    def test_fire7_blockquote_mention(self):
        """stub-ledger fire 5/6: a quoted finding inside a blockquote."""
        body = "> the stub-ledger flagged a TODO that was only being described\n"
        ctx = Context(tool_name="Write", file_path="notes.md", source="tool_input")
        assert not _judge(body, "TODO", ctx, "marker")

    def test_fire8_inline_code_span_naming_the_marker(self):
        """stub-ledger fire 6/6: `TODO` in backticks is a NAME, not an instance."""
        body = "A genuine `TODO` in a `.py` file still fires; prose must not.\n"
        ctx = Context(tool_name="Write", file_path="docs/fix.md",
                      source="tool_input")
        assert not _judge(body, "TODO", ctx, "marker")

    def test_fire9_marker_scanner_on_assistant_prose(self):
        """The Stop-hook marker scanner (todo-surfacer) fire 1/1.

        It flagged an assistant message for NAMING a marker inside a sentence
        explaining that naming markers trips scanners.
        """
        msg = (
            "Naming a TODO or FIXME marker in prose trips the Stop-hook scanner, "
            "which is the defect we are fixing.\n"
        )
        ctx = Context(tool_name="", file_path="", source="assistant_message")
        assert not _judge(msg, "TODO", ctx, "marker")


# --------------------------------------------------------------------------
# TRUE POSITIVES — known-present controls. Every one MUST still be a USE.
# --------------------------------------------------------------------------


class TestKnownPresentControls:
    """D2: prove the detector still finds a known-present item before trusting it."""

    def test_real_todo_in_a_python_file_still_fires(self):
        body = "def f(x):\n    # TODO: handle the negative branch\n    return x\n"
        ctx = Context(tool_name="Write", file_path="src/calc.py",
                      source="tool_input")
        assert _judge(body, "TODO", ctx, "marker")

    def test_real_notimplemented_in_a_python_file_still_fires(self):
        body = "def g():\n    raise NotImplementedError('later')\n"
        ctx = Context(tool_name="Write", file_path="src/api.py",
                      source="tool_input")
        assert _judge(body, "NotImplementedError", ctx, "marker")

    def test_todo_inside_a_fenced_code_block_still_fires(self):
        body = "Example:\n\n```python\n# TODO: wire this up\n```\n"
        ctx = Context(tool_name="Write", file_path="docs/guide.md",
                      source="tool_input")
        assert _judge(body, "TODO", ctx, "marker")

    def test_actual_destructive_shell_command_still_fires(self):
        cmd = "Remove-Item -Recurse -Force C:/tmp/build"
        ctx = Context(tool_name="PowerShell", file_path="", source="tool_input")
        assert _judge(cmd, "Remove-Item", ctx, "command")

    def test_actual_rm_rf_in_bash_still_fires(self):
        cmd = "rm -rf ./dist && npm run build"
        ctx = Context(tool_name="Bash", file_path="", source="tool_input")
        assert _judge(cmd, "rm -rf", ctx, "command")


# --------------------------------------------------------------------------
# Shell-quoting: a destructive token inside a here-string / quoted literal that
# a SHELL tool is merely writing out is still a mention.
# --------------------------------------------------------------------------


class TestShellQuoting:
    def test_here_string_body_is_data_not_a_command(self):
        """The exact 13.6%-failure workaround shape from the windows-shell rule."""
        cmd = (
            "Set-Content -LiteralPath 'q.md' -Value @'\n"
            "Never run Remove-Item -Force on a system path.\n"
            "'@\n"
        )
        ctx = Context(tool_name="PowerShell", file_path="", source="tool_input")
        assert not _judge(cmd, "Remove-Item -Force", ctx, "command")

    def test_single_quoted_literal_is_data(self):
        cmd = "echo 'rm -rf / is dangerous'"
        ctx = Context(tool_name="Bash", file_path="", source="tool_input")
        assert not _judge(cmd, "rm -rf /", ctx, "command")

    def test_command_after_a_closed_quote_still_fires(self):
        """Guard against a naive quote-parser that swallows the rest of the line."""
        cmd = "echo 'safe' && rm -rf ./dist"
        ctx = Context(tool_name="Bash", file_path="", source="tool_input")
        assert _judge(cmd, "rm -rf", ctx, "command")


# --------------------------------------------------------------------------
# find_real(): the batch API the three detectors actually call.
# --------------------------------------------------------------------------


class TestFindReal:
    def test_filters_mentions_and_keeps_uses_in_one_document(self):
        body = (
            "We must not leave a stub behind.\n"      # prose  -> mention
            "\n```python\n# TODO: real one\n```\n"     # fenced -> use
        )
        ctx = Context(tool_name="Write", file_path="docs/plan.md",
                      source="tool_input")
        pattern = re.compile(r"\b(TODO|stub)\b", re.IGNORECASE)
        kept = find_real(body, pattern, ctx, kind="marker")
        assert [m.group(0) for m in kept] == ["TODO"]

    def test_empty_text_is_silent_and_never_raises(self):
        ctx = Context(tool_name="Write", file_path="x.md", source="tool_input")
        assert find_real("", re.compile("TODO"), ctx, kind="marker") == []

    def test_fail_open_on_a_malformed_span(self):
        """A discriminator that crashes is worse than the bug: it must fail OPEN
        (return True = 'treat as real') so a guard is never silently disarmed."""
        ctx = Context(tool_name="Write", file_path="x.py", source="tool_input")
        assert is_real_occurrence("short", (900, 950), ctx, kind="marker") is True
