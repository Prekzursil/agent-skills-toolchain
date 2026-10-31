#!/usr/bin/env python3
"""Deterministic lease scenarios for TST-0161 probes and receipt emit."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from lease import FakeClock, FileLeaseManager

SHARED = "/workspace/shared.txt"
PATH_A = "/workspace/alpha.txt"
PATH_B = "/workspace/beta.txt"
PAYLOAD_A = b"payload-from-A-mid-write"
PAYLOAD_B = b"payload-from-B-after-reclaim"


def _mgr(root: Path, clock: FakeClock, *, recheck: bool) -> FileLeaseManager:
    return FileLeaseManager(root, clock=clock, write_time_recheck=recheck)


def independent_paths(root: Path) -> dict[str, Any]:
    clock = FakeClock(1000.0)
    mgr = _mgr(root, clock, recheck=True)
    a = mgr.acquire("sess-A", PATH_A, ttl_s=60.0)
    b = mgr.acquire("sess-B", PATH_B, ttl_s=60.0)
    wa = mgr.checked_write("sess-A", PATH_A, a["fence"], b"alpha-only")
    wb = mgr.checked_write("sess-B", PATH_B, b["fence"], b"beta-only")
    pub_a = mgr.read_published(PATH_A)
    pub_b = mgr.read_published(PATH_B)
    ok = (
        a.get("ok") is True
        and b.get("ok") is True
        and a.get("kind") == "GRANT"
        and b.get("kind") == "GRANT"
        and wa.get("ok") is True
        and wb.get("ok") is True
        and pub_a == b"alpha-only"
        and pub_b == b"beta-only"
    )
    return {
        "ok": ok,
        "first": a,
        "second": b,
        "write_a": wa,
        "write_b": wb,
        "both_granted": bool(a.get("ok") and b.get("ok")),
        "published_a": None if pub_a is None else pub_a.decode("utf-8"),
        "published_b": None if pub_b is None else pub_b.decode("utf-8"),
    }


def overlapping_conflict(root: Path) -> dict[str, Any]:
    clock = FakeClock(1000.0)
    mgr = _mgr(root, clock, recheck=True)
    first = mgr.acquire("sess-A", SHARED, ttl_s=60.0)
    second = mgr.acquire("sess-B", SHARED, ttl_s=60.0)
    still_a = mgr.acquire("sess-A", SHARED, ttl_s=60.0)
    ok = (
        first.get("ok") is True
        and first.get("kind") == "GRANT"
        and second.get("ok") is False
        and second.get("kind") == "LEASE_CONFLICT"
        and second.get("holder") == "sess-A"
        and second.get("requester") == "sess-B"
        and still_a.get("ok") is True
        and int(still_a.get("fence") or 0) == int(first.get("fence") or 0)
    )
    return {
        "ok": ok,
        "first_grant": first,
        "second_conflict": second,
        "holder_renew": still_a,
        "conflict_kind": second.get("kind"),
        "conflict_explicit": second.get("kind") == "LEASE_CONFLICT",
    }


def concurrent_conflict(root: Path, *, trials: int = 16) -> dict[str, Any]:
    clock = FakeClock(2000.0)
    rows: list[dict[str, Any]] = []
    double_grants = 0
    silent = 0
    for i in range(trials):
        mgr = _mgr(root / f"t{i:02d}", clock, recheck=True)
        path = f"/workspace/race-{i}.txt"
        barrier = threading.Barrier(2)
        slot: list[dict[str, Any] | None] = [None, None]

        def run(idx: int, sid: str) -> None:
            barrier.wait()
            slot[idx] = mgr.acquire(sid, path, ttl_s=60.0)

        t0 = threading.Thread(target=run, args=(0, "sess-A"))
        t1 = threading.Thread(target=run, args=(1, "sess-B"))
        t0.start()
        t1.start()
        t0.join()
        t1.join()
        a, b = slot[0], slot[1]
        grants = [r for r in (a, b) if r and r.get("ok")]
        conflicts = [r for r in (a, b) if r and not r.get("ok")]
        if len(grants) != 1:
            double_grants += 1
        if len(conflicts) != 1 or (conflicts and conflicts[0].get("kind") != "LEASE_CONFLICT"):
            silent += 1
        rows.append(
            {
                "trial": i,
                "grants": len(grants),
                "conflicts": len(conflicts),
                "loser": None if not conflicts else conflicts[0],
                "winner": None if not grants else grants[0].get("holder"),
            }
        )
    ok = double_grants == 0 and silent == 0 and trials == len(rows)
    sample_conflict = None
    for row in rows:
        if row.get("loser"):
            sample_conflict = row["loser"]
            break
    return {
        "ok": ok,
        "trials": trials,
        "double_grants": double_grants,
        "silent_or_untyped": silent,
        "sample_loser_conflict": sample_conflict,
        "rows": rows,
    }


def expiry_mid_write(root: Path, *, write_time_recheck: bool) -> dict[str, Any]:
    clock = FakeClock(3000.0)
    mgr = _mgr(root, clock, recheck=write_time_recheck)
    grant_a = mgr.acquire("sess-A", SHARED, ttl_s=10.0)
    begun = mgr.begin_write("sess-A", SHARED, grant_a["fence"], PAYLOAD_A)
    clock.advance(11.0)
    grant_b = mgr.acquire("sess-B", SHARED, ttl_s=10.0)
    write_b = mgr.checked_write("sess-B", SHARED, grant_b.get("fence") or 0, PAYLOAD_B)
    commit_a = mgr.commit_write(begun)
    published = mgr.read_published(SHARED)
    original_failed = commit_a.get("ok") is False
    original_continued = commit_a.get("ok") is True
    published_is_b = published == PAYLOAD_B
    published_is_a = published == PAYLOAD_A
    fence_bumped = int(grant_b.get("fence") or 0) > int(grant_a.get("fence") or 0)
    transfer_ok = (
        grant_a.get("ok") is True
        and begun.get("ok") is True
        and grant_b.get("ok") is True
        and fence_bumped
        and write_b.get("ok") is True
    )
    if write_time_recheck:
        scenario_ok = (
            transfer_ok
            and original_failed
            and commit_a.get("kind") in {"STALE_FENCE", "LEASE_EXPIRED"}
            and published_is_b
            and not published_is_a
        )
    else:
        scenario_ok = transfer_ok and original_continued and published_is_a
    return {
        "ok": scenario_ok,
        "write_time_recheck": write_time_recheck,
        "grant_a": grant_a,
        "begin_a": {k: begun.get(k) for k in ("ok", "kind", "fence", "payload_bytes", "phase")},
        "grant_b": grant_b,
        "write_b": write_b,
        "commit_a": commit_a,
        "original_failed": original_failed,
        "original_continued": original_continued,
        "fence_bumped": fence_bumped,
        "published": None if published is None else published.decode("utf-8"),
        "published_is_transferee": published_is_b,
        "published_is_original": published_is_a,
    }


def run_all(scratch: Path) -> dict[str, Any]:
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    independent = independent_paths(scratch / "independent")
    conflict = overlapping_conflict(scratch / "conflict")
    concurrent = concurrent_conflict(scratch / "concurrent")
    enforced = expiry_mid_write(scratch / "expiry-enforced", write_time_recheck=True)
    advisory = expiry_mid_write(scratch / "expiry-advisory", write_time_recheck=False)
    negative_fired = advisory.get("original_continued") is True
    negative_silent_on_good = enforced.get("original_failed") is True
    ok = (
        independent.get("ok") is True
        and conflict.get("ok") is True
        and concurrent.get("ok") is True
        and enforced.get("ok") is True
        and advisory.get("ok") is True
        and negative_fired
        and negative_silent_on_good
    )
    return {
        "ok": ok,
        "independent": independent,
        "conflict": conflict,
        "concurrent": concurrent,
        "expiry_enforced": enforced,
        "expiry_advisory": advisory,
        "negative_control": {
            "id": "TST-0161-NC-ADVISORY-NO-RECHECK",
            "fired_on_bad_state": negative_fired,
            "silent_on_good_state": negative_silent_on_good,
            "bad_commit_kind": (advisory.get("commit_a") or {}).get("kind"),
            "good_commit_kind": (enforced.get("commit_a") or {}).get("kind"),
        },
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)
