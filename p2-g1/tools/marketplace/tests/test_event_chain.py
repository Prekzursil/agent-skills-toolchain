"""IMP-0072 tests: tamper detection is localised; clean log verifies; writer is append-only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

MARKET = Path(__file__).resolve().parents[1]
if str(MARKET) not in sys.path:
    sys.path.insert(0, str(MARKET))

from event_chain import (  # noqa: E402
    AppendOnlyViolation,
    EventLog,
    build_demo_log,
    tamper_field,
    verify_log,
)
import pytest


def test_clean_log_verifies_in_the_same_run(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    rows = build_demo_log(log)
    res = verify_log(log)
    assert res.ok is True
    assert res.record_count == len(rows) == 5
    assert res.first_bad_seq is None


def test_tamper_is_detected_and_localised(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    build_demo_log(log)
    # edit ONE field of the MIDDLE record (seq 3), leaving its hash stale
    tamper_field(log, 3, ("payload", "message"), "forged-message")
    res = verify_log(log)
    assert res.ok is False
    assert res.first_bad_seq == 3, res.as_dict()
    assert res.named_record is not None
    assert res.named_record["seq"] == 3
    assert res.named_record["payload"]["message"] == "forged-message"


def test_writer_rejects_rewrite_attempts(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    build_demo_log(log)
    ev = EventLog(log)
    with pytest.raises(AppendOnlyViolation):
        ev.replace(2, payload={"reason": "rewritten"})
    with pytest.raises(AppendOnlyViolation):
        ev.truncate()
    # append still works and chains from the last record
    rec = ev.append("moderate", "moderator:carol", "demo-pkg", "1.0.0",
                    "2026-08-24T17:00:00Z", {"flag": "late"})
    assert verify_log(log).ok is True
    assert rec["seq"] == 6


def test_rechain_is_honest_about_its_limit(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    build_demo_log(log)
    from event_chain import rechain_after_edit
    rechain_after_edit(log, 3, ("payload", "message"), "rewritten-legitimately")
    res = verify_log(log)
    assert res.ok is True  # re-chained log verifies clean -> external anchor needed
