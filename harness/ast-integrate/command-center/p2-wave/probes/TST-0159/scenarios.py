"""Live scenarios for TST-0159: false-negative timeout, failed retry, LWW mutant."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from write_once_store import (  # noqa: E402
    DUPLICATE_COMPLETION,
    VERSION_MISMATCH,
    WriteOnceReceiptStore,
    sha256_path,
    write_once_holds,
)

UNIT_COMPLETED = "UNIT-FN-TIMEOUT"
UNIT_FAILED = "UNIT-GENUINE-FAIL"
ORIGINAL_BODY = {
    "state": "SUCCESS",
    "result": "original-completed-before-dispatcher-timeout",
    "attempt": 1,
}
RETRY_BODY = {
    "state": "SUCCESS",
    "result": "retry-after-false-negative-timeout",
    "attempt": 2,
}
FAILED_BODY = {
    "state": "FAILED",
    "result": "genuine-failure",
    "attempt": 1,
}
FAILED_RETRY_BODY = {
    "state": "SUCCESS",
    "result": "retry-after-genuine-failure",
    "attempt": 2,
}


def _event_kinds(events: list[dict[str, Any]], unit_id: str) -> list[str]:
    return [str(e.get("kind")) for e in events if e.get("unit_id") == unit_id]


def run_false_negative_timeout(
    root: Path, *, last_write_wins: bool = False
) -> dict[str, Any]:
    """Original completed; dispatcher timed out; retry must not overwrite."""
    store = WriteOnceReceiptStore(root, last_write_wins=last_write_wins)
    first = store.write(
        UNIT_COMPLETED,
        ORIGINAL_BODY,
        expected_version=None,
        reason="original-complete",
    )
    path = store.receipt_path(UNIT_COMPLETED)
    hash_before = sha256_path(path)
    dispatch_view = {
        "unit_id": UNIT_COMPLETED,
        "dispatcher_observed": "TIMEOUT",
        "receipt_state_on_disk": store.load_receipt(UNIT_COMPLETED)["state"],
        "false_negative": True,
    }
    (root / "dispatch-view.json").write_text(
        json.dumps(dispatch_view, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    second = store.write(
        UNIT_COMPLETED,
        RETRY_BODY,
        expected_version=None,
        reason="false-negative-timeout-retry",
    )
    hash_after = sha256_path(path)
    events = store.load_events()
    receipt = store.load_receipt(UNIT_COMPLETED)
    holds = write_once_holds(
        hash_before=hash_before,
        hash_after=hash_after,
        events=events,
        unit_id=UNIT_COMPLETED,
    )
    dup = [
        e
        for e in events
        if e.get("kind") == DUPLICATE_COMPLETION and e.get("unit_id") == UNIT_COMPLETED
    ]
    return {
        "unit_id": UNIT_COMPLETED,
        "last_write_wins": last_write_wins,
        "first_action": first.get("action"),
        "second_action": second.get("action"),
        "second_status": second.get("status"),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "hashes_equal": hash_before == hash_after,
        "receipt_state": None if receipt is None else receipt.get("state"),
        "receipt_version": None if receipt is None else receipt.get("version"),
        "receipt_result": None if receipt is None else receipt.get("result"),
        "duplicate_events": dup,
        "event_kinds": _event_kinds(events, UNIT_COMPLETED),
        "dispatch_view": dispatch_view,
        "write_once_holds": holds,
        "ok": holds if not last_write_wins else (not holds),
    }


def run_genuine_failure_retry(root: Path) -> dict[str, Any]:
    """Both-states: a retry of a genuinely FAILED unit DOES write a new receipt."""
    store = WriteOnceReceiptStore(root, last_write_wins=False)
    first = store.write(
        UNIT_FAILED,
        FAILED_BODY,
        expected_version=None,
        reason="genuine-failure",
    )
    path = store.receipt_path(UNIT_FAILED)
    hash_before = sha256_path(path)
    existing = store.load_receipt(UNIT_FAILED)
    second = store.write(
        UNIT_FAILED,
        FAILED_RETRY_BODY,
        expected_version=int(existing["version"]),
        reason="retry-after-genuine-failure",
    )
    hash_after = sha256_path(path)
    events = store.load_events()
    receipt = store.load_receipt(UNIT_FAILED)
    wrote = (
        second.get("action") == "replaced"
        and hash_before != hash_after
        and receipt is not None
        and receipt.get("state") == "SUCCESS"
        and int(receipt.get("version") or 0) == 2
        and receipt.get("result") == FAILED_RETRY_BODY["result"]
    )
    dup = [
        e
        for e in events
        if e.get("kind") == DUPLICATE_COMPLETION and e.get("unit_id") == UNIT_FAILED
    ]
    return {
        "unit_id": UNIT_FAILED,
        "first_action": first.get("action"),
        "second_action": second.get("action"),
        "second_status": second.get("status"),
        "hash_before": hash_before,
        "hash_after": hash_after,
        "hashes_equal": hash_before == hash_after,
        "receipt_state": None if receipt is None else receipt.get("state"),
        "receipt_version": None if receipt is None else receipt.get("version"),
        "receipt_result": None if receipt is None else receipt.get("result"),
        "duplicate_events": dup,
        "event_kinds": _event_kinds(events, UNIT_FAILED),
        "wrote_new_receipt": wrote,
        "ok": wrote,
    }


def run_stale_cas_refused(root: Path) -> dict[str, Any]:
    """Version guard: a stale expected_version cannot replace a FAILED receipt."""
    store = WriteOnceReceiptStore(root, last_write_wins=False)
    store.write(UNIT_FAILED, FAILED_BODY, expected_version=None, reason="genuine-failure")
    path = store.receipt_path(UNIT_FAILED)
    hash_before = sha256_path(path)
    second = store.write(
        UNIT_FAILED,
        FAILED_RETRY_BODY,
        expected_version=0,
        reason="stale-cas",
    )
    hash_after = sha256_path(path)
    receipt = store.load_receipt(UNIT_FAILED)
    ok = (
        second.get("status") == VERSION_MISMATCH
        and hash_before == hash_after
        and receipt is not None
        and receipt.get("state") == "FAILED"
    )
    return {
        "second_status": second.get("status"),
        "hashes_equal": hash_before == hash_after,
        "receipt_state": None if receipt is None else receipt.get("state"),
        "ok": ok,
    }


def run_last_write_wins_must_fail(root: Path) -> dict[str, Any]:
    """Negative control: last-write-wins semantics must fail the write-once test."""
    inner = run_false_negative_timeout(root, last_write_wins=True)
    fired = (
        inner["write_once_holds"] is False
        and inner["hashes_equal"] is False
        and inner["second_action"] == "replaced"
        and inner["receipt_result"] == RETRY_BODY["result"]
        and not inner["duplicate_events"]
    )
    return {
        **inner,
        "detector_fired_on_lww": fired,
        "ok": fired,
        "detail": (
            "last-write-wins overwrote the terminal receipt, hashes diverged, "
            "and no DUPLICATE-COMPLETION was recorded — the write-once "
            "predicate correctly fails this mutant"
        ),
    }


def run_both_states(root: Path) -> dict[str, Any]:
    fn = run_false_negative_timeout(root / "fn-timeout", last_write_wins=False)
    failed = run_genuine_failure_retry(root / "genuine-fail")
    stale = run_stale_cas_refused(root / "stale-cas")
    ok = bool(fn.get("ok") and failed.get("ok") and stale.get("ok"))
    return {
        "false_negative_timeout": fn,
        "genuine_failure_retry": failed,
        "stale_cas": stale,
        "ok": ok,
    }


def run_all(root: Path) -> dict[str, Any]:
    both = run_both_states(root / "both")
    lww = run_last_write_wins_must_fail(root / "lww")
    ok = bool(both.get("ok") and lww.get("ok"))
    return {
        "both_states": both,
        "last_write_wins": lww,
        "ok": ok,
    }
