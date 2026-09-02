#!/usr/bin/env python3
"""Executable pre-flight: may A5 run a given fan-out on a named substrate?

Exit 0 = allowed, 2 = refused, 1 = error.
Never ramps to freeze: this is arithmetic over a live snapshot plus a
measured per-worker commit sample, not a 2048-process spawn.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import box  # noqa: E402

ESTATE = HERE / "fixtures" / "estate-freeze.json"
PROCESS_MARGIN = 0.75
COMMIT_FRACTION = 0.70
LOCAL_DISPATCHERS = 3
A5_BATCH = 2048


def load_estate() -> dict[str, Any]:
    return json.loads(ESTATE.read_text(encoding="utf-8"))


def ceilings(snap: dict[str, Any], estate: dict[str, Any]) -> dict[str, int]:
    sessions = int(estate["sessions"])
    servers = int(estate["servers_per_session"])
    freeze_n = sessions * servers
    max_n = max(1, int(freeze_n * PROCESS_MARGIN))
    limit = int(snap["CommitLimit"])
    max_commit = max(1, int(limit * COMMIT_FRACTION))
    return {
        "estate_freeze_processes": freeze_n,
        "max_concurrent_processes": max_n,
        "max_committed_bytes": max_commit,
        "commit_limit_bytes": limit,
    }


def project(
    *,
    substrate: str,
    fanout: int,
    snap: dict[str, Any],
    commit_per_worker: int,
) -> dict[str, int]:
    base_n = int(snap["nprocs"])
    base_c = int(snap["Committed_AS"])
    extra_n = 0
    extra_c = 0
    if substrate in {"local", "worktree"}:
        extra_n = LOCAL_DISPATCHERS + int(fanout)
        extra_c = extra_n * int(commit_per_worker)
    elif substrate == "cloud":
        extra_n = 1
        extra_c = int(commit_per_worker)
    else:
        raise ValueError(f"unknown substrate {substrate}")
    return {
        "projected_processes": base_n + extra_n,
        "projected_commit_bytes": base_c + extra_c,
        "extra_processes": extra_n,
        "extra_commit_bytes": extra_c,
    }


def evaluate(
    *,
    substrate: str,
    fanout: int,
    snap: dict[str, Any],
    commit_per_worker: int,
    estate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    estate = estate or load_estate()
    ceil = ceilings(snap, estate)
    proj = project(
        substrate=substrate,
        fanout=fanout,
        snap=snap,
        commit_per_worker=commit_per_worker,
    )
    reasons: list[str] = []
    if substrate in {"local", "worktree"}:
        if proj["projected_processes"] > ceil["max_concurrent_processes"]:
            reasons.append(
                "projected_processes "
                f"{proj['projected_processes']} > max_concurrent_processes "
                f"{ceil['max_concurrent_processes']}"
            )
        if proj["projected_commit_bytes"] > ceil["max_committed_bytes"]:
            reasons.append(
                "projected_commit_bytes "
                f"{proj['projected_commit_bytes']} > max_committed_bytes "
                f"{ceil['max_committed_bytes']}"
            )
    allowed = len(reasons) == 0
    return {
        "allowed": allowed,
        "substrate": substrate,
        "fanout": int(fanout),
        "reasons": reasons,
        "snapshot": {
            "Committed_AS": snap["Committed_AS"],
            "CommitLimit": snap["CommitLimit"],
            "MemAvailable": snap["MemAvailable"],
            "nprocs": snap["nprocs"],
            "ram_hides_commit": snap["ram_hides_commit"],
        },
        "resource_ceiling": ceil,
        "projection": proj,
        "commit_per_worker": int(commit_per_worker),
        "actionable": True,
        "executable": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/ARC-0037/preflight.py"
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--substrate", required=True, choices=("local", "worktree", "cloud"))
    p.add_argument("--fanout", required=True, type=int)
    p.add_argument("--commit-per-worker", type=int, default=0)
    args = p.parse_args()
    snap = box.snapshot()
    per = args.commit_per_worker
    if per <= 0:
        per = max(1, int(snap["Committed_AS"] / max(1, snap["nprocs"])))
    doc = evaluate(
        substrate=args.substrate,
        fanout=args.fanout,
        snap=snap,
        commit_per_worker=per,
    )
    print(json.dumps(doc, indent=1, sort_keys=True))
    if doc["allowed"]:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
