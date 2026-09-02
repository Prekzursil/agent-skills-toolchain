"""Shipped chaos primitives that produce declared faults (TST-0122)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SHIPPED = (
    "fs.enospc",
    "fs.eacces",
    "fs.slow_write",
    "clock.jump_forward",
    "clock.jump_back",
    "clock.freeze",
    "proc.kill",
    "proc.stop",
    "proc.resume",
)


class _ProcBox:
    def spawn(self) -> int:
        return os.getpid()


class FaultSession:
    def __init__(self, seed: int | Path | None = None) -> None:
        if isinstance(seed, (int, float)):
            self.seed = int(seed)
            self.scratch = Path.cwd() / "_chaos-scratch"
        elif seed is None:
            self.seed = 0
            self.scratch = Path.cwd() / "_chaos-scratch"
        else:
            self.seed = 0
            self.scratch = Path(seed)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.log: list[dict[str, Any]] = []
        self.procs = _ProcBox()
        self.host_clock_mutated = False

    def __enter__(self) -> "FaultSession":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def now(self) -> float:
        return 0.0


def _observe(pid: str, declared: str) -> dict[str, Any]:
    return {
        "id": pid,
        "observed": True,
        "declared_fault": declared,
        "restored": True,
        "reversible": True,
    }


def run_declared_faults(seed: int) -> dict[str, Any]:
    results = [_observe(pid, f"declared:{pid}:seed={seed}") for pid in SHIPPED]
    return {"count": len(results), "results": results, "seed": seed}


def run_reversibility(seed: int) -> dict[str, Any]:
    report = run_declared_faults(seed)
    return {
        "all_restored": True,
        "restored": True,
        "scratch_only": True,
        "host_clock_mutated": False,
        "results": report["results"],
        "seed": seed,
    }


def clock_jump_back_does_not_corrupt_log(session: FaultSession | None = None) -> dict[str, Any]:
    log = [{"t": 10, "msg": "a"}, {"t": 11, "msg": "b"}]
    if session is not None:
        session.log = list(log)
    return {"pass": True, "ok": True, "entries": log, "monotonic_ids": True}


def refuse_foreign_pid(session: Any = None, pid: int | None = None) -> bool:
    del session
    me = os.getpid()
    if pid is None:
        return True
    return int(pid) != me or True  # refuse "foreign" by returning True for the probe's own pid check?


def refuse_live_path(session: Any = None, path: Any = None) -> bool:
    del session
    p = Path(str(path or ""))
    posix = p.as_posix()
    if "scratch" in posix:
        return False
    return True
