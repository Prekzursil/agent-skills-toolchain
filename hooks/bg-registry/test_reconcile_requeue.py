#!/usr/bin/env python3
"""H-20 acceptance tests — SessionStart crash-reconcile requeue DECISION core.

Written test-first (TDD). The spec (07-OPTIONS-H.md H-20) proof requirement, verbatim:
  "hard-kill a 10-unit run, restart the session, and prove exactly the incomplete units
   requeue and the complete ones do not."
plus the named failure modes:
  * Windows pid-reuse mis-identifies a dead worker as alive -> compare pid AND start-time
    (the liveness callable owns that; a None/unknown liveness must NEVER be read as dead);
  * an auto-requeue storm re-freezes the box -> requeue is PROMPTED, not automatic, by default.

This module tests the PURE decision function only. Live wiring (SessionStart integration,
the actual re-enqueue, admission-gating through H-05/H-06) is a separate, owner-gated step.
"""

from __future__ import annotations

from reconcile_requeue import (
    DONE,
    IGNORE,
    LEAVE_ALIVE,
    REQUEUE,
    SALVAGE,
    UNKNOWN,
    classify_orphan,
    plan_requeue,
)

CUR = "current-session"
OLD = "dead-session"
NOW = 1_000_000.0


def _rec(**kw):
    base = {
        "id": "u1",
        "status": "running",
        "session": OLD,
        "pid": 4242,
        "pid_start": 111.0,
        "started_ts": NOW - 9999,  # old enough to judge
        "expected_artifact": "/out/u1.json",
        "attempt": 0,
    }
    base.update(kw)
    return base


# liveness/artifact stubs the caller would supply (H-10 dual-signal / H-01 predicate)
def _dead(pid, start):
    return False


def _alive(pid, start):
    return True


def _unknown(pid, start):
    return None  # detector could not decide — must not be read as "dead"


def _complete(_art):
    return True


def _severed(_art):
    return False  # exists but incomplete OR missing — caller distinguishes via has_artifact


class TestClassifyOrphan:
    def test_complete_artifact_is_marked_done_even_after_crash(self):
        d = classify_orphan(
            _rec(),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_complete,
            is_pid_alive=_dead,
        )
        assert d.action == DONE  # done_marker's rule applied post-crash

    def test_pid_dead_no_artifact_requeues(self):
        d = classify_orphan(
            _rec(expected_artifact=None),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
        )
        assert d.action == REQUEUE
        assert d.attempt == 1  # attempt incremented

    def test_pid_dead_severed_artifact_salvages(self):
        d = classify_orphan(
            _rec(),  # has an expected_artifact but it is incomplete
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
        )
        assert d.action == SALVAGE  # H-12 salvage/tail-continue before a blind re-run
        assert d.attempt == 1

    def test_pid_alive_is_left_alone(self):
        d = classify_orphan(
            _rec(),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_alive,
        )
        assert d.action == LEAVE_ALIVE

    def test_unknown_liveness_never_requeues(self):
        # rule 3 (a failed detector is not absence): an undecidable pid must NOT be treated
        # as dead and re-run -- that is how a live worker gets a duplicate.
        d = classify_orphan(
            _rec(),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_unknown,
        )
        assert d.action == UNKNOWN
        assert d.attempt == 0  # nothing re-enqueued on a broken detector

    def test_current_session_record_is_ignored(self):
        d = classify_orphan(
            _rec(session=CUR),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
        )
        assert d.action == IGNORE  # my own in-flight work is not an orphan

    def test_non_running_status_is_ignored(self):
        d = classify_orphan(
            _rec(status="done"),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_complete,
            is_pid_alive=_dead,
        )
        assert d.action == IGNORE

    def test_too_fresh_is_ignored(self):
        d = classify_orphan(
            _rec(started_ts=NOW - 5),  # inside the 120s grace window
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
            grace_s=120,
        )
        assert d.action == IGNORE  # too fresh to judge (races a just-launched sibling)

    def test_missing_pid_treated_as_dead_only_when_no_artifact(self):
        # No pid recorded at all + no artifact -> the worker never even registered a live
        # pid, so re-enqueue is safe. (is_pid_alive is not consulted when pid is falsy.)
        d = classify_orphan(
            _rec(pid=None, expected_artifact=None),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_alive,
        )
        assert d.action == REQUEUE

    def test_requeue_is_prompted_by_default(self):
        d = classify_orphan(
            _rec(expected_artifact=None),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
        )
        assert (
            d.prompted is True
        )  # spec default: prompted, not automatic, until H-05/H-06

    def test_auto_requeue_opt_in_flips_prompted_off(self):
        d = classify_orphan(
            _rec(expected_artifact=None),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
            auto_requeue=True,
        )
        assert d.prompted is False

    def test_non_requeue_actions_leave_attempt_unchanged(self):
        # Only REQUEUE/SALVAGE increment attempt; DONE / LEAVE_ALIVE / UNKNOWN must leave it
        # untouched. Closes the review's attempt-invariant gap: with only the +1 branches tested,
        # a mutation that also bumped attempt on the terminal actions survived under 100% coverage.
        r = _rec(attempt=2)
        done = classify_orphan(
            r,
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_complete,
            is_pid_alive=_dead,
        )
        alive = classify_orphan(
            r,
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_alive,
        )
        unknown = classify_orphan(
            r,
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_unknown,
        )
        assert (done.action, done.attempt) == (DONE, 2)
        assert (alive.action, alive.attempt) == (LEAVE_ALIVE, 2)
        assert (unknown.action, unknown.attempt) == (UNKNOWN, 2)


class TestPlanRequeue:
    def test_10_unit_hardkill_only_incomplete_requeue(self):
        # The spec's proof: 10 units, half complete, half severed with a dead pid.
        recs = []
        for i in range(10):
            complete = i % 2 == 0
            recs.append(
                _rec(
                    id=f"u{i}",
                    expected_artifact=(None if not complete else f"/out/u{i}"),
                )
            )

        # even i -> complete, odd i -> no artifact + dead pid
        def art_complete(art):
            return (
                art is not None
                and art.startswith("/out/u")
                and int(art.rsplit("u", 1)[1]) % 2 == 0
            )

        plan = plan_requeue(
            recs,
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=art_complete,
            is_pid_alive=_dead,
        )
        done = {d.record_id for d in plan if d.action == DONE}
        requeued = {d.record_id for d in plan if d.action == REQUEUE}
        assert done == {f"u{i}" for i in range(0, 10, 2)}  # exactly the complete ones
        assert requeued == {
            f"u{i}" for i in range(1, 10, 2)
        }  # exactly the incomplete ones
        # and NOTHING that was complete got re-enqueued
        assert done.isdisjoint(requeued)

    def test_non_numeric_attempt_and_started_ts_are_coerced_not_crash(self):
        # A corrupt record (non-numeric attempt/started_ts) must classify, not raise:
        # _as_float swallows the bad value to 0.0 (started_ts=0 -> grace guard skipped).
        d = classify_orphan(
            _rec(attempt="oops", started_ts="whenever", expected_artifact=None),
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
        )
        assert d.action == REQUEUE
        assert d.attempt == 1  # 0 (coerced) + 1

    def test_plan_skips_ignored(self):
        recs = [_rec(id="mine", session=CUR), _rec(id="dead", expected_artifact=None)]
        plan = plan_requeue(
            recs,
            current_sid=CUR,
            now=NOW,
            is_artifact_complete=_severed,
            is_pid_alive=_dead,
        )
        # IGNORE decisions are dropped from the actionable plan
        assert {d.record_id for d in plan} == {"dead"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
