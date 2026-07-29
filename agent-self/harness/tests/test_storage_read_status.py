"""D-wu-63 — ``read_json`` must not conflate absent / corrupt / unreadable state.

``read_json(path, default)`` returns ``default`` for all three, which is the right
VALUE contract for its 20-odd callers but leaves a caller that persists control
state unable to tell "nothing written yet" (benign) from "what was written is
DAMAGED" (a finding). ``read_json_status`` adds the missing discriminator; these
tests pin each branch, including the two that share ``OSError``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.storage import (
    READ_DAMAGED,
    READ_MALFORMED,
    READ_MISSING,
    READ_OK,
    READ_UNREADABLE,
    atomic_write_json,
    read_json,
    read_json_status,
)


def test_status_ok_returns_the_parsed_document(tmp_path: Path):
    path = tmp_path / "good.json"
    atomic_write_json(path, {"settings": {"hooks": {}}})

    value, status = read_json_status(path, None)

    assert status == READ_OK
    assert value == {"settings": {"hooks": {}}}


def test_status_missing_is_distinct_from_malformed_and_unreadable(tmp_path: Path):
    absent = tmp_path / "never-written.json"
    malformed = tmp_path / "truncated.json"
    malformed.write_text('{"settings":', encoding="utf-8")
    unreadable = tmp_path / "adirectory.json"
    unreadable.mkdir()

    statuses = [read_json_status(p, "D")[1] for p in (absent, malformed, unreadable)]

    # The whole point: three different causes, three different labels. Before the
    # fix every one of these was indistinguishable at the call site.
    assert statuses == [READ_MISSING, READ_MALFORMED, READ_UNREADABLE]
    assert len(set(statuses)) == 3


@pytest.mark.parametrize(
    "status,damaged",
    [
        (READ_OK, False),
        (READ_MISSING, False),
        (READ_MALFORMED, True),
        (READ_UNREADABLE, True),
    ],
)
def test_read_damaged_covers_exactly_the_present_but_unusable_states(status, damaged):
    # A caller guards on this set; if MISSING ever slipped in, first-run installs
    # would nag, and if MALFORMED ever slipped out the original defect returns.
    assert (status in READ_DAMAGED) is damaged


def test_missing_wins_over_the_generic_oserror_branch(tmp_path: Path):
    # FileNotFoundError IS an OSError, so the order of the except clauses is the
    # whole behaviour here. A regression that reorders them turns every pre-install
    # first run into a spurious "damaged baseline" warning.
    _, status = read_json_status(tmp_path / "nested" / "deep" / "absent.json", None)

    assert status == READ_MISSING
    assert status not in READ_DAMAGED


def test_read_json_value_contract_is_unchanged_for_every_status(tmp_path: Path):
    # read_json stays fail-open and value-only; the discriminator is additive, so
    # none of the existing callers change behaviour.
    good = tmp_path / "good.json"
    good.write_text(json.dumps([1, 2]), encoding="utf-8")
    malformed = tmp_path / "bad.json"
    malformed.write_text("{", encoding="utf-8")
    unreadable = tmp_path / "dir.json"
    unreadable.mkdir()

    assert read_json(good, "D") == [1, 2]
    assert read_json(tmp_path / "absent.json", "D") == "D"
    assert read_json(malformed, "D") == "D"
    assert read_json(unreadable, "D") == "D"


class _TypeErrorOnRead:
    def read_text(self, encoding: str | None = None):
        raise TypeError("read blew up")


class _NonTextRead:
    def read_text(self, encoding: str | None = None):
        return 12345  # json.loads on a non-str raises TypeError, not ValueError


def test_typeerror_on_read_and_on_parse_both_stay_fail_open():
    # read_json originally caught (OSError, ValueError, TypeError) across the whole
    # expression. Splitting the try blocks must not narrow that: a TypeError from
    # the READ is unreadable, a TypeError from the PARSE is malformed, and neither
    # may escape into a hook.
    assert read_json_status(_TypeErrorOnRead(), "D") == ("D", READ_UNREADABLE)  # type: ignore[arg-type]
    assert read_json_status(_NonTextRead(), "D") == ("D", READ_MALFORMED)  # type: ignore[arg-type]
    assert read_json(_TypeErrorOnRead(), "D") == "D"  # type: ignore[arg-type]
    assert read_json(_NonTextRead(), "D") == "D"  # type: ignore[arg-type]
