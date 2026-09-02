"""Session discovery and the two-signal liveness AND-gate."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from coordination.errors import StoreCorrupt
from coordination.oslock import LockOutcome
from coordination.session import (
    DEFAULT_HEARTBEAT_TTL,
    Liveness,
    SessionRecord,
    classify,
    close_session,
    discover,
    heartbeat,
    lock_path_for,
    register_session,
)
from coordination.simclock import SimClock
from coordination.store import Store

CHILD = Path(__file__).resolve().parent / "lock_probe_child.py"


def _register(store: Store, sid: str, vendor: str = "anthropic", **kw):
    return register_session(
        store,
        vendor=vendor,
        adapter_id=kw.pop("adapter_id", "claude-code"),
        tool=kw.pop("tool", "claude-code"),
        session_id=sid,
        **kw,
    )


# ------------------------------------------------------------------ the four liveness rows


def test_fresh_heartbeat_plus_held_lock_is_live(store: Store, clock: SimClock) -> None:
    record, lock = _register(store, "s-live")
    try:
        assert lock is not None and lock.acquired
        view = classify(store, record)
        assert view.liveness is Liveness.LIVE
        assert (
            view.lock_probe.outcome is LockOutcome.HELD_BY_OTHER or view.heartbeat_fresh
        )
    finally:
        if lock:
            lock.release()


def test_stale_heartbeat_plus_free_lock_is_dead(store: Store, clock: SimClock) -> None:
    """Both signals agree. This is the ONLY combination that authorises automatic recovery."""
    record, _ = _register(store, "s-dead", hold_lock=False)
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    view = classify(store, record)
    assert view.liveness is Liveness.DEAD
    assert "both signals agree" in view.reason
    assert view.needs_recovery is True


def test_fresh_heartbeat_plus_free_lock_is_unverified(
    store: Store, clock: SimClock
) -> None:
    record, _ = _register(store, "s-just-died", hold_lock=False)
    view = classify(store, record)
    assert view.liveness is Liveness.UNVERIFIED
    assert "signals disagree" in view.reason
    assert view.blocks_automatic_recovery is True


def test_stale_heartbeat_plus_held_lock_is_unverified_and_never_called_hung(
    store: Store, clock: SimClock
) -> None:
    """The rule that a stall cannot be proven from timestamps, encoded as a verdict.

    A process that holds its lock is running. Claiming it is STUCK would need orchestrator state
    a store scan does not contain, so the verdict is UNVERIFIED and the reason says exactly that.
    """
    record, lock = _register(store, "s-quiet")
    try:
        clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
        view = classify(store, record)
        assert view.liveness is Liveness.UNVERIFIED
        assert "NOT reported as hung" in view.reason
        assert "hung" not in view.liveness.value.lower()
    finally:
        if lock:
            lock.release()


def test_missing_lock_file_is_unverified_not_dead(
    store: Store, clock: SimClock
) -> None:
    """One signal is not evidence. No second signal => no reaping."""
    record, _ = _register(store, "s-nolock", hold_lock=False)
    lock_path_for(store, "s-nolock").unlink()
    clock.advance(DEFAULT_HEARTBEAT_TTL + 100)
    view = classify(store, record)
    assert view.liveness is Liveness.UNVERIFIED
    assert "no second signal" in view.reason


def test_graceful_close_is_closed_not_dead(store: Store, clock: SimClock) -> None:
    _register(store, "s-closed", hold_lock=False)
    record = close_session(store, "s-closed")
    clock.advance(10_000)
    view = classify(store, record)
    assert view.liveness is Liveness.CLOSED
    assert view.needs_recovery is False


# --------------------------------------------------------------- both signals are declared


def test_session_view_serialises_both_signals(store: Store, clock: SimClock) -> None:
    """single-signal-verification rule 6: an undeclared source probe is zero signals, not one."""
    record, _ = _register(store, "s-sig", hold_lock=False)
    payload = classify(store, record).to_dict()
    assert set(payload["signals"]) == {"A_heartbeat", "B_oslock"}
    assert payload["signals"]["A_heartbeat"]["mechanism"].startswith("userspace")
    assert payload["signals"]["B_oslock"]["mechanism"].startswith("kernel")
    assert payload["reason"]


# ------------------------------------------------------------------------------- heartbeat


def test_heartbeat_advances_sequence_and_clock(store: Store, clock: SimClock) -> None:
    _register(store, "s-hb", hold_lock=False)
    clock.advance(30)
    first = heartbeat(store, "s-hb")
    clock.advance(30)
    second = heartbeat(store, "s-hb")
    assert (second.heartbeat_seq, second.heartbeat_at) > (
        first.heartbeat_seq,
        first.heartbeat_at,
    )


def test_heartbeat_revives_a_stale_session(store: Store, clock: SimClock) -> None:
    record, lock = _register(store, "s-revive")
    try:
        clock.advance(DEFAULT_HEARTBEAT_TTL + 5)
        assert classify(store, record).liveness is Liveness.UNVERIFIED
        refreshed = heartbeat(store, "s-revive")
        assert classify(store, refreshed).liveness is Liveness.LIVE
    finally:
        if lock:
            lock.release()


def test_heartbeat_for_unknown_session_raises(store: Store) -> None:
    with pytest.raises(StoreCorrupt, match="unregistered session"):
        heartbeat(store, "never-registered")


def test_close_for_unknown_session_raises(store: Store) -> None:
    with pytest.raises(StoreCorrupt, match="unregistered session"):
        close_session(store, "never-registered")


# ------------------------------------------------------------------------------- discovery


def test_discover_filters_by_canonical_vendor_not_raw_string(store: Store) -> None:
    """``discover(vendor="claude")`` must find a session registered as ``anthropic``.

    A raw string filter would miss it - the D1 failure at the session plane.
    """
    _register(store, "s-anthropic", vendor="anthropic", hold_lock=False)
    _register(
        store,
        "s-openai",
        vendor="codex",
        adapter_id="codex-cli",
        tool="codex-cli",
        hold_lock=False,
    )
    assert [v.session_id for v in discover(store, vendor="claude")] == ["s-anthropic"]
    assert [v.session_id for v in discover(store, vendor="OpenAI")] == ["s-openai"]
    assert len(discover(store)) == 2


def test_discover_with_unresolvable_vendor_returns_empty_not_everything(
    store: Store,
) -> None:
    """Fail closed: an unrecognised filter must not degrade to 'match all'."""
    _register(store, "s1", hold_lock=False)
    assert discover(store, vendor="not-a-vendor-at-all") == ()


def test_discover_filters_by_liveness(store: Store, clock: SimClock) -> None:
    _register(store, "s-dead", hold_lock=False)
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    _register(store, "s-fresh", hold_lock=False)
    dead = discover(store, liveness=[Liveness.DEAD])
    assert [v.session_id for v in dead] == ["s-dead"]


def test_discover_is_sorted_for_determinism(store: Store) -> None:
    for sid in ("s-c", "s-a", "s-b"):
        _register(store, sid, hold_lock=False)
    assert [v.session_id for v in discover(store)] == ["s-a", "s-b", "s-c"]


def test_session_id_with_path_separators_keeps_record_and_lock_together(
    store: Store,
) -> None:
    """A folded record name and an unfolded lock name would silently decouple the two signals."""
    record, _ = _register(store, "weird/id:1", hold_lock=False)
    assert store.read(store.path_for("sessions", record.session_id)) is not None
    assert lock_path_for(store, record.session_id).exists()
    assert classify(store, record).lock_probe.outcome is not LockOutcome.NOT_COMPUTABLE


def test_record_round_trips(store: Store) -> None:
    record, _ = _register(store, "s-rt", hold_lock=False)
    assert SessionRecord.from_dict(record.to_dict()) == record


def test_vendor_resolution_is_recorded_on_the_record(store: Store) -> None:
    record, _ = _register(store, "s-v", vendor="Claude Code", hold_lock=False)
    assert record.vendor_canonical == "anthropic"
    assert record.vendor_resolution == "KNOWN"


def test_real_crashed_process_is_classified_dead_end_to_end(
    store: Store, clock: SimClock
) -> None:
    """Integration: a REAL child holds the lock, is killed, and the classifier says DEAD.

    The in-process tests simulate the lock states; this one produces them for real, which is the
    mechanically independent check on the classifier itself.
    """
    record, _ = _register(store, "s-real", hold_lock=False)
    lock_file = lock_path_for(store, "s-real")
    ready = Path(store.root).parent / "ready.txt"
    proc = subprocess.Popen(
        [sys.executable, str(CHILD), str(lock_file), str(ready), "25"]
    )  # noqa: S603
    try:
        deadline = time.time() + 30
        while time.time() < deadline and not ready.exists():
            time.sleep(0.05)
        clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
        assert classify(store, record).liveness is Liveness.UNVERIFIED, (
            "held lock blocks reaping"
        )
    finally:
        proc.kill()
        proc.wait(timeout=30)
    assert classify(store, record).liveness is Liveness.DEAD


def test_a_session_from_another_host_is_unverified_never_reaped(
    store: Store, clock: SimClock
) -> None:
    """L-06: the OS lock is a fact about the LOCAL kernel only.

    Acquiring a lock file that lives on a share says nothing about a process on another machine,
    so a cross-host record has no admissible second signal and must never be classified DEAD.
    """
    record, _ = _register(store, "s-remote", hold_lock=False)
    remote = SessionRecord.from_dict({**record.to_dict(), "host": "some-other-box"})
    store.write_atomic(store.path_for("sessions", "s-remote"), remote.to_dict())
    clock.advance(DEFAULT_HEARTBEAT_TTL + 10_000)
    view = classify(store, remote)
    assert view.liveness is Liveness.UNVERIFIED
    assert "inadmissible" in view.reason
    assert view.needs_recovery is False
