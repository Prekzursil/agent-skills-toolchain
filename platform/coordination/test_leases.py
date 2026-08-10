"""File leases: part-wise containment, fail-closed conflict detection, and the sibling control."""

from __future__ import annotations

from pathlib import Path

import pytest

from coordination.errors import LeaseConflict, PathOutsideRoot
from coordination.leases import (
    DEFAULT_LEASE_TTL,
    Lease,
    LeaseMode,
    LeaseOutcome,
    acquire_lease,
    detect_conflicts,
    normalize_lease_path,
    overlaps,
    path_parts,
    release_leases,
    renew_lease,
    require_lease,
)
from coordination.session import DEFAULT_HEARTBEAT_TTL, register_session
from coordination.simclock import SimClock
from coordination.store import Store


def _live(store: Store, sid: str):
    return register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id=sid,
    )


def _dead(store: Store, sid: str):
    return register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id=sid,
        hold_lock=False,
    )


# --------------------------------------------------------------------- containment algebra


def test_directory_contains_its_files() -> None:
    assert overlaps("dir", "dir/file.py") is True
    assert overlaps("dir/file.py", "dir") is True
    assert overlaps("dir/sub", "dir/sub/deep/x.py") is True


def test_sibling_prefix_is_not_containment() -> None:
    """THE negative control. ``str.startswith`` reports ``dir`` as containing ``dir-sibling``.

    This estate paid for that exact bug twice (a StartsWith backup guard and an ensure_within
    sibling). A regression to a prefix test turns this red instead of silently widening every
    lease to cover its neighbours.
    """
    assert overlaps("dir", "dir-sibling") is False
    assert overlaps("dir", "dirty/file.py") is False
    assert overlaps("a/b", "a/bb") is False
    assert "dir-sibling".startswith("dir"), (
        "the wrong algorithm really would match here"
    )


def test_unrelated_paths_do_not_overlap() -> None:
    assert overlaps("a/b.py", "c/d.py") is False


def test_root_lease_covers_everything() -> None:
    assert path_parts(".") == ()
    assert overlaps(".", "anything/at/all.py") is True


def test_identical_paths_overlap() -> None:
    assert overlaps("x/y.py", "x/y.py") is True


# ------------------------------------------------------------------------- normalisation


def test_relative_and_absolute_forms_normalise_together(tmp_path: Path) -> None:
    a = normalize_lease_path(tmp_path, "sub/file.py")
    b = normalize_lease_path(tmp_path, tmp_path / "sub" / "file.py")
    assert a == b == "sub/file.py"


def test_backslash_and_case_fold_on_windows(tmp_path: Path) -> None:
    """Two sessions writing ``a/B.py`` and ``A\\b.py`` must collide, not coexist."""
    a = normalize_lease_path(tmp_path, "sub/File.PY")
    b = normalize_lease_path(tmp_path, "sub\\file.py")
    assert a == b


def test_escape_via_dotdot_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathOutsideRoot, match="not under the declared root"):
        normalize_lease_path(tmp_path / "root", "../outside/x.py")


def test_sibling_root_is_rejected_not_treated_as_child(tmp_path: Path) -> None:
    """The normalisation half of the sibling bug: ``root-sibling`` is not under ``root``."""
    (tmp_path / "root").mkdir()
    (tmp_path / "root-sibling").mkdir()
    with pytest.raises(PathOutsideRoot):
        normalize_lease_path(tmp_path / "root", tmp_path / "root-sibling" / "x.py")


# ------------------------------------------------------------------------------ acquisition


def test_exclusive_lease_is_granted_then_conflicts(
    store: Store, tmp_path: Path
) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        first = acquire_lease(store, session_id="s1", paths=["a/b.py"], root=tmp_path)
        assert first.outcome is LeaseOutcome.GRANTED
        second = acquire_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
        assert second.outcome is LeaseOutcome.CONFLICT
        assert second.lease is None
        assert second.conflicts[0].session_b == "s1"
        assert second.sentinel_line.startswith("FAILED:lease")
    finally:
        if lock:
            lock.release()


def test_conflict_writes_nothing(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        acquire_lease(store, session_id="s1", paths=["a"], root=tmp_path)
        before = sorted(p.name for p in store.dir_for("leases").iterdir())
        acquire_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
        assert sorted(p.name for p in store.dir_for("leases").iterdir()) == before
    finally:
        if lock:
            lock.release()


def test_shared_readers_coexist(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        a = acquire_lease(
            store,
            session_id="s1",
            paths=["a/b.py"],
            root=tmp_path,
            mode=LeaseMode.SHARED,
        )
        b = acquire_lease(
            store,
            session_id="s2",
            paths=["a/b.py"],
            root=tmp_path,
            mode=LeaseMode.SHARED,
        )
        assert a.granted and b.granted
    finally:
        if lock:
            lock.release()


def test_exclusive_excludes_a_shared_reader(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        acquire_lease(
            store,
            session_id="s1",
            paths=["a/b.py"],
            root=tmp_path,
            mode=LeaseMode.SHARED,
        )
        result = acquire_lease(
            store, session_id="s2", paths=["a"], root=tmp_path, mode=LeaseMode.EXCLUSIVE
        )
        assert result.outcome is LeaseOutcome.CONFLICT
    finally:
        if lock:
            lock.release()


def test_same_session_reacquiring_is_already_held(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        acquire_lease(store, session_id="s1", paths=["a"], root=tmp_path)
        again = acquire_lease(store, session_id="s1", paths=["a/b.py"], root=tmp_path)
        assert again.outcome is LeaseOutcome.ALREADY_HELD
        assert again.granted is True
    finally:
        if lock:
            lock.release()


def test_dead_holder_does_not_block(
    store: Store, tmp_path: Path, clock: SimClock
) -> None:
    _dead(store, "s1")
    acquire_lease(store, session_id="s1", paths=["a/b.py"], root=tmp_path)
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    _dead(store, "s2")
    result = acquire_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
    assert result.outcome is LeaseOutcome.GRANTED


def test_unverified_holder_DOES_block(store: Store, tmp_path: Path) -> None:
    """Fail closed. Granting over a session that may still be writing is the data-loss direction."""
    _dead(store, "s1")
    acquire_lease(store, session_id="s1", paths=["a/b.py"], root=tmp_path)
    result = acquire_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
    assert result.outcome is LeaseOutcome.CONFLICT
    assert "UNVERIFIED holders keep their leases" in result.conflicts[0].reason


def test_orphan_lease_with_no_session_row_blocks(store: Store, tmp_path: Path) -> None:
    acquire_lease(store, session_id="ghost", paths=["a/b.py"], root=tmp_path)
    result = acquire_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
    assert result.outcome is LeaseOutcome.CONFLICT


def test_expired_lease_does_not_block(
    store: Store, tmp_path: Path, clock: SimClock
) -> None:
    lock = _live(store, "s1")[1]
    try:
        acquire_lease(store, session_id="s1", paths=["a/b.py"], root=tmp_path, ttl=10)
        clock.advance(11)
        result = acquire_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
        assert result.outcome is LeaseOutcome.GRANTED
    finally:
        if lock:
            lock.release()


def test_renew_extends_expiry_and_counts(
    store: Store, tmp_path: Path, clock: SimClock
) -> None:
    lock = _live(store, "s1")[1]
    try:
        lease = acquire_lease(
            store, session_id="s1", paths=["a"], root=tmp_path, ttl=10
        ).lease
        assert lease is not None
        clock.advance(5)
        renewed = renew_lease(store, lease.lease_id, ttl=DEFAULT_LEASE_TTL)
        assert renewed.expires_at > lease.expires_at
        assert renewed.renew_seq == 1
    finally:
        if lock:
            lock.release()


def test_renew_unknown_lease_raises(store: Store) -> None:
    with pytest.raises(LeaseConflict, match="unknown lease"):
        renew_lease(store, "lease-nope")


def test_release_marks_rather_than_deletes(store: Store, tmp_path: Path) -> None:
    """History must survive: a deleted lease record makes a post-hoc audit blind."""
    lock = _live(store, "s1")[1]
    try:
        lease = acquire_lease(store, session_id="s1", paths=["a"], root=tmp_path).lease
        assert lease is not None
        assert release_leases(store, session_id="s1") == (lease.lease_id,)
        raw = store.read(store.path_for("leases", lease.lease_id))
        assert raw is not None and raw["released_at"] is not None
        assert release_leases(store, session_id="s1") == (), "release is idempotent"
    finally:
        if lock:
            lock.release()


def test_require_lease_raises_on_conflict(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        require_lease(store, session_id="s1", paths=["a"], root=tmp_path)
        with pytest.raises(LeaseConflict, match="FAILED:lease"):
            require_lease(store, session_id="s2", paths=["a/b.py"], root=tmp_path)
    finally:
        if lock:
            lock.release()


def test_empty_path_list_is_rejected(store: Store, tmp_path: Path) -> None:
    with pytest.raises(PathOutsideRoot, match="at least one path"):
        acquire_lease(store, session_id="s1", paths=[], root=tmp_path)


# ------------------------------------------------------------------ retrospective auditing


def test_detect_conflicts_finds_a_hand_corrupted_store(
    store: Store, tmp_path: Path
) -> None:
    """A prospective guard that is never audited is a guard nobody has measured.

    Two overlapping exclusive leases are written DIRECTLY, bypassing ``acquire_lease``, which is
    what a crash mid-recovery or a hand edit would leave behind.
    """
    lock1 = _live(store, "s1")[1]
    lock2 = _live(store, "s2")[1]
    try:
        for sid, lease_id, rel in (("s1", "L1", "pkg"), ("s2", "L2", "pkg/mod.py")):
            store.write_atomic(
                store.path_for("leases", lease_id),
                Lease(
                    lease_id=lease_id,
                    session_id=sid,
                    paths=(normalize_lease_path(tmp_path, rel),),
                    mode=LeaseMode.EXCLUSIVE,
                    acquired_at=store.clock(),
                    expires_at=store.clock() + 600,
                    root=str(tmp_path),
                ).to_dict(),
            )
        conflicts = detect_conflicts(store)
        assert len(conflicts) == 1
        assert {conflicts[0].session_a, conflicts[0].session_b} == {"s1", "s2"}
        assert "two in-force leases overlap" in conflicts[0].reason
    finally:
        for lock in (lock1, lock2):
            if lock:
                lock.release()


def test_detect_conflicts_is_clean_on_a_store_built_through_the_api(
    store: Store, tmp_path: Path
) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        acquire_lease(store, session_id="s1", paths=["a/one.py"], root=tmp_path)
        acquire_lease(store, session_id="s2", paths=["b/two.py"], root=tmp_path)
        assert detect_conflicts(store) == ()
    finally:
        if lock:
            lock.release()


def test_detect_conflicts_ignores_shared_pairs(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        acquire_lease(
            store, session_id="s1", paths=["a"], root=tmp_path, mode=LeaseMode.SHARED
        )
        acquire_lease(
            store,
            session_id="s2",
            paths=["a/b.py"],
            root=tmp_path,
            mode=LeaseMode.SHARED,
        )
        assert detect_conflicts(store) == ()
    finally:
        if lock:
            lock.release()


def test_lease_round_trips(store: Store, tmp_path: Path) -> None:
    lock = _live(store, "s1")[1]
    try:
        lease = acquire_lease(store, session_id="s1", paths=["a"], root=tmp_path).lease
        assert lease is not None
        assert Lease.from_dict(lease.to_dict()) == lease
    finally:
        if lock:
            lock.release()
