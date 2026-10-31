"""Two-signal stall tests for ``monitorcore.agent_state`` (the L1-stall regression).

A stall is an INFERENCE and may be reported only when TWO mechanically-independent
signals agree — a stale file mtime (filesystem) AND a frozen content fingerprint across
``>= 2`` polls (content). A terminal transcript is a FACT and outranks both, at any age.

The acceptance test is :func:`test_eleven_hour_old_finished_agent_is_done_never_stalled`:
it reproduces the MEASURED live defect where a long-finished agent was reported as a live
stall from mtime age alone. Its fixture is the real shape of a transcript observed on this
box (an assistant turn that declared ``stop_reason="end_turn"`` whose last content block is
a ``server_tool_use``), not an invented one.
"""

from __future__ import annotations

import json
import os

import pytest

from monitorcore import agent_state as st

ELEVEN_HOURS = 11 * 3600.0


@pytest.fixture(autouse=True)
def _clear_state():
    st.reset_state()
    yield
    st.reset_state()


def _write(path, *entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return str(path)


def _set_age(path, now, age):
    """Set the file's mtime so ``now - mtime == age``."""
    os.utime(path, (now, now - age))


def _finished_turn(text="all done"):
    """An assistant turn the model itself declared complete (``stop_reason='end_turn'``).

    The trailing content block is a ``server_tool_use``, so the pre-existing
    assistant-``text``-tail signal does NOT fire — this is the measured shape that the
    single-signal oracle mislabelled ``stalled``.
    """
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [
                {"type": "server_tool_use", "name": "web_search", "input": {}},
            ],
        },
    }


def _unfinished_turn(name="Bash"):
    """An assistant turn cut off mid-tool-call — NO terminal evidence of any kind."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "name": name}],
        },
    }


# ═════════════ THE ACCEPTANCE TEST (the measured live defect) ═════════════
def test_eleven_hour_old_finished_agent_is_done_never_stalled(tmp_path):
    """An 11-hour-old transcript carrying terminal evidence is ``done``, never ``stalled``.

    This is the regression: file mtime ALONE cannot distinguish a stalled agent from a
    long-FINISHED one, so age must never by itself produce ``stalled`` when the transcript
    says the agent finished.
    """
    p = _write(tmp_path / "finished.jsonl", _unfinished_turn(), _finished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)  # ~66x the 600s dead-man window

    # Poll it repeatedly: the content is frozen forever, yet it is terminal, so no number
    # of frozen polls may ever promote it to a stall.
    for _ in range(4):
        state, age = st.agent_status(p, now=now)
        assert state == "done", f"terminal transcript reported {state!r}"
        assert age == ELEVEN_HOURS


# ═════════════ classify_status — the PURE decision ═════════════
def _ev(**kw):
    """A :class:`StatusEvidence` with the module defaults, overridden by ``kw``."""
    base = dict(
        age=700.0,
        fresh=st.FRESH,
        stall=st.STALL,
        terminal=False,
        fingerprint="fp",
        previous="fp",
    )
    base.update(kw)
    return st.StatusEvidence(**base)


def test_classify_fresh_is_running():
    # freshness is decided before any content is consulted, so a frozen fingerprint and
    # terminal evidence must both lose to a just-touched file.
    assert st.classify_status(_ev(age=5.0, terminal=True)) == "running"


def test_classify_terminal_is_done_at_any_age():
    assert st.classify_status(_ev(age=ELEVEN_HOURS, terminal=True)) == "done"


def test_classify_terminal_outranks_a_corroborated_freeze():
    """Both stall signals present AND terminal ⇒ done. Terminal is a fact; a stall is not."""
    ev = _ev(age=ELEVEN_HOURS, terminal=True, fingerprint="fp", previous="fp")
    assert ev.content_frozen is True
    assert st.classify_status(ev) == "done"


def test_classify_stalled_needs_both_signals():
    ev = _ev(age=700.0, fingerprint="fp", previous="fp")
    assert ev.content_frozen is True
    assert st.classify_status(ev) == "stalled"


def test_classify_stale_mtime_alone_is_working_not_stalled():
    """Signal 1 only (never-seen content): the honest answer is ``working``."""
    ev = _ev(age=ELEVEN_HOURS, fingerprint="fp", previous=None)
    assert ev.content_frozen is False
    assert st.classify_status(ev) == "working"


def test_classify_changed_fingerprint_is_working_not_stalled():
    """A content change breaks the freeze even when the mtime is stale."""
    ev = _ev(age=ELEVEN_HOURS, fingerprint="new", previous="old")
    assert ev.content_frozen is False
    assert st.classify_status(ev) == "working"


def test_classify_frozen_content_with_fresh_mtime_is_working():
    """Signal 2 only (mtime inside the dead-man window): not a stall either."""
    ev = _ev(age=100.0, fingerprint="fp", previous="fp")  # FRESH < 100 < STALL
    assert ev.content_frozen is True
    assert st.classify_status(ev) == "working"


def test_content_frozen_is_false_when_fingerprint_is_missing():
    """An unreadable poll carries no content signal, so it can never corroborate a stall."""
    assert _ev(fingerprint=None, previous=None).content_frozen is False


# ═════════════ tail_evidence / read_evidence — terminal signals ═════════════
def test_tail_evidence_end_turn_is_terminal_without_a_text_tail():
    ev = st.tail_evidence(json.dumps(_finished_turn()) + "\n")
    assert ev.last_type == "server_tool_use"
    assert ev.terminal is True


def test_tail_evidence_tool_use_stop_reason_is_not_terminal():
    ev = st.tail_evidence(json.dumps(_unfinished_turn()) + "\n")
    assert ev.last_type == "tool_use"
    assert ev.terminal is False


def test_tail_evidence_assistant_text_tail_is_still_terminal():
    """The pre-existing signal is preserved: a trailing assistant text turn is done."""
    rec = {"message": {"role": "assistant", "content": [{"type": "text", "text": "x"}]}}
    ev = st.tail_evidence(json.dumps(rec) + "\n")
    assert ev.terminal is True


def test_tail_evidence_no_assistant_record_is_not_terminal():
    """A transcript with only user records has no end-of-turn declaration to read."""
    rec = {"message": {"role": "user", "content": [{"type": "tool_result"}]}}
    ev = st.tail_evidence(json.dumps(rec) + "\n")
    assert ev.last_type == "tool_result"
    assert ev.terminal is False


def test_tail_evidence_roleless_record_reports_no_role():
    """A content-bearing record with no ``role`` yields a typed ``None``, not a raw object."""
    ev = st.tail_evidence('{"message": {"content": [{"type": "text"}]}}\n')
    assert (ev.last_type, ev.role) == ("text", None)
    assert ev.terminal is False  # no role -> not an assistant text tail, no stop_reason


def test_tail_evidence_non_string_block_type_is_reported_as_none():
    """A malformed block whose ``type`` is not a string must not leak a non-``str``."""
    ev = st.tail_evidence('{"message": {"role": "user", "content": [{"type": 7}]}}\n')
    assert (ev.last_type, ev.role) == (None, "user")


def test_tail_evidence_fingerprint_tracks_content_not_length_only():
    a = st.tail_evidence('{"message": {"role": "user", "content": "aaa"}}\n')
    b = st.tail_evidence('{"message": {"role": "user", "content": "bbb"}}\n')
    again = st.tail_evidence('{"message": {"role": "user", "content": "aaa"}}\n')
    assert a.fingerprint != b.fingerprint  # same length, different bytes
    assert a.fingerprint == again.fingerprint  # stable across calls


def test_read_evidence_unreadable_carries_no_signal():
    ev = st.read_evidence("/no/such/file.jsonl")
    assert ev == st.TailEvidence(
        last_type=None, role=None, terminal=False, fingerprint=None
    )


# ═════════════ agent_status — the wired behaviour ═════════════
def test_agent_status_frozen_across_two_polls_is_stalled(tmp_path):
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)  # 1 signal
    assert st.agent_status(p, now=now) == ("stalled", ELEVEN_HOURS)  # 2 signals


def test_agent_status_changed_content_is_never_stalled(tmp_path):
    """A stale mtime plus MOVING content is not a freeze — the file is being written."""
    path = tmp_path / "busy.jsonl"
    p = _write(path, _unfinished_turn("Bash"))
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)
    # content advances while the mtime is held stale -> the freeze counter must reset
    _write(path, _unfinished_turn("Bash"), _unfinished_turn("Read"))
    _set_age(p, now, age=ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)


def test_agent_status_uses_an_injected_fingerprint_memory(tmp_path):
    """The cross-poll memory is injectable, so a caller can scope it per board."""
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    mine: dict[str, str | None] = {}
    assert st.agent_status(p, now=now, fingerprints=mine) == ("working", ELEVEN_HOURS)
    assert list(mine) == [p]  # recorded there, not in the module default
    assert p not in st._FINGERPRINTS
    assert st.agent_status(p, now=now, fingerprints=mine) == ("stalled", ELEVEN_HOURS)


def test_agent_status_caller_supplied_terminal_evidence_beats_any_freeze(tmp_path):
    """The board can contribute the terminal evidence the transcript does not carry.

    Measured: 64 of the 66 long-finished transcripts the single-signal oracle mislabelled
    end mid-``tool_use``/``tool_result`` and carry NO end-of-turn evidence in their own
    bytes. ``terminal=True`` (from the manifest/journal ``done`` that ``bucket_agent``
    models) must therefore override any depth of content freeze.
    """
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    # without it: a corroborated stall by the second poll
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("stalled", ELEVEN_HOURS)
    # with it: done on every poll, however deep the freeze.
    # NOTE the ``reset_state`` below scopes this test to a CLEAN cache. That is a real
    # case, but on its own it MASKED a live defect — see the sibling
    # ``…_overrides_an_already_cached_stall``, which deliberately omits the reset.
    st.reset_state()
    for _ in range(3):
        assert st.agent_status(p, now=now, terminal=True) == ("done", ELEVEN_HOURS)


def test_caller_terminal_evidence_overrides_an_already_cached_stall(tmp_path):
    """``terminal=True`` must beat a stall ALREADY IN THE CACHE — no reset first.

    The natural polling order is: the monitor polls, infers a stall, and only THEN does the
    manifest/``Task``-result evidence arrive. Because a finished agent's mtime never moves
    again, a ``stalled`` cached before that moment can never be invalidated by mtime, so a
    cache short-circuit placed ahead of the ``terminal`` read makes the wrong verdict
    PERMANENT. Measured on the unfixed code: ``working → stalled → stalled → stalled``.

    Deliberately does NOT call :func:`reset_state` — the reset is exactly what hid this.
    """
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("stalled", ELEVEN_HOURS)
    assert st._STATUS_CACHE[p][1] == "stalled"  # the wrong verdict is now cached

    # Evidence arrives late. Every subsequent poll must answer ``done`` — the first by
    # recomputing past the stale cache, the rest from the CORRECTED cache entry.
    for _ in range(3):
        assert st.agent_status(p, now=now, terminal=True) == ("done", ELEVEN_HOURS)
    assert st._STATUS_CACHE[p][1] == "done"  # …and the entry was repaired, not bypassed


def test_a_cached_stall_is_recomputed_once_the_mtime_moves(tmp_path):
    """A cached verdict must not outlive the file it described (the mtime half).

    Guards the docstring's "any mtime movement invalidates that cache". Without the
    ``cached[0] == mtime`` half of the check, a woken-up agent stays ``stalled`` forever:
    ``--cov-branch`` scores the ``if`` OUTCOME, not each sub-condition, so mutating it to a
    bare ``if cached:`` otherwise leaves the suite green at 100%.
    """
    path = tmp_path / "wedged.jsonl"
    p = _write(path, _unfinished_turn("Bash"))
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)
    # the stall is cached against THIS mtime:
    assert st.agent_status(p, now=now) == ("stalled", ELEVEN_HOURS)

    # The agent wakes and appends, which moves the mtime. Hold the file STALE so the
    # freshness short-circuit cannot be what answers — the cache check must be reached.
    _write(path, _unfinished_turn("Bash"), _unfinished_turn("Read"))
    woke = ELEVEN_HOURS - 1.0
    _set_age(path, now, age=woke)
    assert st.agent_status(p, now=now) == ("working", woke)


def test_an_mtime_move_alone_forces_a_re_read_even_when_content_is_identical(tmp_path):
    """The mtime axis in isolation: byte-identical content, moved mtime ⇒ still re-read.

    The sibling above moves mtime and content together (they always move together in the
    wild), so it cannot say WHICH one invalidated. Here the content is unchanged, so the
    recomputed verdict equals the cached one and the return value proves nothing — the
    observable is instead the injected fingerprint memory, which is written ONLY on the
    recompute path (``agent_state.agent_status`` records ``seen[path]`` after reading).
    An empty dict afterwards means the cache short-circuited and the file was never read.
    """
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    shared: dict[str, str | None] = {}
    assert st.agent_status(p, now=now, fingerprints=shared) == ("working", ELEVEN_HOURS)
    assert st.agent_status(p, now=now, fingerprints=shared) == ("stalled", ELEVEN_HOURS)

    os.utime(p, (now, now - (ELEVEN_HOURS - 1.0)))  # mtime moves; bytes do not
    # a FRESH memory, so non-empty afterwards ⇔ the file really was re-read:
    probe: dict[str, str | None] = {}
    assert st.agent_status(p, now=now, fingerprints=probe) == (
        "working",  # a fresh memory has no previous fingerprint ⇒ one signal only
        ELEVEN_HOURS - 1.0,
    )
    assert list(probe) == [p], "cache hit: the moved mtime did not invalidate"


def test_reset_state_clears_both_caches(tmp_path):
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    st.agent_status(p, now=now)
    st.agent_status(p, now=now)
    assert st._STATUS_CACHE and st._FINGERPRINTS
    st.reset_state()
    assert not st._STATUS_CACHE and not st._FINGERPRINTS
    # …and the freeze counter genuinely restarted: one signal again, so working
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)


# ═════════════ MUTATION GUARD (both-states) ═════════════
def _single_signal_gate(signals, **_kw):
    """The OLD, refuted gate: mtime staleness alone decides. The mutant under test."""
    return signals.mtime_stale


def test_mutating_the_gate_to_single_signal_breaks_the_stall_verdict(
    tmp_path, monkeypatch
):
    """Both-states proof that the two-signal gate is load-bearing in the SHIPPED path.

    With the real gate, the first poll of a silent transcript is ``working``. Swap the
    collaborator for the single-signal form and the very same call flips to ``stalled`` —
    so if the gate were ever weakened, ``test_classify_stale_mtime_alone_is_working…`` and
    ``test_agent_status_frozen_across_two_polls_is_stalled`` go red rather than staying
    quietly green.
    """
    p = _write(tmp_path / "wedged.jsonl", _unfinished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    assert st.agent_status(p, now=now) == ("working", ELEVEN_HOURS)

    st.reset_state()
    monkeypatch.setattr(st, "is_corroborated_stall", _single_signal_gate)
    assert st.agent_status(p, now=now) == ("stalled", ELEVEN_HOURS)


def test_terminal_preemption_is_independent_of_the_stall_gate(tmp_path, monkeypatch):
    """Terminal evidence must win even if the stall gate is maximally trigger-happy."""
    p = _write(tmp_path / "finished.jsonl", _finished_turn())
    now = 1_000_000.0
    _set_age(p, now, age=ELEVEN_HOURS)
    monkeypatch.setattr(st, "is_corroborated_stall", _single_signal_gate)
    assert st.agent_status(p, now=now) == ("done", ELEVEN_HOURS)
