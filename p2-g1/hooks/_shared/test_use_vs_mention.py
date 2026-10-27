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
    Judgement,
    Verdict,
    audit_subject_rule,
    classify,
    find_real,
    is_real_occurrence,
)


# Synthetic, non-functional fixture. Assembled from fragments ON PURPOSE: this repo is
# PUBLIC, and a whole `ghp_`-shaped literal is indistinguishable from a live token to
# GitHub secret scanning (and to any credential-shape linter). The runtime value is
# byte-identical to the single literal it replaces, so every assertion below is unchanged.
_FAKE_PAT = "ghp" + "_" + "9f2Ab7Qz1LmNpR4sT6uV8wX0yZ3cD5eF7gH"


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
            tool_name="Write",
            file_path="rules/common/windows-shell.md",
            source="tool_input",
        )
        assert not _judge(body, "rm -rf /", ctx, "command")

    def test_fire3_word_stub_in_a_markdown_paragraph(self):
        """stub-ledger fire 1/6: prose describing a fixture, not pending work."""
        body = "The fixture is a stub that returns a canned response.\n"
        ctx = Context(
            tool_name="Write", file_path="docs/design.md", source="tool_input"
        )
        assert not _judge(body, "stub", ctx, "marker")

    def test_fire4_reworded_to_test_double_still_flagged(self):
        """stub-ledger fire 2/6: rewording chased the matcher instead of fixing it."""
        body = "The fixture is a test double, i.e. a placeholder object.\n"
        ctx = Context(
            tool_name="Write", file_path="docs/design.md", source="tool_input"
        )
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
        ctx = Context(tool_name="Write", file_path="docs/fix.md", source="tool_input")
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
        ctx = Context(tool_name="Write", file_path="src/calc.py", source="tool_input")
        assert _judge(body, "TODO", ctx, "marker")

    def test_real_notimplemented_in_a_python_file_still_fires(self):
        body = "def g():\n    raise NotImplementedError('later')\n"
        ctx = Context(tool_name="Write", file_path="src/api.py", source="tool_input")
        assert _judge(body, "NotImplementedError", ctx, "marker")

    def test_todo_inside_a_fenced_code_block_still_fires(self):
        body = "Example:\n\n```python\n# TODO: wire this up\n```\n"
        ctx = Context(tool_name="Write", file_path="docs/guide.md", source="tool_input")
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


class TestResultKind:
    """kind="result" — the value-not-key judge for a TOOL RESULT payload.

    Closes the corpus GAP recorded as RES-FP-fieldname / RES-TP-failvalue
    ("the discriminator has no 'result' kind ... needs a value-not-key judge").

    `json_value_text()` already drops field NAMES structurally, but only while the
    whole payload parses. A payload truncated by a caller's size cap, or a JSON/YAML
    document embedded inside a returned string, falls back to a flat-text scan where
    the key is visible again — so the rule also has to hold LEXICALLY.
    """

    RESULT_CTX = Context(tool_name="PostToolUse", file_path="", source="file")

    def test_quoted_json_key_is_a_mention(self):
        """The recorded Databricks fire, reached via the raw-text fallback."""
        raw = '{"state": {"life_cycle_state": "RUNNING", "user_cancelled_or_timedout": false'
        assert not _judge(raw, "timedout", self.RESULT_CTX, "result")

    def test_quoted_key_truncated_at_the_closing_quote_is_a_mention(self):
        """Truncation can cut the payload right after the key's closing quote."""
        raw = '{"data": {"user_cancelled_or_timedout"'
        assert not _judge(raw, "timedout", self.RESULT_CTX, "result")

    def test_embedded_config_key_in_a_returned_document_is_a_mention(self):
        """The recorded github get_file_contents fire: `"timeout": 100000`."""
        doc = 'Set the budget:\n{\n  "timeout": 100000\n}\n'
        assert not _judge(doc, "timeout", self.RESULT_CTX, "result")

    def test_same_word_as_a_VALUE_is_a_real_occurrence(self):
        """The discriminating control: key-vs-value is the ONLY difference."""
        raw = '{"state": {"result_state": "TIMEDOUT"}}'
        assert _judge(raw, "TIMEDOUT", self.RESULT_CTX, "result")

    def test_multiword_phrase_is_never_read_as_a_key(self):
        raw = '{"detail": "timed out waiting for the server"}'
        assert _judge(raw, "timed out", self.RESULT_CTX, "result")

    def test_unquoted_word_before_a_colon_is_NOT_treated_as_a_key(self):
        """Quoted keys ONLY. An error message is commonly `Timeout: <cause>`, so an
        unquoted-key rule would silence a genuine report. Residual, disclosed: a bare
        YAML key (`timeout: 30`) in a result body is therefore still scanned.

        Both spellings are asserted because the `lo == 0` arm of the quote test is
        only reachable at index 0: a mutation that relaxed just that arm SURVIVED the
        first version of this test, since the closer-matches-opener check happened to
        keep the verdict right. The mid-string spelling is what actually pins the
        quoted-only design.
        """
        assert _judge(
            "Timeout: the server never answered", "Timeout", self.RESULT_CTX, "result"
        )
        raw = "probe result -- Timeout: the server never answered"
        assert _judge(raw, "Timeout", self.RESULT_CTX, "result")

    def test_a_NEWLINE_between_the_token_and_the_colon_is_NOT_a_key(self):
        r"""Pins `_KEY_COLON = ^[ \t]*:` (colon on the SAME line) against `\s*`.

        MUTANT V10 -- one of two survivors of an INDEPENDENT 15-mutation harness run
        against this branch. Relaxing the key-colon pattern to `\s*` lets a quoted
        token on one line be adopted as the key of a colon on the NEXT line, turning
        this real report into a mention.

        Honest scope: the shape is CONTRIVED -- no JSON emitter produces it -- so no
        claim about live payloads rests on this test, and the surviving mutant refuted
        no behaviour. What it pins is the DOCUMENTED one-line constraint at
        `_KEY_COLON`, which until now was guarded only by a comment, and the DIRECTION
        of the risk: relaxing it can only convert a report into a mention, never the
        reverse.
        """
        raw = '{"error": "TIMEDOUT"\n: 1}'
        assert raw.count("\n") == 1, "premise: the colon must sit on the NEXT line"
        assert _judge(raw, "TIMEDOUT", self.RESULT_CTX, "result")

    def test_a_MISMATCHED_quote_pair_is_NOT_a_key(self):
        """Pins the closer-must-match-opener check against dropping it.

        MUTANT V11 -- the second independent survivor. Accepting ANY quote character
        as the closer (instead of the one that opened the token) lets a mixed pair be
        read as a field name, which silences the match. Asserted in BOTH directions so
        neither half of the pair carries the test alone.

        Honest scope: contrived like V10. It pins the documented decision at the
        `tail[0] != text[lo - 1]` guard, not a measured live payload.
        """
        assert _judge("{'ETIMEDOUT\": 1}", "ETIMEDOUT", self.RESULT_CTX, "result")
        assert _judge("{\"ETIMEDOUT': 1}", "ETIMEDOUT", self.RESULT_CTX, "result")

    def test_fenced_example_in_a_returned_document_is_a_mention(self):
        doc = "You will see:\n\n```console\ncurl: (28) Operation timed out\n```\n\nRetry.\n"
        assert not _judge(doc, "timed out", self.RESULT_CTX, "result")

    def test_error_after_a_closed_fence_still_fires(self):
        """Guard against a fence parser that swallows the tail of the payload."""
        doc = "Doc:\n```json\n{}\n```\nMCP error -32000: server is not responding"
        assert _judge(doc, "MCP error", self.RESULT_CTX, "result")

    def test_unclosed_fence_does_NOT_swallow_a_later_real_error(self):
        """A truncated document leaves an UNCLOSED fence. Suppressing to EOF there
        would silence every real error after it, so only CLOSED fences count."""
        doc = 'Doc:\n```json\n{\n  "retries": 3\nconnection refused by the server'
        assert _judge(doc, "connection refused", self.RESULT_CTX, "result")

    def test_inline_code_span_is_a_mention(self):
        doc = "the field `user_cancelled_or_timedout` is False on a running job"
        assert not _judge(doc, "timedout", self.RESULT_CTX, "result")

    def test_negated_sentence_is_a_mention(self):
        doc = "Nothing failed and no connection timed out here."
        assert not _judge(doc, "timed out", self.RESULT_CTX, "result")

    def test_negation_window_does_not_reach_a_previous_line(self):
        """A negation cue 2 lines up in a serialized payload has no bearing on this
        report; an unbounded window would silence real failures in long payloads."""
        doc = 'no retries configured\nrun_id 1011848026466066\n"error": "connection refused"'
        assert _judge(doc, "connection refused", self.RESULT_CTX, "result")

    def test_negation_window_is_bounded_in_a_NEWLINE_FREE_payload(self):
        """The case the previous test cannot reach, and the one that actually bites.

        A truncated JSON payload is ONE long line with no sentence terminator, so the
        sentence-start clamp degenerates to offset 0 and an unbounded window spans the
        whole blob. A single ordinary `not` anywhere upstream would then silence every
        genuine failure in the payload. Realistic: Databricks emits
        `"state_message": "Cluster not available yet"` while the same body carries the
        real transport error.
        """
        pad = ", ".join(f'"task_{i:02d}": "unit_{i:02d}_running"' for i in range(12))
        blob = (
            '{"state_message": "Cluster not available yet", '
            + pad
            + ', "error": "connection refused"}'
        )
        assert blob.count("\n") == 0, "premise: the payload must be a single line"
        idx = blob.index("connection refused")
        assert idx - blob.index("not available") > 200, "cue must be outside the window"
        assert _judge(blob, "connection refused", self.RESULT_CTX, "result")

    def test_result_kind_fails_open_on_a_malformed_span(self):
        assert is_real_occurrence("short", (900, 950), self.RESULT_CTX, kind="result")


class TestFindReal:
    def test_filters_mentions_and_keeps_uses_in_one_document(self):
        body = (
            "We must not leave a stub behind.\n"  # prose  -> mention
            "\n```python\n# TODO: real one\n```\n"  # fenced -> use
        )
        ctx = Context(tool_name="Write", file_path="docs/plan.md", source="tool_input")
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


# --------------------------------------------------------------------------
# P2-01 TYPED VERDICT. The discriminator must be able to say "I could not tell"
# and have the caller surface it, rather than silently picking a side. A bare
# bool structurally cannot express that, which is why classify() exists.
# --------------------------------------------------------------------------
class TestTypedVerdict:
    def test_a_mention_is_typed_MENTION_and_names_its_rule(self):
        text = "The doc says do not add a TODO here.\n"
        ctx = Context(tool_name="Write", file_path="notes.md", source="tool_input")
        j = classify(text, _span(text, "TODO"), ctx, kind="marker")
        assert isinstance(j, Judgement)
        assert j.verdict is Verdict.MENTION
        assert j.rule, "a verdict with no rule is unauditable"
        assert j.is_real is False

    def test_a_real_occurrence_is_typed_USE(self):
        text = "# TODO: wire the retry path\n"
        ctx = Context(tool_name="Write", file_path="src/router.py", source="tool_input")
        j = classify(text, _span(text, "TODO"), ctx, kind="marker")
        assert j.verdict is Verdict.USE
        assert j.is_real is True

    def test_a_malformed_span_is_UNKNOWN_not_a_guess(self):
        """The third state is the point of P2-01: a check that cannot prove it ran
        must be able to report NOT-CHECKED rather than silently returning a side."""
        ctx = Context(tool_name="Write", file_path="x.py", source="tool_input")
        j = classify("short", (900, 950), ctx, kind="marker")
        assert j.verdict is Verdict.UNKNOWN
        assert j.rule == "bad-span"

    def test_an_unrecognised_kind_is_UNKNOWN_and_fails_OPEN(self):
        """Regression: an unknown kind used to fall through to the marker branch and
        inherit marker semantics in silence, so a guard that merely MISSPELLED its
        kind could be silently disarmed in prose. Surfacing UNKNOWN can only make a
        caller fire more, never less."""
        text = "A TODO left in the design note still needs an owner.\n"
        ctx = Context(tool_name="Write", file_path="docs/plan.md", source="tool_input")
        j = classify(text, _span(text, "TODO"), ctx, kind="markr")
        assert j.verdict is Verdict.UNKNOWN
        assert j.rule == "unknown-kind"
        # and the bool projection must be True (fail-open), NOT the marker answer
        assert is_real_occurrence(text, _span(text, "TODO"), ctx, kind="markr") is True

    def test_UNKNOWN_projects_to_True_so_no_guard_is_disarmed(self):
        assert Judgement(Verdict.UNKNOWN, "x", "y").is_real is True
        assert bool(Judgement(Verdict.UNKNOWN, "x", "y")) is True
        assert bool(Judgement(Verdict.MENTION, "x", "y")) is False
        assert bool(Judgement(Verdict.USE, "x", "y")) is True

    def test_verdict_serialises_as_a_plain_string_for_a_receipt(self):
        import json

        assert json.dumps({"v": Verdict.UNKNOWN}) == '{"v": "UNKNOWN"}'

    def test_is_real_occurrence_still_returns_a_plain_bool(self):
        """The four already-wired guards call the bool API; it must not start
        returning a Judgement at them."""
        text = "# TODO: x\n"
        ctx = Context(tool_name="Write", file_path="a.py", source="tool_input")
        out = is_real_occurrence(text, _span(text, "TODO"), ctx, kind="marker")
        assert out is True and isinstance(out, bool)


# --------------------------------------------------------------------------
# DESIGN RULE 4 -- the audit-subject allowlist. A file whose JOB is to test or
# guard a thing legitimately carries that thing's shape.
# --------------------------------------------------------------------------
class TestAuditSubjectAllowlist:
    def test_a_fixture_path_silences_a_secret_shaped_literal(self):
        text = 'LEAKED = "AKIAIOSFODNN7REALLOOK"'
        ctx = Context(
            tool_name="Write",
            file_path="hooks/deny-credential-reads/fixtures/leaked_key.py",
            source="tool_input",
        )
        assert (
            classify(
                text, _span(text, "AKIAIOSFODNN7REALLOOK"), ctx, kind="secret"
            ).verdict
            is Verdict.MENTION
        )

    def test_a_test_basename_outside_a_tests_dir_is_still_an_audit_subject(self):
        text = 'EXPECTED = "AKIAIOSFODNN7REALLOOK"'
        ctx = Context(
            tool_name="Write",
            file_path="src/redact/test_redaction.py",
            source="tool_input",
        )
        assert (
            classify(
                text, _span(text, "AKIAIOSFODNN7REALLOOK"), ctx, kind="secret"
            ).verdict
            is Verdict.MENTION
        )

    def test_a_production_path_still_FIRES(self):
        """The control that stops the allowlist from being a blinding shortcut."""
        text = f'TOKEN = "{_FAKE_PAT}"'
        ctx = Context(
            tool_name="Write", file_path="services/api/settings.py", source="tool_input"
        )
        assert (
            classify(text, _span(text, _FAKE_PAT), ctx, kind="secret").verdict
            is Verdict.USE
        )

    def test_a_guard_named_directory_is_not_its_own_violation(self):
        """A hook named after what it blocks contains the word it blocks."""
        text = "claude/hooks/deny-credential-reads/deny.py"
        ctx = Context(source="file", file_path=text)
        assert (
            classify(text, _span(text, "credential"), ctx, kind="pathword").verdict
            is Verdict.MENTION
        )

    def test_a_real_credential_path_still_FIRES(self):
        text = "home/miky/.aws/credentials"
        ctx = Context(source="file", file_path=text)
        assert (
            classify(text, _span(text, "credentials"), ctx, kind="pathword").verdict
            is Verdict.USE
        )

    def test_audit_subject_rule_is_exported_and_names_the_exemption(self):
        assert audit_subject_rule("tests/conftest.py").startswith("audit-subject:")
        assert audit_subject_rule("hooks/deny-credential-reads/deny.py") == (
            "audit-subject:guard-dir"
        )
        assert audit_subject_rule("services/api/settings.py") == ""
        assert audit_subject_rule("") == ""

    def test_no_fake_declaration_heuristic_silences_a_production_key(self):
        """A self-declared-fake rule was written, refuted by mutation, and REMOVED.
        This pins its absence: a comment must NOT be able to talk a real key at a
        production path into silence."""
        text = f'# synthetic key, non-functional\nTOKEN = "{_FAKE_PAT}"'
        ctx = Context(
            tool_name="Write", file_path="services/api/settings.py", source="tool_input"
        )
        assert (
            classify(text, _span(text, _FAKE_PAT), ctx, kind="secret").verdict
            is Verdict.USE
        )


# --------------------------------------------------------------------------
# THE RECURSION TERMINATOR (measured live 2026-08-08). A script that enumerates
# the needles it wants deferred necessarily CONTAINS those needles, so per-needle
# deferral produced 13 NEW fires and a script deferring THOSE would produce more.
# Only a rule about ROLE terminates it: a marker spelled inside a string literal
# is data, not pending work.
# --------------------------------------------------------------------------
class TestStringLiteralRule:
    RULES = (
        "RULES = [\n"
        '    "_stubscan_proof.py::# todo: wire this up",\n'
        '    "_stubscan_proof.py::raise notimplementederror",\n'
        "]\n"
    )

    def test_a_needle_inside_a_string_literal_is_a_mention(self):
        ctx = Context(file_path="_defer_stub_fixtures.py", source="file")
        j = classify(
            self.RULES, _span(self.RULES, "# todo: wire this up"), ctx, kind="stub"
        )
        assert j.verdict is Verdict.MENTION
        assert j.rule == "stub:string-literal"

    def test_the_rule_is_structural_not_a_filename_accident(self):
        """Identical content under a name matching NO fixture/test pattern must also be
        silent. If this fails, the silence came from `_fixtures.py` matching the
        audit-subject basename rule rather than from the string-literal rule."""
        ctx = Context(file_path="_defer_stub_needles.py", source="file")
        assert audit_subject_rule("_defer_stub_needles.py") == ""
        j = classify(
            self.RULES, _span(self.RULES, "# todo: wire this up"), ctx, kind="stub"
        )
        assert j.verdict is Verdict.MENTION

    def test_a_real_raise_NotImplementedError_still_FIRES(self):
        """The control that killed the first attempt. An apostrophe-naive quote scanner
        blinded all five genuine sites in fbmcp/dm_e2ee.py:155-167."""
        text = (
            "class S:\n    def encrypt(self, p):\n        raise NotImplementedError\n"
        )
        ctx = Context(file_path="fbmcp/dm_e2ee.py", source="file")
        assert (
            classify(text, _span(text, "NotImplementedError"), ctx, kind="stub").verdict
            is Verdict.USE
        )

    def test_a_real_comment_still_FIRES(self):
        text = "def handler():\n    # TODO: wire the retry path\n    return None\n"
        ctx = Context(file_path="src/handler.py", source="file")
        assert (
            classify(text, _span(text, "# TODO"), ctx, kind="stub").verdict
            is Verdict.USE
        )

    def test_a_docstring_is_a_string_literal(self):
        text = '"""Doc that quotes raise NotImplementedError as an example."""\nX = 1\n'
        ctx = Context(file_path="mod.py", source="file")
        assert (
            classify(text, _span(text, "NotImplementedError"), ctx, kind="stub").verdict
            is Verdict.MENTION
        )

    def test_non_python_is_UNFILTERED_fail_open(self):
        text = "function Invoke-Thing {\n    # stub scope\n}\n"
        ctx = Context(file_path="tools/harness.ps1", source="file")
        assert (
            classify(text, _span(text, "# stub scope"), ctx, kind="stub").verdict
            is Verdict.USE
        )

    def test_non_python_that_PARSES_as_python_is_still_unfiltered(self):
        """A bare quoted line is valid PowerShell AND a valid Python expression. Without
        the extension guard, ast would silence a real marker in a shell script."""
        text = '"# stub scope"\n'
        ctx = Context(file_path="tools/harness.ps1", source="file")
        assert (
            classify(text, _span(text, "# stub scope"), ctx, kind="stub").verdict
            is Verdict.USE
        )

    def test_unparseable_python_is_UNFILTERED_fail_open(self):
        text = "def broken(:\n    # TODO: fix the syntax\n"
        ctx = Context(file_path="src/broken.py", source="file")
        assert (
            classify(text, _span(text, "# TODO"), ctx, kind="stub").verdict
            is Verdict.USE
        )

    def test_the_recursion_terminates_at_depth_two(self):
        """A script that defers THIS script's needles is itself silent, without anyone
        adding a new path or a new needle."""
        depth2 = 'RULES = [\n    "_defer_stub_fixtures.py::# todo: wire this up",\n]\n'
        ctx = Context(file_path="_defer_the_deferrer.py", source="file")
        assert (
            classify(
                depth2, _span(depth2, "# todo: wire this up"), ctx, kind="stub"
            ).verdict
            is Verdict.MENTION
        )
