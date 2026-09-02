#!/usr/bin/env python3
"""Live TST-0201 experiments: boundary lengths, mixed package, detector control."""
from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

from tracefs import DestTrace
from writer import (
    DEFAULT_BUDGET,
    entries_under,
    relative_for_length,
    resolved_len,
    resolved_str,
    write_package,
    write_package_late_check,
)

PAYLOAD = b"payload-ok"


def _scratch() -> Path:
    return Path(tempfile.mkdtemp(prefix="tst0201-", dir="/tmp"))


def run_boundary(scratch: Path, budget: int = DEFAULT_BUDGET) -> dict:
    rows: dict[str, dict] = {}
    labels = (
        ("limit_minus_1", budget - 1),
        ("limit", budget),
        ("limit_plus_1", budget + 1),
    )
    for label, total in labels:
        dest = scratch / label
        dest.mkdir()
        before = entries_under(dest)
        rel = relative_for_length(dest, total)
        measured = resolved_len(dest / rel)
        wr = write_package(dest, {rel: PAYLOAD}, budget=budget)
        after = entries_under(dest)
        round_trip = None
        if wr.ok:
            round_trip = (dest / rel).read_bytes() == PAYLOAD
        rows[label] = {
            "target_len": total,
            "measured_len": measured,
            "ok": wr.ok,
            "preflight_rejected": wr.preflight_rejected,
            "bytes_written": wr.bytes_written,
            "mkdir_calls": wr.mkdir_calls,
            "open_calls": wr.open_calls,
            "entries_before": before,
            "entries_after": after,
            "new_entries": sorted(set(after) - set(before)),
            "message": wr.message,
            "round_trip": round_trip,
            "rel": rel,
            "resolved": resolved_str(dest / rel),
        }
    return rows


def run_mixed(scratch: Path, budget: int = DEFAULT_BUDGET) -> dict:
    dest = scratch / "mixed-preflight"
    dest.mkdir()
    long_rel = relative_for_length(dest, budget + 1)
    members = {
        "ok-a.txt": b"A",
        "ok-b/nested.txt": b"B",
        long_rel: b"L",
    }
    before = entries_under(dest)
    wr = write_package(dest, members, budget=budget)
    after = entries_under(dest)
    return {
        "ok": wr.ok,
        "preflight_rejected": wr.preflight_rejected,
        "bytes_written": wr.bytes_written,
        "mkdir_calls": wr.mkdir_calls,
        "open_calls": wr.open_calls,
        "entries_before": before,
        "entries_after": after,
        "new_entries": sorted(set(after) - set(before)),
        "message": wr.message,
        "first_breach_len": next(
            (m.length for m in wr.members if m.over_budget), None
        ),
        "member_count": len(wr.members),
        "over_budget_count": sum(1 for m in wr.members if m.over_budget),
        "dest_exists": dest.exists(),
    }


def run_ghost(scratch: Path, budget: int = DEFAULT_BUDGET) -> dict:
    dest = scratch / "ghost-missing"
    long_rel = relative_for_length(dest, budget + 1)
    wr = write_package(dest, {long_rel: PAYLOAD}, budget=budget)
    return {
        "ok": wr.ok,
        "preflight_rejected": wr.preflight_rejected,
        "dest_existed_after": dest.exists(),
        "bytes_written": wr.bytes_written,
        "mkdir_calls": wr.mkdir_calls,
        "open_calls": wr.open_calls,
        "message": wr.message,
        "measured_len": resolved_len(dest / long_rel),
    }


def run_naive_mixed(scratch: Path, budget: int = DEFAULT_BUDGET) -> dict:
    dest = scratch / "mixed-naive"
    dest.mkdir()
    long_rel = relative_for_length(dest, budget + 1)
    members = {
        "ok-a.txt": b"A",
        "ok-b/nested.txt": b"B",
        long_rel: b"L",
    }
    before = entries_under(dest)
    wr = write_package_late_check(dest, members, budget=budget)
    after = entries_under(dest)
    return {
        "ok": wr.ok,
        "preflight_rejected": wr.preflight_rejected,
        "bytes_written": wr.bytes_written,
        "created": list(wr.created),
        "entries_before": before,
        "entries_after": after,
        "new_entries": sorted(set(after) - set(before)),
        "message": wr.message,
        "residue": len(after) > 0,
    }


def run_traced_breach(scratch: Path, budget: int = DEFAULT_BUDGET) -> dict:
    dest = scratch / "traced-breach"
    dest.mkdir()
    long_rel = relative_for_length(dest, budget + 1)
    with DestTrace(dest) as tr:
        wr = write_package(dest, {long_rel: b"L", "short.txt": b"S"}, budget=budget)
        events = list(tr.events)
    after = entries_under(dest)
    return {
        "ok": wr.ok,
        "preflight_rejected": wr.preflight_rejected,
        "bytes_written": wr.bytes_written,
        "trace_events": events,
        "trace_create_count": len(events),
        "entries_after": after,
        "message": wr.message,
    }


def run_traced_naive(scratch: Path, budget: int = DEFAULT_BUDGET) -> dict:
    dest = scratch / "traced-naive"
    dest.mkdir()
    long_rel = relative_for_length(dest, budget + 1)
    members = {"ok-a.txt": b"A", long_rel: b"L"}
    with DestTrace(dest) as tr:
        wr = write_package_late_check(dest, members, budget=budget)
        events = list(tr.events)
    after = entries_under(dest)
    return {
        "ok": wr.ok,
        "trace_events": events,
        "trace_create_count": len(events),
        "entries_after": after,
        "residue": len(after) > 0,
        "bytes_written": wr.bytes_written,
        "message": wr.message,
    }


def run_all(budget: int = DEFAULT_BUDGET) -> dict:
    scratch = _scratch()
    try:
        boundary = run_boundary(scratch, budget)
        mixed = run_mixed(scratch, budget)
        ghost = run_ghost(scratch, budget)
        naive = run_naive_mixed(scratch, budget)
        traced = run_traced_breach(scratch, budget)
        traced_naive = run_traced_naive(scratch, budget)
        return {
            "budget": budget,
            "scratch": str(scratch),
            "host": {
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
                "tmp": "/tmp",
            },
            "boundary": boundary,
            "mixed": mixed,
            "ghost": ghost,
            "naive": naive,
            "traced_breach": traced,
            "traced_naive": traced_naive,
        }
    finally:
        # Leave the tree for a moment? Always clean: experiments are re-runnable.
        import shutil

        shutil.rmtree(scratch, ignore_errors=True)


def verdicts(doc: dict) -> dict[str, bool]:
    b = doc["boundary"]
    lm, lim, lp = b["limit_minus_1"], b["limit"], b["limit_plus_1"]
    mixed = doc["mixed"]
    ghost = doc["ghost"]
    naive = doc["naive"]
    traced = doc["traced_breach"]
    traced_naive = doc["traced_naive"]
    budget = doc["budget"]
    return {
        "limit_minus_1_writes": (
            lm["ok"] is True
            and lm["measured_len"] == budget - 1
            and lm["round_trip"] is True
            and lm["bytes_written"] == len(PAYLOAD)
        ),
        "limit_writes": (
            lim["ok"] is True
            and lim["measured_len"] == budget
            and lim["round_trip"] is True
            and lim["bytes_written"] == len(PAYLOAD)
        ),
        "limit_plus_1_rejects": (
            lp["ok"] is False
            and lp["preflight_rejected"] is True
            and lp["bytes_written"] == 0
            and lp["new_entries"] == []
            and lp["open_calls"] == 0
            and lp["mkdir_calls"] == 0
            and lp["measured_len"] == budget + 1
            and str(budget) in (lp["message"] or "")
        ),
        "mixed_all_or_nothing": (
            mixed["ok"] is False
            and mixed["preflight_rejected"] is True
            and mixed["bytes_written"] == 0
            and mixed["new_entries"] == []
            and mixed["open_calls"] == 0
            and mixed["over_budget_count"] == 1
        ),
        "ghost_not_created": (
            ghost["ok"] is False
            and ghost["preflight_rejected"] is True
            and ghost["dest_existed_after"] is False
            and ghost["bytes_written"] == 0
            and ghost["mkdir_calls"] == 0
            and ghost["open_calls"] == 0
        ),
        "naive_leaves_residue": (
            naive["ok"] is False
            and naive["preflight_rejected"] is False
            and naive["residue"] is True
            and naive["bytes_written"] > 0
            and len(naive["new_entries"]) > 0
        ),
        "trace_breach_zero_creates": (
            traced["preflight_rejected"] is True
            and traced["trace_create_count"] == 0
            and traced["entries_after"] == []
            and traced["bytes_written"] == 0
        ),
        "trace_naive_creates": (
            traced_naive["residue"] is True and traced_naive["trace_create_count"] > 0
        ),
    }
