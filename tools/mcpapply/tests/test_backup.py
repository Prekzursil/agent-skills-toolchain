"""Backup naming, the printed restore command, and the injected clock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcpapply.backup import (
    BACKUP_SUFFIX,
    MAX_COLLISION_SUFFIXES,
    BackupRecord,
    backup_path,
    fixed_clock,
    make_clock,
    restore_command,
    utc_stamp,
)
from conftest import FIXED_NOW, STAMP


def test_the_stamp_is_utc_and_filesystem_safe():
    assert utc_stamp(FIXED_NOW) == STAMP
    assert ":" not in STAMP


def test_a_non_utc_clock_is_converted_not_recorded_verbatim():
    kolkata = timezone(timedelta(hours=5, minutes=30))
    assert utc_stamp(FIXED_NOW.astimezone(kolkata)) == STAMP


def test_a_naive_clock_is_treated_as_utc_rather_than_refused():
    """Refusing to back up because a clock lacked tzinfo is the wrong failure mode."""
    assert utc_stamp(datetime(2026, 7, 27, 3, 15, 0)) == STAMP


def test_the_backup_sits_beside_the_original_and_names_this_tool():
    target = Path("/home/o/.claude.json")
    sidecar = backup_path(target, FIXED_NOW)
    assert sidecar.parent == target.parent
    assert sidecar.name == f".claude.json.{BACKUP_SUFFIX}-{STAMP}.bak"


def test_the_restore_command_covers_both_shells_on_this_box():
    text = restore_command(
        (
            BackupRecord(source="a.json", backup="a.json.bak", size_bytes=3),
            BackupRecord(source="b.json", backup="b.json.bak", size_bytes=4),
        )
    )
    assert text.count("Copy-Item") == 2
    assert text.count("cp --") == 2
    assert "# PowerShell" in text and "# bash" in text


def test_no_backup_says_so_rather_than_printing_an_empty_command():
    assert restore_command(()) == "no backup was taken (nothing was written)"


def test_the_record_serialises_every_field():
    assert BackupRecord(source="s", backup="b", size_bytes=7).to_dict() == {
        "source": "s",
        "backup": "b",
        "size_bytes": 7,
    }


def test_the_production_clock_is_tz_aware_utc():
    moment = make_clock()()
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


def test_a_fixed_clock_returns_the_same_instant_every_call():
    clock = fixed_clock(FIXED_NOW)
    assert clock() == clock() == FIXED_NOW


# --------------------------------------------------------------------------
# A backup must never overwrite an earlier backup
# --------------------------------------------------------------------------


def test_a_taken_name_is_never_reused_so_an_earlier_backup_survives():
    """Two writes in the SAME SECOND must not land on the same sidecar.

    Regression: the GUI froze one ``datetime`` for its whole process, so every apply
    after the first overwrote the sidecar the previous apply's printed restore command
    pointed at. Even with a live clock, two writes inside one second still collide, so
    the name itself has to be collision-avoidant.
    """
    target = Path("/home/o/.claude.json")
    first = backup_path(target, FIXED_NOW, taken=lambda _p: False)
    assert first.name == f".claude.json.{BACKUP_SUFFIX}-{STAMP}.bak"

    existing = {first}
    second = backup_path(target, FIXED_NOW, taken=lambda p: p in existing)
    assert second != first
    assert second.name == f".claude.json.{BACKUP_SUFFIX}-{STAMP}-1.bak"

    existing.add(second)
    third = backup_path(target, FIXED_NOW, taken=lambda p: p in existing)
    assert third not in existing
    assert third.name == f".claude.json.{BACKUP_SUFFIX}-{STAMP}-2.bak"


def test_an_exhausted_suffix_range_falls_back_to_a_microsecond_stamp():
    """Never give up and return a colliding name -- widen the stamp instead."""
    target = Path("/home/o/.claude.json")
    sidecar = backup_path(target, FIXED_NOW, taken=lambda _p: True)
    assert sidecar.name == (
        f".claude.json.{BACKUP_SUFFIX}-{utc_stamp(FIXED_NOW, precise=True)}.bak"
    )
    assert f"-{MAX_COLLISION_SUFFIXES - 1}.bak" not in sidecar.name
    assert utc_stamp(FIXED_NOW, precise=True) != utc_stamp(FIXED_NOW)
