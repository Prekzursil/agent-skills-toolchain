#!/usr/bin/env python3
"""Numeric ceiling projection for THIS box under MCP stdio fan-out."""
from __future__ import annotations

from typing import Any

ABORT_FRACTION = 0.50
ESTATE_SESSIONS = 23
ESTATE_MCP_PER_SESSION = 65
ESTATE_PROCESS_COUNT = 2037  # catalog incident figure; not re-measured as a freeze
SCHEDULER_BOUND = 80
SCHEDULER_SOURCE = (
    "command-center/p2-wave/seed-stage/dispatch_cursor.py default cap=80 "
    "(simultaneity cap, not commit-aware)"
)
ESTATE_COMMIT_PER_MCP_BYTES = 50 * 1024 * 1024  # labelled estate-precedent, not this-box freeze


def project(
    snap: dict[str, Any],
    calib: dict[str, Any],
    *,
    live_mcp_count: int,
) -> dict[str, Any]:
    abort = ABORT_FRACTION
    commit_limit = int(snap["commit_limit_bytes"] or 0)
    committed = int(snap["committed_as_bytes"] or 0)
    headroom_commit = max(0, commit_limit - committed)
    pid_max = int(snap["pid_max"] or 0)
    nproc = snap.get("nproc_soft") or pid_max
    try:
        nproc_i = int(nproc)
    except (TypeError, ValueError):
        nproc_i = pid_max
    proc_cap = min(pid_max, nproc_i) if pid_max and nproc_i else max(pid_max, nproc_i)
    headroom_procs = max(0, proc_cap - int(snap["process_count"] or 0))
    fd_max = int(snap["fd_max"] or 0)
    fd_unbounded = fd_max > 10**12
    headroom_fds = None if fd_unbounded else max(0, fd_max - int(snap["fd_allocated"] or 0))

    measured_commit = max(0, int(calib.get("delta_committed_as_bytes") or 0))
    measured_fds = max(1, int(calib.get("delta_fd_allocated") or 4))
    mcp_policy = ESTATE_MCP_PER_SESSION
    procs_per_session = 1 + mcp_policy
    dummy_commit_per_session = procs_per_session * max(measured_commit, 1)
    estate_commit_per_session = procs_per_session * ESTATE_COMMIT_PER_MCP_BYTES
    fds_per_session = procs_per_session * measured_fds

    def sessions_for(headroom: int | None, cost: int) -> int | None:
        if headroom is None or cost <= 0:
            return None
        return int((abort * headroom) // cost)

    ceil_commit_measured = sessions_for(headroom_commit, dummy_commit_per_session)
    ceil_commit_estate = sessions_for(headroom_commit, estate_commit_per_session)
    ceil_procs = sessions_for(headroom_procs, procs_per_session)
    ceil_fds = sessions_for(headroom_fds, fds_per_session)

    candidates = [
        ("commit-charge-estate-precedent", ceil_commit_estate),
        ("process-table", ceil_procs),
    ]
    if ceil_fds is not None:
        candidates.append(("file-handles", ceil_fds))
    binding_name, binding_val = min(
        [(n, v) for n, v in candidates if v is not None],
        key=lambda kv: kv[1],
    )
    safe = int(binding_val or 0)

    ten_x_same_cap = SCHEDULER_BOUND  # 10x units, same simultaneity cap
    ten_x_concurrency = SCHEDULER_BOUND * 10
    eager_procs_at_cap = SCHEDULER_BOUND * procs_per_session
    eager_procs_at_10x_conc = ten_x_concurrency * procs_per_session

    production_stops_first = False  # IMP-0445 absent; cap 80 is not commit-aware
    ref_guard_would_stop_sandbox_first = True

    first = binding_name
    if ceil_commit_estate is not None and ceil_procs is not None:
        if ceil_commit_estate <= ceil_procs:
            first = (
                "commit charge (Committed_AS toward CommitLimit), matching the "
                "estate freeze class; Task Manager / RAM-percent would stay silent"
            )
        else:
            first = (
                "process/nproc table on this Linux box binds before modeled "
                "commit headroom under the abort fraction"
            )

    return {
        "abort_fraction_of_headroom": abort,
        "live_mcp_like_count": live_mcp_count,
        "mcp_per_session_policy": mcp_policy,
        "mcp_policy_source": (
            "catalog estate spawn policy 65 stdio MCP per session "
            "(incident 23 x 65 = 2037 processes); live MCP-like census is "
            "heuristic and is not a freeze re-run"
        ),
        "procs_per_session": procs_per_session,
        "headroom": {
            "commit_bytes": headroom_commit,
            "processes": headroom_procs,
            "fds": headroom_fds,
            "fd_unbounded": fd_unbounded,
            "process_cap": proc_cap,
        },
        "cost": {
            "measured_dummy_commit_delta_bytes": measured_commit,
            "measured_dummy_fd_delta": measured_fds,
            "estate_precedent_commit_per_mcp_bytes": ESTATE_COMMIT_PER_MCP_BYTES,
            "dummy_commit_per_session_bytes": dummy_commit_per_session,
            "estate_commit_per_session_bytes": estate_commit_per_session,
            "fds_per_session": fds_per_session,
        },
        "session_ceilings": {
            "commit_using_dummy_worker": ceil_commit_measured,
            "commit_using_estate_precedent": ceil_commit_estate,
            "process_table": ceil_procs,
            "file_handles": ceil_fds,
        },
        "safe_session_ceiling": safe,
        "binding_constraint": binding_name,
        "first_to_degrade": first,
        "program_scheduler": {
            "bound": SCHEDULER_BOUND,
            "source": SCHEDULER_SOURCE,
            "commit_aware": False,
        },
        "program_stops_first": production_stops_first,
        "reference_guard_stops_sandbox_first": ref_guard_would_stop_sandbox_first,
        "ten_x": {
            "same_cap_peak_sessions": ten_x_same_cap,
            "same_cap_eager_processes": eager_procs_at_cap,
            "ten_x_concurrency_sessions": ten_x_concurrency,
            "ten_x_concurrency_eager_processes": eager_procs_at_10x_conc,
            "same_cap_sits_below_safe_ceiling": SCHEDULER_BOUND <= safe,
            "ten_x_concurrency_sits_below_safe_ceiling": ten_x_concurrency <= safe,
            "note": (
                "10x unit count with an unchanged simultaneity cap still peaks at 80. "
                "10x concurrency (800) with eager stdio MCP is a different question "
                "and is the one that collides with box headroom."
            ),
        },
        "estate_incident": {
            "sessions": ESTATE_SESSIONS,
            "mcp_per_session": ESTATE_MCP_PER_SESSION,
            "process_count_cited": ESTATE_PROCESS_COUNT,
            "reproduced_as_freeze": False,
        },
    }
