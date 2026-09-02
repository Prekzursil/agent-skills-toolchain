"""Conformance suite for :mod:`monitorcore.dbx_completion` — the VERSIONED C1 gate.

WRITE-AS-YOU-GO (fan-out contract C1): every behaviour is enumerated by name. If a test in
this file still reads ``NOT-YET-IMPLEMENTED`` then the unit died before measuring anything
and NO verdict here may be cited.

COVERAGE: all 15 behaviours measured against the real module.

Each test isolates ONE gate. The two window tests are deliberately *self-proving*: they
assert that a 600-CHARACTER window and a 600-BYTE window genuinely disagree on the fixture
before asserting which one the contract implements.
"""

from __future__ import annotations

import pytest

from monitorcore.dbx_completion import (
    CONTRACT_VERSION,
    DEFAULT_MIN_BYTES,
    SENTINEL_TAIL_BYTES,
    Event,
    EventKind,
    Expectation,
    State,
    Verdict,
    classify,
)

UID = "U-042"
BUNDLE = "deadbeefcafe"
OTHER_BUNDLE = "0123456789ab"

#: The C1 pin, HARDCODED on purpose. The window fixtures below are built against this
#: literal rather than against ``SENTINEL_TAIL_BYTES`` so that widening the module constant
#: is caught as a BEHAVIOUR change at the verdict, not as a self-referentially broken
#: fixture premise (a fixture that moves with the constant it is meant to police proves
#: nothing).
_WINDOW = 600


def test_the_sentinel_window_is_pinned_at_600_bytes() -> None:
    """The contract's window is a fixed BYTE count; drifting it redefines fleet-wide 'done'."""
    assert SENTINEL_TAIL_BYTES == _WINDOW
    assert DEFAULT_MIN_BYTES == 1024


# --------------------------------------------------------------------------------------
# fixtures / helpers
# --------------------------------------------------------------------------------------
def _sentinel(uid: str = UID, bundle: str = BUNDLE) -> str:
    """The C1 sentinel line — carries the identity and the provenance it attests."""
    return f"UNIT-COMPLETE: {uid} bundle={bundle}\n"


def _good_artifact(tmp_path, *, uid: str = UID, bundle: str = BUNDLE):
    """A well-formed artifact: >= 1024 B, sentinel inside the last 600 BYTES."""
    path = tmp_path / "unit.out"
    path.write_bytes(b"x" * 2000 + _sentinel(uid, bundle).encode("utf-8"))
    return path


def _expect(path, *, uid: str = UID, bundle: str = BUNDLE, **kw) -> Expectation:
    return Expectation(
        logical_unit_id=uid,
        input_bundle_hash=bundle,
        artifact_path=str(path),
        **kw,
    )


class _RaisingProbe:
    """A detector that is BROKEN, not a detector reporting an absence."""

    def __init__(self, exc: Exception, *, fail_on: str = "size") -> None:
        self._exc = exc
        self._fail_on = fail_on

    def exists(self, path: str) -> bool:
        if self._fail_on == "exists":
            raise self._exc
        return True

    def size(self, path: str) -> int:
        if self._fail_on == "size":
            raise self._exc
        return DEFAULT_MIN_BYTES + 1

    def read_tail(self, path: str, nbytes: int) -> bytes:
        if self._fail_on == "read_tail":
            raise self._exc
        return _sentinel().encode("utf-8")

    def mtime(self, path: str) -> float:
        if self._fail_on == "mtime":
            raise self._exc
        return 100.0


# --------------------------------------------------------------------------------------
# gate 1/2: existence + minimum size
# --------------------------------------------------------------------------------------
def test_exit_zero_with_no_artifact_is_severed_not_done(tmp_path) -> None:
    """Exit code zero alone is NEVER success — and neither is a glowing self-report."""
    exp = _expect(tmp_path / "never-written.out")

    verdict = classify(
        exp,
        exit_code=0,
        agent_self_report="All work completed successfully. UNIT-COMPLETE.",
    )

    assert verdict.state is State.SEVERED
    assert verdict.state is not State.DONE
    # the self-report was recorded as a signal but granted nothing
    assert verdict.signals.get("agent_self_report_trusted") is False


def test_artifact_exactly_1023_bytes_is_not_done(tmp_path) -> None:
    """1023 < 1024 — one byte under the floor is a truncated stream."""
    path = tmp_path / "unit.out"
    body = _sentinel().encode("utf-8")
    path.write_bytes(b"x" * (1023 - len(body)) + body)
    assert path.stat().st_size == 1023

    verdict = classify(_expect(path), exit_code=0)

    assert verdict.state is State.SEVERED
    assert verdict.state is not State.DONE
    assert verdict.artifact_bytes == 1023


def test_artifact_truncated_at_exactly_1024_bytes_is_not_done(tmp_path) -> None:
    """Size gate passes at exactly the floor, but the stream was cut before the sentinel."""
    path = tmp_path / "unit.out"
    path.write_bytes(b"x" * DEFAULT_MIN_BYTES)
    assert path.stat().st_size == DEFAULT_MIN_BYTES

    verdict = classify(_expect(path), exit_code=0)

    assert verdict.state is State.SEVERED
    assert verdict.state is not State.DONE


# --------------------------------------------------------------------------------------
# gate 6: the sentinel, pinned in BYTES
# --------------------------------------------------------------------------------------
def test_artifact_present_but_no_sentinel_is_not_done(tmp_path) -> None:
    path = tmp_path / "unit.out"
    path.write_bytes(b"y" * 4096)

    verdict = classify(_expect(path), exit_code=0)

    assert verdict.state is State.SEVERED
    assert verdict.state is not State.DONE


def test_sentinel_present_but_no_artifact_is_not_done(tmp_path) -> None:
    """The producer printed its completion marker but never landed the file."""
    exp = _expect(tmp_path / "never-written.out")

    verdict = classify(exp, exit_code=0, agent_self_report=_sentinel())

    assert verdict.state is State.SEVERED
    assert verdict.state is not State.DONE


def test_sentinel_outside_the_600_byte_tail_window_is_not_done(tmp_path) -> None:
    """A sentinel that has scrolled out of the required tail window does not count."""
    path = tmp_path / "unit.out"
    raw = b"x" * 2000 + _sentinel().encode("utf-8") + b"z" * 700
    path.write_bytes(raw)

    # self-proving: the sentinel really is outside the pinned window
    assert b"UNIT-COMPLETE" in raw
    assert b"UNIT-COMPLETE" not in raw[-_WINDOW:]

    verdict = classify(_expect(path), exit_code=0)

    assert verdict.state is State.SEVERED
    assert verdict.state is not State.DONE


def test_non_ascii_artifact_where_char_window_and_byte_window_disagree(
    tmp_path,
) -> None:
    """600 CHARACTERS and 600 BYTES are different measurements on non-ASCII.

    400 two-byte characters occupy 800 bytes: the sentinel lands INSIDE a 600-character
    window but OUTSIDE the 600-byte window. The C1 contract is pinned in BYTES, so this
    must NOT be DONE. A character-based implementation would wrongly return DONE.
    """
    text = "x" * 2000 + _sentinel() + ("é" * 400)
    raw = text.encode("utf-8")
    path = tmp_path / "unit.out"
    path.write_bytes(raw)

    # self-proving fixture: the two windows genuinely disagree
    assert "UNIT-COMPLETE" in text[-_WINDOW:], "char window should find it"
    assert b"UNIT-COMPLETE" not in raw[-_WINDOW:], "byte window must not"

    verdict = classify(_expect(path), exit_code=0)

    assert verdict.state is State.SEVERED, "the BYTE window is authoritative"
    assert verdict.state is not State.DONE


# --------------------------------------------------------------------------------------
# gates 4/5: identity + input provenance
# --------------------------------------------------------------------------------------
def test_wrong_logical_unit_id_is_quarantined_not_done(tmp_path) -> None:
    """A complete artifact belonging to a DIFFERENT unit is contamination, not success."""
    path = _good_artifact(tmp_path, uid="U-999")

    verdict = classify(_expect(path, uid=UID), exit_code=0)

    assert verdict.state is State.QUARANTINED
    assert verdict.state is not State.DONE
    assert verdict.state is not State.FAILED
    assert verdict.logical_unit_id == "U-999"


def test_stale_input_bundle_hash_is_quarantined_not_done(tmp_path) -> None:
    """A complete artifact produced from SUPERSEDED inputs must not satisfy this unit."""
    path = _good_artifact(tmp_path, bundle=OTHER_BUNDLE)

    verdict = classify(_expect(path, bundle=BUNDLE), exit_code=0)

    assert verdict.state is State.QUARANTINED
    assert verdict.state is not State.DONE
    assert verdict.input_bundle_hash == OTHER_BUNDLE


def test_duplicate_attempt_result_is_idempotent_or_quarantined(tmp_path) -> None:
    """Re-observing the SAME attempt is a no-op; a second attempt from DIFFERENT inputs
    claiming the same logical unit is contamination."""
    path = _good_artifact(tmp_path)
    exp = _expect(path)

    first = classify(exp, exit_code=0)
    assert first.state is State.DONE

    # same bundle observed twice -> idempotent, still DONE, not double-counted
    again = classify(exp, exit_code=0, prior=first)
    assert again.state is State.DONE
    assert again.signals.get("duplicate_attempt") is True

    # a prior DONE recorded against a DIFFERENT bundle -> quarantine
    conflicting = Verdict(
        state=State.DONE,
        reason="earlier attempt",
        logical_unit_id=UID,
        input_bundle_hash=OTHER_BUNDLE,
    )
    clashed = classify(exp, exit_code=0, prior=conflicting)
    assert clashed.state is State.QUARANTINED
    assert clashed.state is not State.DONE


# --------------------------------------------------------------------------------------
# gate 7: event supersession
# --------------------------------------------------------------------------------------
def test_terminal_event_arriving_before_artifact_is_durable_is_unknown(
    tmp_path,
) -> None:
    """A success claim landed, the artifact has not. The process has not been observed to
    exit, so the artifact may still be flushing — refuse to guess in EITHER direction."""
    exp = _expect(tmp_path / "not-yet-durable.out")

    verdict = classify(
        exp,
        exit_code=None,
        events=[Event(kind=EventKind.SUCCESS_CLAIM, at=100.0)],
    )

    assert verdict.state is State.UNKNOWN
    assert verdict.state is not State.DONE
    assert verdict.state is not State.FAILED


def test_success_followed_by_failure_is_superseded(tmp_path) -> None:
    """A LATER failure event supersedes an otherwise-valid artifact (gate 7)."""
    path = _good_artifact(tmp_path)
    exp = _expect(path)
    durable_at = path.stat().st_mtime

    verdict = classify(
        exp,
        exit_code=0,
        events=[Event(kind=EventKind.FAILURE, at=durable_at + 60.0)],
    )

    assert verdict.state is State.FAILED
    assert verdict.state is not State.DONE
    assert verdict.signals.get("superseded_by") == EventKind.FAILURE


def test_failure_followed_by_a_valid_retry_is_done(tmp_path) -> None:
    """An EARLIER failure does not supersede an artifact durable after it."""
    path = _good_artifact(tmp_path)
    exp = _expect(path)
    durable_at = path.stat().st_mtime

    verdict = classify(
        exp,
        exit_code=0,
        events=[Event(kind=EventKind.FAILURE, at=durable_at - 600.0)],
    )

    assert verdict.state is State.DONE
    assert verdict.contract_version == CONTRACT_VERSION


def test_later_cancellation_supersedes_into_cancelled(tmp_path) -> None:
    path = _good_artifact(tmp_path)
    durable_at = path.stat().st_mtime

    verdict = classify(
        _expect(path),
        exit_code=0,
        events=[Event(kind=EventKind.CANCELLATION, at=durable_at + 5.0)],
    )

    assert verdict.state is State.CANCELLED
    assert verdict.state is not State.DONE


# --------------------------------------------------------------------------------------
# gate 3: declared format check
# --------------------------------------------------------------------------------------
def test_artifact_that_fails_its_declared_format_check_is_failed_not_done(
    tmp_path,
) -> None:
    """A complete, correctly-identified artifact that does not PARSE is FAILED — the unit
    reached a terminal state, it just produced garbage. That is not a severed stream."""
    path = _good_artifact(tmp_path)

    verdict = classify(
        _expect(path, format_check=lambda _raw: False),
        exit_code=0,
    )

    assert verdict.state is State.FAILED
    assert verdict.state is not State.DONE
    assert verdict.state is not State.SEVERED


def test_a_passing_format_check_falls_through_to_the_remaining_gates(tmp_path) -> None:
    """Both-states control for gate 3: passing the check must not SHORT-CIRCUIT to DONE.

    A format check that returns True only clears gate 3 — the sentinel, identity and
    provenance gates still have to be applied. The pairing matters: the FAILED case
    above proves the gate can reject, and this proves it does not become a bypass.
    """
    path = _good_artifact(tmp_path)

    verdict = classify(_expect(path, format_check=lambda _raw: True), exit_code=0)

    assert verdict.state is State.DONE
    assert verdict.signals.get("format_check") is True
    assert verdict.logical_unit_id == UID
    assert verdict.input_bundle_hash == BUNDLE

    # ...and a passing check does NOT rescue an artifact that fails a LATER gate.
    wrong_unit = _good_artifact(tmp_path, uid="U-999")
    still_bad = classify(
        _expect(wrong_unit, format_check=lambda _raw: True), exit_code=0
    )
    assert still_bad.state is State.QUARANTINED


def test_the_format_check_receives_the_WHOLE_artifact_not_the_tail_window(
    tmp_path,
) -> None:
    """Gate 3 parses the full byte stream; gate 6's 600-byte window is gate 6's alone.

    Handing a parser only the tail would make every format check on an artifact larger
    than the window a parse of a truncated document — which would either fail honestly
    or, worse, succeed on a fragment.
    """
    path = _good_artifact(tmp_path)
    full_size = path.stat().st_size
    assert full_size > SENTINEL_TAIL_BYTES, (
        "fixture must exceed the window, or this is vacuous"
    )

    seen: list[int] = []

    def _record(payload: bytes) -> bool:
        seen.append(len(payload))
        return True

    verdict = classify(_expect(path, format_check=_record), exit_code=0)

    assert verdict.state is State.DONE
    assert seen == [full_size], "the checker saw the entire artifact"


# --------------------------------------------------------------------------------------
# hard rule: a detector failure is NEVER an absence
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("fail_on", ["exists", "size", "read_tail", "mtime"])
def test_detector_raises_returns_unknown_never_failed_never_done(
    tmp_path, fail_on
) -> None:
    """Every probe seam: a broken detector yields UNKNOWN with the cause PRESERVED."""
    boom = OSError(5, "I/O error")
    exp = _expect(tmp_path / "unit.out")

    verdict = classify(exp, exit_code=0, probe=_RaisingProbe(boom, fail_on=fail_on))

    assert verdict.state is State.UNKNOWN
    assert verdict.state is not State.FAILED, (
        "a broken probe must never read as failure"
    )
    assert verdict.state is not State.DONE
    # the exception is carried, not swallowed into a boolean
    assert verdict.signals.get("detector_error") is not None
    assert "I/O error" in str(verdict.signals["detector_error"])


def test_format_check_that_raises_is_unknown_not_failed(tmp_path) -> None:
    """A format check that BLOWS UP is a detector failure; returning False is a verdict."""
    path = _good_artifact(tmp_path)

    def _explode(_raw: bytes) -> bool:
        raise ValueError("parser crashed")

    verdict = classify(_expect(path, format_check=_explode), exit_code=0)

    assert verdict.state is State.UNKNOWN
    assert verdict.state is not State.FAILED
    assert verdict.state is not State.DONE
    assert "parser crashed" in str(verdict.signals.get("detector_error"))


# --------------------------------------------------------------------------------------
# gate 1: what an ABSENT artifact resolves to depends on the surrounding evidence
#
# Each branch below is a DIFFERENT terminal state for the same missing file. Collapsing
# any pair of them would erase the distinction the contract exists to draw: "cancelled"
# is not "failed", and "exited non-zero" is not "exited clean but produced nothing".
# --------------------------------------------------------------------------------------
def test_cancelled_before_any_artifact_is_cancelled_not_severed(tmp_path) -> None:
    """A cancellation with nothing on disk is CANCELLED — the unit was stopped, not broken."""
    exp = _expect(tmp_path / "never-written.out")

    verdict = classify(
        exp,
        exit_code=0,
        events=[Event(kind=EventKind.CANCELLATION, at=100.0)],
    )

    assert verdict.state is State.CANCELLED
    assert verdict.state is not State.SEVERED, "a stopped unit is not a severed stream"
    assert verdict.state is not State.FAILED
    assert verdict.state is not State.DONE
    assert verdict.signals.get("artifact_exists") is False


def test_failure_event_with_no_artifact_is_failed_not_severed(tmp_path) -> None:
    """An explicit failure event outranks the exit code: FAILED, not SEVERED."""
    exp = _expect(tmp_path / "never-written.out")

    verdict = classify(
        exp,
        exit_code=0,
        events=[Event(kind=EventKind.FAILURE, at=100.0, detail="worker raised")],
    )

    assert verdict.state is State.FAILED
    assert verdict.state is not State.SEVERED
    assert verdict.state is not State.DONE


def test_cancellation_outranks_a_failure_event_when_no_artifact_exists(
    tmp_path,
) -> None:
    """Both events present: cancellation is checked FIRST and wins.

    This pins the precedence rather than leaving it to be rediscovered — a unit the
    operator stopped must not be reported as a unit that broke.
    """
    exp = _expect(tmp_path / "never-written.out")

    verdict = classify(
        exp,
        exit_code=1,
        events=[
            Event(kind=EventKind.FAILURE, at=100.0),
            Event(kind=EventKind.CANCELLATION, at=101.0),
        ],
    )

    assert verdict.state is State.CANCELLED
    assert verdict.state is not State.FAILED


def test_nonzero_exit_with_no_artifact_is_failed_not_severed(tmp_path) -> None:
    """Exit 1 and nothing on disk: the unit terminated non-successfully.

    Contrast with ``test_exit_zero_with_no_artifact_is_severed_not_done`` — the SAME
    missing artifact is SEVERED at exit 0 and FAILED at exit 1, because a clean exit that
    produced nothing is a lost stream while a dirty one is a reported failure.
    """
    exp = _expect(tmp_path / "never-written.out")

    verdict = classify(exp, exit_code=1)

    assert verdict.state is State.FAILED
    assert verdict.state is not State.SEVERED
    assert verdict.state is not State.DONE
    assert "exit=1" in verdict.reason


def test_cancelled_with_a_partial_artifact_is_cancelled_not_severed(tmp_path) -> None:
    """Gate 2 + cancellation: a truncated artifact from a STOPPED unit is CANCELLED.

    Without the cancellation this is SEVERED (see the 1023-byte test); the event is what
    explains the truncation, so the verdict must carry that explanation.
    """
    path = tmp_path / "unit.out"
    path.write_bytes(b"x" * 32)
    assert path.stat().st_size < DEFAULT_MIN_BYTES

    verdict = classify(
        _expect(path),
        exit_code=0,
        events=[Event(kind=EventKind.CANCELLATION, at=100.0)],
    )

    assert verdict.state is State.CANCELLED
    assert verdict.state is not State.SEVERED
    assert verdict.state is not State.DONE
    assert verdict.artifact_bytes == 32


def test_cancelled_before_the_sentinel_is_cancelled_not_severed(tmp_path) -> None:
    """Gate 6 + cancellation: a big-enough artifact stopped before its completion marker.

    The size gate passes and the format gate is not declared, so the ONLY thing missing is
    the sentinel — and a cancellation event explains why it never arrived.
    """
    path = tmp_path / "unit.out"
    path.write_bytes(b"y" * 4096)
    assert b"UNIT-COMPLETE" not in path.read_bytes()

    verdict = classify(
        _expect(path),
        exit_code=0,
        events=[Event(kind=EventKind.CANCELLATION, at=100.0)],
    )

    assert verdict.state is State.CANCELLED
    assert verdict.state is not State.SEVERED
    assert verdict.state is not State.DONE
    assert verdict.artifact_bytes == 4096


# --------------------------------------------------------------------------------------
# Verdict's own surface: the two accessors a caller actually branches and logs on
# --------------------------------------------------------------------------------------
def test_is_done_tracks_the_state_and_is_true_only_for_done(tmp_path) -> None:
    """``is_done`` is the caller's branch point; it must not be true for any near-miss."""
    done = classify(_expect(_good_artifact(tmp_path)), exit_code=0)
    assert done.state is State.DONE
    assert done.is_done is True

    severed = classify(_expect(tmp_path / "never-written.out"), exit_code=0)
    assert severed.state is State.SEVERED
    assert severed.is_done is False

    # every non-DONE state reads false — including the two that are not failures
    for state in (
        State.FAILED,
        State.SEVERED,
        State.UNKNOWN,
        State.CANCELLED,
        State.QUARANTINED,
    ):
        assert Verdict(state=state, reason="x").is_done is False


def test_str_carries_the_state_and_the_contract_version(tmp_path) -> None:
    """A verdict logged as a bare string must still name WHICH ruleset produced it.

    This is the whole point of stamping ``contract_version``: a line in a log that says
    only ``DONE`` is unreadable once two rulesets coexist during a migration.
    """
    verdict = classify(_expect(_good_artifact(tmp_path)), exit_code=0)

    rendered = str(verdict)

    assert rendered.startswith("DONE")
    assert f"[{CONTRACT_VERSION}]" in rendered
    assert verdict.reason in rendered
