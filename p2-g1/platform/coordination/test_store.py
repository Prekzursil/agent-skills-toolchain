"""The store's crash-safety and determinism properties."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coordination.errors import StoreCorrupt
from coordination.store import (
    RECORD_KINDS,
    Store,
    canonical_json,
    fingerprint_bytes,
    safe_record_name,
)
from coordination.simclock import SimClock


def _store(tmp_path: Path, clock: SimClock) -> Store:
    return Store(root=tmp_path / "coord", clock=clock).initialise()


def test_initialise_is_idempotent(tmp_path: Path, clock: SimClock) -> None:
    store = _store(tmp_path, clock)
    store.initialise()
    for kind in RECORD_KINDS:
        assert store.dir_for(kind).is_dir()


def test_unknown_record_kind_raises(tmp_path: Path, clock: SimClock) -> None:
    with pytest.raises(StoreCorrupt, match="unknown record kind"):
        _store(tmp_path, clock).dir_for("not-a-kind")


def test_create_exclusive_is_won_by_exactly_one_caller(
    tmp_path: Path, clock: SimClock
) -> None:
    """The atomic primitive behind work claims. A read-then-write check would let both win."""
    store = _store(tmp_path, clock)
    path = store.path_for("claims", "UNIT-0001")
    assert store.create_exclusive(path, {"who": "first"}) is True
    assert store.create_exclusive(path, {"who": "second"}) is False
    assert store.read(path) == {"who": "first"}, (
        "the loser must not overwrite the winner"
    )


def test_records_are_written_lf_only(tmp_path: Path, clock: SimClock) -> None:
    """Windows text mode would translate \\n to \\r\\n and make every digest platform-dependent."""
    store = _store(tmp_path, clock)
    path = store.path_for("sessions", "s1")
    store.write_atomic(path, {"a": 1})
    store.journal("evt", n=1)
    assert b"\r\n" not in path.read_bytes()
    assert b"\r\n" not in store.journal_path.read_bytes()


def test_write_atomic_leaves_no_temp_files(tmp_path: Path, clock: SimClock) -> None:
    store = _store(tmp_path, clock)
    path = store.path_for("claims", "U")
    store.write_atomic(path, {"v": 1})
    store.write_atomic(path, {"v": 2})
    assert store.read(path) == {"v": 2}
    leftovers = [p.name for p in path.parent.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_corrupt_record_raises_instead_of_reading_as_absent(
    tmp_path: Path, clock: SimClock
) -> None:
    """'unreadable claim' and 'no claim' must not collapse into one branch.

    If a truncated claim read as ``None``, a second session would see the unit as unclaimed and
    the same work would be dispatched twice.
    """
    store = _store(tmp_path, clock)
    path = store.path_for("claims", "U")
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StoreCorrupt, match="not valid JSON"):
        store.read(path)


def test_non_object_record_raises(tmp_path: Path, clock: SimClock) -> None:
    store = _store(tmp_path, clock)
    path = store.path_for("claims", "U")
    path.write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(StoreCorrupt, match="expected object"):
        store.read(path)


def test_absent_record_reads_as_none(tmp_path: Path, clock: SimClock) -> None:
    store = _store(tmp_path, clock)
    assert store.read(store.path_for("claims", "missing")) is None


def test_journal_is_append_only_and_ordered(tmp_path: Path, clock: SimClock) -> None:
    store = _store(tmp_path, clock)
    store.journal("first", i=1)
    clock.advance(5)
    store.journal("second", i=2)
    entries = store.journal_entries()
    assert [e["event"] for e in entries] == ["first", "second"]
    assert entries[0]["at"] < entries[1]["at"]


def test_corrupt_journal_line_raises_with_line_number(
    tmp_path: Path, clock: SimClock
) -> None:
    store = _store(tmp_path, clock)
    store.journal("ok")
    with open(store.journal_path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("{broken\n")
    with pytest.raises(StoreCorrupt, match=r"journal\.jsonl:2"):
        store.journal_entries()


def test_canonical_json_is_key_order_independent() -> None:
    a = canonical_json({"b": 1, "a": [3, {"z": 1, "y": 2}]})
    b = canonical_json({"a": [3, {"y": 2, "z": 1}].copy(), "b": 1})
    assert a == b
    assert fingerprint_bytes({"x": 1}) == fingerprint_bytes({"x": 1})


def test_canonical_json_preserves_non_ascii() -> None:
    assert "é" in canonical_json({"k": "é"})


def test_safe_record_name_cannot_collide_after_folding() -> None:
    """``a/b`` and ``a_b`` must not land in the same file."""
    assert safe_record_name("a/b") != safe_record_name("a_b")
    assert "/" not in safe_record_name("a/b")
    assert safe_record_name("plain-name") == "plain-name"


def test_safe_record_name_rejects_empty() -> None:
    with pytest.raises(StoreCorrupt, match="empty"):
        safe_record_name("")


def test_safe_record_name_strips_trailing_dot_and_space() -> None:
    folded = safe_record_name("weird. ")
    assert not folded.endswith((" ", "."))


def test_iter_records_is_sorted_and_skips_non_json(
    tmp_path: Path, clock: SimClock
) -> None:
    store = _store(tmp_path, clock)
    for name in ("c", "a", "b"):
        store.write_atomic(store.path_for("leases", name), {"n": name})
    (store.dir_for("leases") / "notes.txt").write_text("ignored", encoding="utf-8")
    assert [n for n, _ in store.iter_records("leases")] == ["a", "b", "c"]


def test_delete_reports_whether_it_removed_anything(
    tmp_path: Path, clock: SimClock
) -> None:
    store = _store(tmp_path, clock)
    path = store.path_for("claims", "U")
    store.write_atomic(path, {})
    assert store.delete(path) is True
    assert store.delete(path) is False


def test_record_round_trips_through_json(tmp_path: Path, clock: SimClock) -> None:
    store = _store(tmp_path, clock)
    payload = {"nested": {"list": [1, 2, {"deep": True}]}, "unicode": "ünïcødé"}
    path = store.path_for("handoffs", "h1")
    store.write_atomic(path, payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
