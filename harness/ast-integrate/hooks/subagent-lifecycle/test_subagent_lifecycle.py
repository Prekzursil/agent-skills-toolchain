"""Tests for subagent-lifecycle hooks.

Run:  pytest test_subagent_lifecycle.py -v
Pass: all assertions green.

Coverage:
  start.py:
    - goal injected when present (mocked ledger source)
    - no output when no goal
    - agent_type appears in context
    - malformed stdin → exit 0, no output
    - opt-out via env var → exit 0, no output
    - opt-out via .disabled file → exit 0, no output
    - empty stdin → exit 0
  stop.py (updated to use transcript_path — the real SubagentStop field):
    - realistic {session_id, transcript_path, agent_type} payload, no "output" key,
      substantive transcript → SILENCE (C1)
    - transcript with empty final message → flag (C1)
    - transcript with whitespace-only final message → flag
    - transcript with too-short final message → flag
    - missing transcript_path → SILENT fail-open (not flagged)
    - unreadable transcript_path → SILENT fail-open
    - contract pass → silent (no block)
    - contract fail under max-retries → TOP-LEVEL decision:"block" + reason (M1)
    - contract fail at max-retries → give up (no block, exit 0)
    - contract fail over max-retries → give up
    - malformed stdin → exit 0, no output
    - opt-out env var → exit 0
    - SUCCESS:<id> terminal marker → NOT flagged (L3)
    - FAILED:<id> terminal marker → NOT flagged (L3)
  unit:
    - build_context includes agent_type and goal
    - check_degenerate: empty, whitespace, too-short, bare assertion, substantive
    - check_degenerate: SUCCESS:/FAILED: terminal markers are exempt (L3)
    - validate_contract: required_keywords, forbidden_keywords, min_length, empty contract
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Ensure the hook directory is on the path so we can import start / stop / _common.
THIS = Path(__file__).resolve().parent
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """Redirect STATE_ROOT to tmp_path for every test so disk state never bleeds."""
    monkeypatch.setenv("SUBAGENT_LIFECYCLE_STATE_DIR", str(tmp_path / "slife"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_import(module_name: str):
    """Import module_name after clearing it (and _common) from the module cache.

    This guarantees each call gets a module whose module-level code re-runs,
    picking up the current os.environ values (especially STATE_ROOT).
    """
    for m in (module_name, "_common"):
        sys.modules.pop(m, None)
    # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import -- test helper imports a fixed internal hook module by name, not untrusted input
    return importlib.import_module(module_name)


def _capture_main(
    module_name: str,
    stdin_payload,
    env_extras: dict | None = None,
    patches: list | None = None,
) -> tuple[int, dict | None]:
    """Run <module>.main() with controlled stdin/stdout; return (exit_code, parsed_json).

    stdin_payload: dict (serialised to JSON) or raw str (for malformed-input tests).
    env_extras: extra env vars to add via mock.patch.dict (non-destructive).
    patches: list of mock.patch() context managers applied AFTER the module is imported.
    Returns (exit_code, json.loads(stdout)) — None if stdout was empty.
    """
    # Serialise stdin
    stdin_text = (
        json.dumps(stdin_payload)
        if not isinstance(stdin_payload, str)
        else stdin_payload
    )

    # Fresh import so module-level STATE_ROOT picks up the env vars set by the
    # isolated_state_dir fixture.
    mod = _fresh_import(module_name)

    buf = io.StringIO()
    with (
        mock.patch("sys.stdin", io.StringIO(stdin_text)),
        mock.patch("sys.stdout", buf),
        mock.patch.dict(os.environ, env_extras or {}, clear=False),
    ):
        with contextlib.ExitStack() as stack:
            for p in patches or []:
                stack.enter_context(p)
            code = mod.main()

    raw = buf.getvalue().strip()
    return code, json.loads(raw) if raw else None


def _make_transcript(tmp_path: Path, text: str) -> Path:
    """Create a minimal JSONL transcript with *text* as the final assistant message.

    Uses the Shape 1 format that Claude Code emits:
        {"type": "assistant", "message": {"role": "assistant", "content": [...]}}
    """
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir(exist_ok=True)
    p = transcript_dir / "session.jsonl"
    event = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
    }
    p.write_text(json.dumps(event) + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# start.py tests
# ---------------------------------------------------------------------------


class TestSubagentStart:
    """Tests for the SubagentStart hook (start.py)."""

    # -- happy path ----------------------------------------------------------

    def test_injects_goal_when_present(self):
        """Verbatim goal injected as additionalContext in hookSpecificOutput."""
        goal = "Build a widget factory with 100% test coverage"
        code, out = _capture_main(
            "start",
            {"session_id": "s1", "cwd": "/proj", "agent_type": "coder"},
            patches=[mock.patch("start.get_goal", return_value=goal)],
        )
        assert code == 0
        assert out is not None
        hs = out["hookSpecificOutput"]
        assert hs["hookEventName"] == "SubagentStart"
        assert goal in hs["additionalContext"]

    def test_agent_type_appears_in_context(self):
        """The injected context must name the spawned agent type."""
        code, out = _capture_main(
            "start",
            {"session_id": "s1", "cwd": "/proj", "agent_type": "architect"},
            patches=[mock.patch("start.get_goal", return_value="Do something")],
        )
        assert "architect" in out["hookSpecificOutput"]["additionalContext"]

    def test_no_output_when_no_goal(self):
        """No goal in ledger → emit nothing (silent pass)."""
        with mock.patch("start.get_goal", return_value=None):
            code, out = _capture_main(
                "start",
                {"session_id": "s1", "cwd": "/proj", "agent_type": "coder"},
            )
        assert code == 0
        assert out is None

    # -- resilience ----------------------------------------------------------

    def test_malformed_stdin_exits_zero(self):
        """Invalid JSON on stdin → exit 0, no output, no exception raised."""
        code, out = _capture_main("start", "{{{not valid json}}}")
        assert code == 0
        assert out is None

    def test_empty_stdin_exits_zero(self):
        """Empty stdin string → exit 0, no output."""
        code, out = _capture_main("start", "")
        assert code == 0

    # -- opt-out -------------------------------------------------------------

    def test_opt_out_env_var_off(self):
        """SUBAGENT_LIFECYCLE=off → exit 0, no output (even when goal is present)."""
        with mock.patch("start.get_goal", return_value="some goal"):
            code, out = _capture_main(
                "start",
                {"session_id": "s1", "cwd": "/proj", "agent_type": "coder"},
                env_extras={"SUBAGENT_LIFECYCLE": "off"},
            )
        assert code == 0
        assert out is None

    def test_opt_out_env_var_zero(self):
        """SUBAGENT_LIFECYCLE=0 → exit 0, no output."""
        with mock.patch("start.get_goal", return_value="some goal"):
            code, out = _capture_main(
                "start",
                {"session_id": "s1", "cwd": "/proj", "agent_type": "coder"},
                env_extras={"SUBAGENT_LIFECYCLE": "0"},
            )
        assert code == 0
        assert out is None

    def test_opt_out_disabled_file_mocked(self):
        """When is_opted_out() returns True (simulates .disabled file) → silent."""
        with mock.patch("start.is_opted_out", return_value=True):
            code, out = _capture_main(
                "start",
                {"session_id": "s1", "cwd": "/proj", "agent_type": "coder"},
            )
        assert code == 0
        assert out is None


# ---------------------------------------------------------------------------
# stop.py tests
# ---------------------------------------------------------------------------


class TestSubagentStop:
    """Tests for the SubagentStop hook (stop.py).

    All tests use transcript_path (the real SubagentStop payload field).
    The old 'output' field is never present — it is not sent by Claude Code.
    """

    def _run(
        self,
        payload: dict,
        contracts=None,
        retries=None,
        env_extras: dict | None = None,
    ) -> tuple[int, dict | None]:
        """Convenience wrapper: patches load_contract / load_retries / save_retries."""
        patches = []
        if contracts is not None:
            patches.append(mock.patch("stop.load_contract", return_value=contracts))
        if retries is not None:
            patches.append(mock.patch("stop.load_retries", return_value=retries))
            patches.append(mock.patch("stop.save_retries"))  # prevent disk writes
        return _capture_main("stop", payload, env_extras=env_extras, patches=patches)

    # -- clean output, no contract ------------------------------------------

    def test_clean_output_no_contract_silent(self, tmp_path):
        """Substantive transcript + no contract → no output at all (silent approval)."""
        tp = _make_transcript(
            tmp_path,
            "I completed the refactor. Modified 5 files, all tests pass.",
        )
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=None,
        )
        assert code == 0
        assert out is None

    # -- degenerate output checks (read from transcript) --------------------

    def test_degenerate_empty_transcript_message_flags(self, tmp_path):
        """Transcript with empty final assistant message → degenerate flag."""
        tp = _make_transcript(tmp_path, "")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=None,
        )
        assert code == 0
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"].lower()
        assert "empty" in ctx or "no meaningful" in ctx

    def test_degenerate_whitespace_only_flags(self, tmp_path):
        """Transcript with whitespace-only final message → degenerate flag."""
        tp = _make_transcript(tmp_path, "   \n\t  ")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=None,
        )
        assert code == 0
        assert out is not None

    def test_degenerate_too_short_flags(self, tmp_path):
        """Transcript with very short final message → 'brief' flag."""
        tp = _make_transcript(tmp_path, "ok")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=None,
        )
        assert code == 0
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"].lower()
        assert "brief" in ctx or "short" in ctx

    def test_missing_transcript_path_is_silent(self):
        """No transcript_path in payload → silent fail-open (cannot verify output)."""
        # SubagentStop with no transcript_path should never produce a flag —
        # there is nothing to read, so fail-open is the correct behavior.
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder"},
            contracts=None,
        )
        assert code == 0
        assert out is None

    def test_unreadable_transcript_path_is_silent(self):
        """Non-existent transcript_path → silent fail-open."""
        code, out = self._run(
            {
                "session_id": "s1",
                "agent_type": "coder",
                "transcript_path": "/does/not/exist/session.jsonl",
            },
            contracts=None,
        )
        assert code == 0
        assert out is None

    # -- contract: pass ------------------------------------------------------

    def test_contract_pass_silent(self, tmp_path):
        """Transcript satisfies contract constraints → no output (approval)."""
        contract = {
            "required_keywords": ["SUCCESS"],
            "min_length": 10,
            "max_retries": 3,
        }
        tp = _make_transcript(tmp_path, "Task done. SUCCESS — all 5 files modified.")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=contract,
            retries={},
        )
        assert code == 0
        assert out is None

    # -- contract: fail, retry budget available (M1: top-level decision) ---

    def test_contract_fail_under_max_retries_blocks(self, tmp_path):
        """Contract fail, 0 prior attempts < max_retries → TOP-LEVEL decision:'block' + reason."""
        contract = {"required_keywords": ["SUCCESS"], "max_retries": 3}
        tp = _make_transcript(
            tmp_path,
            "I did some work and finished the task but forgot the keyword.",
        )
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=contract,
            retries={"attempts": 0},
        )
        assert code == 0
        assert out is not None
        # decision and reason must be TOP-LEVEL (M1 fix) — NOT nested in hookSpecificOutput
        assert out.get("decision") == "block"
        assert out.get("reason") is not None
        # additionalContext still present in hookSpecificOutput for context injection
        assert "SUCCESS" in out["hookSpecificOutput"]["additionalContext"]

    def test_contract_fail_mentions_attempt_count(self, tmp_path):
        """Feedback message should reference the attempt number."""
        contract = {"required_keywords": ["DONE"], "max_retries": 5}
        tp = _make_transcript(tmp_path, "I finished but forgot the keyword.")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=contract,
            retries={"attempts": 2},
        )
        assert out is not None
        assert out.get("decision") == "block"
        # Should mention attempt 3/5 (2 prior + 1 = 3rd attempt)
        reason = out.get("reason", "")
        assert "3" in reason or "5" in reason

    # -- contract: fail, retry budget exhausted ------------------------------

    def test_contract_fail_at_max_retries_gives_up(self, tmp_path):
        """Contract fail, attempts == max_retries → NO block (give up gracefully)."""
        contract = {"required_keywords": ["SUCCESS"], "max_retries": 3}
        tp = _make_transcript(tmp_path, "Some output without the keyword, at limit.")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=contract,
            retries={"attempts": 3},  # at max
        )
        assert code == 0
        # Must NOT block — allow the subagent to stop
        if out is not None:
            assert out.get("decision") != "block"

    def test_contract_fail_over_max_retries_gives_up(self, tmp_path):
        """Contract fail, attempts > max_retries → give up (no infinite loop)."""
        contract = {"required_keywords": ["DONE"], "max_retries": 2}
        tp = _make_transcript(tmp_path, "Some output without DONE, way past limit.")
        code, out = self._run(
            {"session_id": "s1", "agent_type": "coder", "transcript_path": str(tp)},
            contracts=contract,
            retries={"attempts": 99},  # way over max
        )
        assert code == 0
        if out is not None:
            assert out.get("decision") != "block"

    # -- resilience ----------------------------------------------------------

    def test_malformed_stdin_exits_zero(self):
        """Invalid JSON on stdin → exit 0, no output, no exception."""
        code, out = _capture_main("stop", "{bad json}")
        assert code == 0
        assert out is None

    # -- opt-out -------------------------------------------------------------

    def test_opt_out_env_var_silent(self):
        """SUBAGENT_LIFECYCLE=off → exit 0, no output (opt-out fires before transcript read)."""
        code, out = self._run(
            # No transcript_path: opt-out fires before we'd try to read it
            {"session_id": "s1", "agent_type": "coder"},
            contracts={"required_keywords": ["X"], "max_retries": 1},
            retries={},
            env_extras={"SUBAGENT_LIFECYCLE": "off"},
        )
        assert code == 0
        assert out is None

    def test_opt_out_disabled_file_mocked(self):
        """When is_opted_out() returns True (simulates .disabled file) → silent."""
        code, out = _capture_main(
            "stop",
            {"session_id": "s1", "agent_type": "coder"},
            patches=[mock.patch("stop.is_opted_out", return_value=True)],
        )
        assert code == 0
        assert out is None


# ---------------------------------------------------------------------------
# Real-payload tests (C1 · M1 · L3 — four mandated by adversarial review)
# ---------------------------------------------------------------------------


class TestSubagentStopRealPayload:
    """Realistic SubagentStop payload tests with no 'output' key — only transcript_path.

    These cover the four specific scenarios called out in the adversarial review:
      C1a — substantive transcript, no "output" key → SILENCE
      C1b — degenerate (short) transcript, no "output" key → FLAG
      M1  — contract fail → decision+reason at TOP LEVEL (not inside hookSpecificOutput)
      L3  — SUCCESS:<id> terminal marker → NOT flagged
    """

    def _run(
        self,
        payload: dict,
        contracts=None,
        retries=None,
    ) -> tuple[int, dict | None]:
        patches = []
        if contracts is not None:
            patches.append(mock.patch("stop.load_contract", return_value=contracts))
        if retries is not None:
            patches.append(mock.patch("stop.load_retries", return_value=retries))
            patches.append(mock.patch("stop.save_retries"))
        return _capture_main("stop", payload, patches=patches)

    def test_c1_realistic_payload_substantive_transcript_silent(self, tmp_path):
        """C1: Real SubagentStop shape (session_id+transcript_path+agent_type, NO 'output').
        Substantive transcript → hook stays completely silent."""
        tp = _make_transcript(
            tmp_path,
            "Completed the task. Analysed 12 files, found 3 issues, applied fixes, "
            "all tests now green. See diff for details.",
        )
        payload = {
            "session_id": "abc123",
            "agent_type": "code-reviewer",
            "transcript_path": str(tp),
            # NOTE: no 'output' key — this matches the real SubagentStop schema
        }
        code, out = self._run(payload, contracts=None)
        assert code == 0
        assert out is None, (
            f"Substantive transcript should produce no output — got: {out}"
        )

    def test_c1_degenerate_transcript_flags(self, tmp_path):
        """C1: Real SubagentStop shape, degenerate transcript → hook injects a flag."""
        tp = _make_transcript(tmp_path, "ok")  # 2 chars — well below _MIN_SUBSTANTIVE
        payload = {
            "session_id": "abc123",
            "agent_type": "code-reviewer",
            "transcript_path": str(tp),
        }
        code, out = self._run(payload, contracts=None)
        assert code == 0
        assert out is not None, "Short transcript should produce a degenerate flag"
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "[subagent-lifecycle]" in ctx

    def test_m1_block_decision_is_top_level(self, tmp_path):
        """M1: Contract-fail block emits decision+reason at TOP LEVEL, not inside hookSpecificOutput."""
        contract = {"required_keywords": ["VERIFIED"], "max_retries": 2}
        tp = _make_transcript(
            tmp_path,
            "I finished the analysis but did not include the required keyword.",
        )
        payload = {
            "session_id": "sess-x",
            "agent_type": "tdd-guide",
            "transcript_path": str(tp),
        }
        code, out = self._run(payload, contracts=contract, retries={"attempts": 0})

        assert code == 0
        assert out is not None

        # decision and reason MUST be at the root of the JSON object (M1 fix).
        assert out.get("decision") == "block", (
            f"Expected top-level decision='block', got: {out}"
        )
        assert "reason" in out, f"Expected top-level 'reason' key, got: {out}"

        # additionalContext still lives inside hookSpecificOutput for context injection.
        hs = out.get("hookSpecificOutput", {})
        assert hs.get("additionalContext"), "additionalContext should still be present"
        assert "VERIFIED" in hs["additionalContext"]

    def test_l3_success_terminal_marker_not_flagged(self, tmp_path):
        """L3: SUCCESS:<id> AGENTS.md §4 terminal marker must NOT be flagged as degenerate."""
        tp = _make_transcript(tmp_path, "SUCCESS:42")
        payload = {
            "session_id": "sess-y",
            "agent_type": "coder",
            "transcript_path": str(tp),
        }
        code, out = self._run(payload, contracts=None)
        assert code == 0
        assert out is None, (
            "SUCCESS:42 is a valid §4 terminal marker and must not be flagged — "
            f"got: {out}"
        )

    def test_l3_failed_terminal_marker_not_flagged(self, tmp_path):
        """L3: FAILED:<id> AGENTS.md §4 terminal marker must NOT be flagged as degenerate."""
        tp = _make_transcript(tmp_path, "FAILED:build-timeout exceeded threshold")
        payload = {
            "session_id": "sess-z",
            "agent_type": "coder",
            "transcript_path": str(tp),
        }
        code, out = self._run(payload, contracts=None)
        assert code == 0
        assert out is None, (
            "FAILED:<id> is a valid §4 terminal marker and must not be flagged — "
            f"got: {out}"
        )


# ---------------------------------------------------------------------------
# Unit tests — build_context
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Unit tests for start.build_context (pure function, no I/O)."""

    def test_includes_agent_type_and_goal(self):
        mod = _fresh_import("start")
        result = mod.build_context("architect", "Ship the payment service")
        assert "architect" in result
        assert "Ship the payment service" in result

    def test_prefixed_with_hook_tag(self):
        mod = _fresh_import("start")
        result = mod.build_context("coder", "Any goal")
        assert result.startswith("[subagent-lifecycle]")

    def test_different_agent_types(self):
        mod = _fresh_import("start")
        for agent_type in ("coder", "code-reviewer", "architect", "security-reviewer"):
            result = mod.build_context(agent_type, "Test goal")
            assert agent_type in result


# ---------------------------------------------------------------------------
# Unit tests — check_degenerate
# ---------------------------------------------------------------------------


class TestCheckDegenerate:
    """Unit tests for stop.check_degenerate (pure function)."""

    def _get(self):
        return _fresh_import("stop").check_degenerate

    def test_empty_string_is_degenerate(self):
        assert self._get()("") is not None

    def test_whitespace_only_is_degenerate(self):
        assert self._get()("   \n\t  ") is not None

    def test_single_word_too_short(self):
        assert self._get()("ok") is not None

    def test_done_too_short(self):
        assert self._get()("done") is not None

    def test_success_too_short(self):
        # "success" (7 chars) has no colon — NOT a §4 terminal marker, gets length flag
        assert self._get()("success") is not None

    def test_bare_assertion_done(self):
        # "done" is 4 chars — caught by length check
        assert self._get()("done") is not None

    def test_substantive_output_passes(self):
        assert (
            self._get()(
                "I completed the task. Modified main.py and added 3 tests. All passing."
            )
            is None
        )

    def test_medium_length_meaningful_passes(self):
        assert self._get()("The refactor is complete. 5 files changed.") is None

    def test_returns_string_message_when_degenerate(self):
        result = self._get()("")
        assert isinstance(result, str)
        assert len(result) > 0

    # -- L3: terminal marker exemptions ------------------------------------

    def test_success_terminal_marker_not_flagged(self):
        """SUCCESS:<id> is a §4 marker — must return None even though it is short."""
        assert self._get()("SUCCESS:42") is None

    def test_success_terminal_marker_with_longer_id_not_flagged(self):
        assert self._get()("SUCCESS:build-pipeline-2026") is None

    def test_failed_terminal_marker_not_flagged(self):
        """FAILED:<id> is a §4 marker — must return None."""
        assert self._get()("FAILED:timeout") is None

    def test_failed_terminal_marker_with_reason_not_flagged(self):
        """FAILED:<id> with a trailing reason is still a valid marker."""
        assert self._get()("FAILED:xyz exceeded retries limit") is None

    def test_success_without_colon_is_flagged(self):
        """'success' alone (no colon+id) is NOT a §4 terminal marker."""
        assert self._get()("success") is not None

    def test_failed_without_colon_is_flagged(self):
        """'failed' alone (no colon+id) is NOT a §4 terminal marker."""
        # 6 chars — caught by length check
        assert self._get()("failed") is not None

    def test_success_colon_space_is_not_exempt(self):
        """'SUCCESS: id' with a space after colon is NOT a valid §4 marker."""
        # The marker regex requires a non-whitespace char immediately after ':'
        # "SUCCESS: " would fail [^\s] — so it stays subject to normal checks.
        # "SUCCESS: id" is also short enough (11 chars) to be flagged by length.
        result = self._get()("SUCCESS: ")
        # Either flagged as too short or bare assertion — not exempt
        assert result is not None


# ---------------------------------------------------------------------------
# Unit tests — validate_contract
# ---------------------------------------------------------------------------


class TestValidateContract:
    """Unit tests for stop.validate_contract (pure function)."""

    def _get(self):
        return _fresh_import("stop").validate_contract

    def test_required_keyword_present_passes(self):
        ok, _ = self._get()(
            "Task done. SUCCESS — verified.", {"required_keywords": ["SUCCESS"]}
        )
        assert ok

    def test_required_keyword_missing_fails(self):
        ok, reason = self._get()("Task done.", {"required_keywords": ["SUCCESS"]})
        assert not ok
        assert "SUCCESS" in reason

    def test_forbidden_keyword_absent_passes(self):
        ok, _ = self._get()("All good.", {"forbidden_keywords": ["ERROR"]})
        assert ok

    def test_forbidden_keyword_present_fails(self):
        ok, reason = self._get()(
            "ERROR: something went wrong.", {"forbidden_keywords": ["ERROR"]}
        )
        assert not ok
        assert "ERROR" in reason

    def test_min_length_pass(self):
        ok, _ = self._get()("A" * 100, {"min_length": 50})
        assert ok

    def test_min_length_fail(self):
        ok, reason = self._get()("short text here", {"min_length": 50})
        assert not ok
        assert "50" in reason or "short" in reason.lower()

    def test_empty_contract_passes_anything(self):
        ok, _ = self._get()("whatever output", {})
        assert ok

    def test_multiple_failures_combined_in_reason(self):
        ok, reason = self._get()(
            "bad",
            {
                "required_keywords": ["SUCCESS", "VERIFIED"],
                "min_length": 100,
            },
        )
        assert not ok
        # reason should mention at least one of the failures
        assert "SUCCESS" in reason or "VERIFIED" in reason or "100" in reason

    def test_none_output_treated_as_empty(self):
        # validate_contract receives str(output or ""), so None is already ""
        ok, reason = self._get()("", {"min_length": 50})
        assert not ok
