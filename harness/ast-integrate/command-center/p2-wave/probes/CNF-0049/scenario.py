#!/usr/bin/env python3
"""CNF-0049 measurement: rollback vs prefix-hash, plus detector controls.

Probe 1 and emit share this runner so the recorded hashes are live, not typed.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from ledger import (  # noqa: E402
    encode_event,
    is_byte_prefix,
    line_count,
    prefix_hash,
    retained_prefix_diff,
    rewrite_timestamp_in_retained_line,
    sha256_bytes,
    snap,
    truncate_one_line,
)
from rollback import ROLLBACK_PAYLOAD, rollback_append_only  # noqa: E402

SEED_EVENTS: list[dict[str, Any]] = [
    {
        "id": "R-M08",
        "title": "seed-a",
        "ts": "2026-08-01T00:00:00+00:00",
        "verb": "open",
    },
    {
        "id": "R-M08",
        "note": "progress",
        "ts": "2026-08-01T00:00:01+00:00",
        "verb": "note",
    },
    {
        "id": "R-M09",
        "evidence": "shipped",
        "ts": "2026-08-01T00:00:02+00:00",
        "verb": "close",
    },
    {
        "id": "R-M10",
        "title": "seed-b",
        "ts": "2026-08-01T00:00:03+00:00",
        "verb": "open",
    },
]


def seed_ledger(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(encode_event(ev) for ev in SEED_EVENTS)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path.read_bytes()


def run_rollback_prefix() -> dict[str, Any]:
    """SUT: append-only rollback. Pre-rollback bytes must be a prefix of post."""
    with tempfile.TemporaryDirectory(prefix="cnf0049-rb-") as tmp:
        events = Path(tmp) / "events" / "EVENTS.jsonl"
        before = seed_ledger(events)
        meta = rollback_append_only(events, dict(ROLLBACK_PAYLOAD))
        after = events.read_bytes()
        pre_ok = is_byte_prefix(before, after)
        after_lines = after.decode("utf-8").splitlines()
        appended = after_lines[line_count(before) :] if pre_ok else []
        return {
            "pass": pre_ok
            and line_count(after) == line_count(before) + 1
            and sha256_bytes(after[: len(before)]) == sha256_bytes(before),
            "pre_is_byte_prefix_of_post": pre_ok,
            "only_new_lines_appended": pre_ok and len(after) > len(before),
            "before": snap(before),
            "after": {
                **snap(after),
                "prefix_hash": prefix_hash(after, len(before)),
            },
            "retained_prefix_diff": retained_prefix_diff(before, after),
            "appended_line_count": line_count(after) - line_count(before),
            "appended_lines": appended,
            "rollback_meta": meta,
            "writer": "tools/command-center/close.py:append_event",
        }


def run_truncation_control() -> dict[str, Any]:
    """Control: drop one line from a copy; prefix check must fail."""
    with tempfile.TemporaryDirectory(prefix="cnf0049-tr-") as tmp:
        events = Path(tmp) / "events" / "EVENTS.jsonl"
        before = seed_ledger(events)
        truncated = truncate_one_line(before)
        failed = not is_byte_prefix(before, truncated)
        return {
            "pass": failed,
            "prefix_check_failed_as_designed": failed,
            "lines_dropped": 1,
            "before_line_count": line_count(before),
            "truncated_line_count": line_count(truncated),
            "before_prefix_hash": prefix_hash(before),
            "truncated_prefix_hash": prefix_hash(truncated),
            "method": "truncate a copy of the pre-rollback ledger by one trailing line, then assert original is not a byte prefix of the copy",
        }


def run_timestamp_rewrite_control() -> dict[str, Any]:
    """Control: rewrite ts in a retained line; hash catches it, line count does not."""
    with tempfile.TemporaryDirectory(prefix="cnf0049-ts-") as tmp:
        events = Path(tmp) / "events" / "EVENTS.jsonl"
        before = seed_ledger(events)
        rewritten = rewrite_timestamp_in_retained_line(before, 0)
        same_lines = line_count(rewritten) == line_count(before)
        hash_diff = prefix_hash(rewritten) != prefix_hash(before)
        still_prefix = is_byte_prefix(before, rewritten)
        return {
            "pass": same_lines and hash_diff and not still_prefix,
            "caught_by_prefix_hash": hash_diff,
            "invisible_to_line_count": same_lines,
            "prefix_check_fails": not still_prefix,
            "line_count_before": line_count(before),
            "line_count_after_rewrite": line_count(rewritten),
            "before_prefix_hash": prefix_hash(before),
            "rewritten_prefix_hash": prefix_hash(rewritten),
            "rewritten_bytes": len(rewritten),
            "before_bytes": len(before),
            "method": "rewrite ts on retained line 0 to 1999-01-01; compare prefix hash vs line count",
        }


def run_all() -> dict[str, Any]:
    rb = run_rollback_prefix()
    tr = run_truncation_control()
    ts = run_timestamp_rewrite_control()
    return {
        "rollback": rb,
        "truncation_control": tr,
        "timestamp_rewrite_control": ts,
        "pass": bool(rb.get("pass") and tr.get("pass") and ts.get("pass")),
    }


def recorded_from_artifact(doc: dict[str, Any]) -> dict[str, Any]:
    """Read probe-compared fields from a receipt_core document.

    Domain measurements live under report.* so the artifact can parse against
    ledger-audit (receipt_core additionalProperties=false). Older top-level
    keys are still accepted if present.
    """
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    tests = report.get("tests") if isinstance(report.get("tests"), dict) else {}
    top_tests = doc.get("tests")
    if not tests and isinstance(top_tests, dict):
        tests = top_tests
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    if not ledger and isinstance(doc.get("ledger"), dict):
        ledger = doc["ledger"]
    verdict = report.get("verdict") if isinstance(report.get("verdict"), dict) else {}
    if not verdict and isinstance(doc.get("verdict"), dict):
        verdict = doc["verdict"]
    return {
        "state": doc.get("state"),
        "ledger": ledger,
        "verdict": verdict,
        "tests": tests,
    }
