#!/usr/bin/env python3
"""C16 acceptance tests — typed failure taxonomy, per-class handler, per-node timeout,
and the runtime-enforced two-strikes fingerprint breaker.

Written test-first (TDD). The spec (07-OPTIONS-C.md C16) demands, verbatim:
  * each named failure class is classified and routed to the CORRECT handler;
  * a hung agent is KILLED at its timeout instead of stalling the phase;
  * a THIRD identical-fingerprint attempt is actually REFUSED;
  * every node carries a mandatory ``timeout_s`` — a missing one is a lint failure.
Each test below fault-injects one of those conditions (the "cassette" the spec asks for).
"""

from __future__ import annotations

import pytest

from failure_taxonomy import (
    CODEX_EXIT,
    RATE_LIMITED,
    SCHEMA_INVALID,
    SEVERED_STREAM,
    TIMEOUT,
    UNCLASSIFIED,
    WIN_ARG_LIMIT,
    TwoStrikesBreaker,
    classify_failure,
    handler_for,
    require_timeout_s,
)


# --------------------------------------------------------------- classification
class TestClassification:
    def test_timeout_wins_over_everything(self):
        # A runtime-declared timeout is authoritative regardless of exit/stderr.
        assert (
            classify_failure(timed_out=True, exit_code=0, stderr="429 blah") == TIMEOUT
        )

    def test_win_arg_limit_from_os_error_206(self):
        # The measured Windows CreateProcess 32767-char cap (cross-vendor-dispatch #3).
        assert (
            classify_failure(exit_code=1, stderr="CreateProcess ... os error 206")
            == WIN_ARG_LIMIT
        )

    def test_win_arg_limit_from_payload_len(self):
        assert (
            classify_failure(exit_code=1, stderr="payload_len=34472") == WIN_ARG_LIMIT
        )

    def test_rate_limited_from_429(self):
        assert (
            classify_failure(exit_code=1, stderr="HTTP 429 Too Many Requests")
            == RATE_LIMITED
        )

    def test_rate_limited_from_overloaded(self):
        assert (
            classify_failure(exit_code=1, stderr="Error: overloaded_error")
            == RATE_LIMITED
        )

    def test_schema_invalid_from_flag(self):
        assert classify_failure(schema_valid=False) == SCHEMA_INVALID

    def test_severed_stream_exit_zero_no_artifact(self):
        # Exit 0 with no valid artifact is a severed stream, not a success (completion.py rule 2).
        assert classify_failure(exit_code=0, artifact_ok=False) == SEVERED_STREAM

    def test_codex_exit_nonzero(self):
        assert classify_failure(exit_code=7, stderr="codex crashed") == CODEX_EXIT

    def test_nonzero_exit_with_novel_stderr_is_codex_exit(self):
        # A nonzero exit IS classifiable -- it is the taxonomy's codex-exit-<n> bucket.
        assert classify_failure(exit_code=1, stderr="something novel") == CODEX_EXIT

    def test_no_failure_signal_is_unclassified_not_a_crash(self):
        # UNCLASSIFIED is reserved for a failure with NO usable signal at all (the spec's
        # named failure mode: a novel shape must fail VISIBLY, never a silent default).
        assert classify_failure() == UNCLASSIFIED
        assert classify_failure(stderr="weird but exit unknown") == UNCLASSIFIED


# ------------------------------------------------------------------- handlers
class TestHandlers:
    def test_win_arg_limit_retries_once_with_ignore_user_config(self):
        h = handler_for(WIN_ARG_LIMIT)
        assert h.action == "retry"
        assert h.max_retries == 1
        assert h.retry_mutation == "--ignore-user-config"

    def test_rate_limited_backs_off_with_jitter(self):
        h = handler_for(RATE_LIMITED)
        assert h.action == "backoff"
        assert h.backoff is True
        assert h.max_retries >= 1

    def test_schema_invalid_reasks_once_then_fails(self):
        h = handler_for(SCHEMA_INVALID)
        assert h.action == "reask"
        assert h.max_retries == 1
        assert h.terminal_on_exhaust == "FAILED"

    def test_severed_stream_redispatches_once_then_unknown(self):
        h = handler_for(SEVERED_STREAM)
        assert h.action == "redispatch"
        assert h.max_retries == 1
        assert h.terminal_on_exhaust == "UNKNOWN"

    def test_timeout_kills_and_never_retries(self):
        h = handler_for(TIMEOUT)
        assert h.action == "kill"
        assert h.max_retries == 0  # kill and mark — never hang, never blanket-retry

    def test_unclassified_fails_without_retry(self):
        # A misclassification must NOT produce a retry storm — the spec's stated failure mode.
        h = handler_for(UNCLASSIFIED)
        assert h.action == "fail"
        assert h.max_retries == 0

    def test_unknown_class_is_a_hard_error_not_a_silent_default(self):
        with pytest.raises(KeyError):
            handler_for("not-a-real-class")


# ------------------------------------------------------- per-node timeout lint
class TestTimeoutLint:
    def test_missing_timeout_s_is_a_lint_failure(self):
        with pytest.raises(ValueError):
            require_timeout_s({"id": "n1"})  # no timeout_s at all

    def test_zero_timeout_s_is_a_lint_failure(self):
        with pytest.raises(ValueError):
            require_timeout_s({"id": "n1", "timeout_s": 0})

    def test_negative_timeout_s_is_a_lint_failure(self):
        with pytest.raises(ValueError):
            require_timeout_s({"id": "n1", "timeout_s": -5})

    def test_non_numeric_timeout_s_is_a_lint_failure(self):
        with pytest.raises(ValueError):
            require_timeout_s({"id": "n1", "timeout_s": "soon"})

    def test_bool_timeout_s_is_a_lint_failure(self):
        # bool is a subclass of int in Python; True must NOT count as a valid timeout.
        with pytest.raises(ValueError):
            require_timeout_s({"id": "n1", "timeout_s": True})

    def test_positive_timeout_s_passes_and_returns_float(self):
        assert require_timeout_s({"id": "n1", "timeout_s": 1800}) == 1800.0


# --------------------------------------------------- two-strikes fingerprint breaker
class TestTwoStrikesBreaker:
    def test_first_attempt_not_refused(self):
        b = TwoStrikesBreaker()
        assert b.refuses("fp-A") is False

    def test_third_identical_attempt_is_refused(self):
        b = TwoStrikesBreaker()
        b.record_failure("fp-A")  # attempt 1 failed
        assert b.refuses("fp-A") is False  # attempt 2 still allowed
        b.record_failure("fp-A")  # attempt 2 failed -> two strikes
        assert b.refuses("fp-A") is True  # attempt 3 refused (spec: refuse a third)

    def test_success_resets_the_streak(self):
        b = TwoStrikesBreaker()
        b.record_failure("fp-A")
        b.record_failure("fp-A")
        assert b.refuses("fp-A") is True
        b.record_success("fp-A")
        assert b.refuses("fp-A") is False  # a green result clears the breaker

    def test_different_fingerprints_are_independent(self):
        # A legitimately different third approach must NOT be blocked by another's strikes.
        b = TwoStrikesBreaker()
        b.record_failure("fp-A")
        b.record_failure("fp-A")
        assert b.refuses("fp-B") is False

    def test_escalation_names_the_fingerprint_and_demands_an_alternative(self):
        b = TwoStrikesBreaker()
        b.record_failure("fp-A")
        b.record_failure("fp-A")
        esc = b.escalation("fp-A")
        assert esc["fingerprint"] == "fp-A"
        assert esc["consecutive_failures"] == 2
        assert "alternative" in esc["demand"].lower()

    def test_configurable_limit(self):
        b = TwoStrikesBreaker(limit=3)  # three strikes before refusal
        b.record_failure("fp-A")
        b.record_failure("fp-A")
        assert b.refuses("fp-A") is False  # still allowed at 2 when limit=3
        b.record_failure("fp-A")
        assert b.refuses("fp-A") is True

    def test_limit_below_one_is_rejected(self):
        with pytest.raises(ValueError):
            TwoStrikesBreaker(limit=0)

    def test_record_failure_returns_the_running_count(self):
        b = TwoStrikesBreaker()
        assert b.record_failure("fp-A") == 1
        assert b.record_failure("fp-A") == 2
        assert b.consecutive_failures("fp-A") == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
