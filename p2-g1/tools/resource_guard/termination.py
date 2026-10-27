"""Ceiling-pressure resource guard: spare allowlisted shared services, reap proven orphans."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "ceiling-pressure.json"

ACTION_REAP = "REAP"
ACTION_SPARE = "SPARE"
REASON_ALLOWLIST = "ALLOWLIST_PROTECTED"
REASON_BELOW_CEILING = "BELOW_CEILING"
REASON_ORPHAN_NOT_PROVEN = "ORPHAN_NOT_PROVEN"
REASON_ORPHAN_PROVEN = "ORPHAN_PROVEN"

SHARED_NAME = "agent-mail"


@dataclass
class Process:
    pid: int
    name: str
    rss: int
    alive: bool = True
    allowlisted: bool = False
    death_signals: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "rss": self.rss,
            "alive": self.alive,
            "allowlisted": self.allowlisted,
            "death_signals": list(self.death_signals),
        }


@dataclass
class World:
    commit_charge: float
    commit_ceiling: float
    ram_percent: float
    processes: dict[int, Process]
    allowlist: list[str] = field(default_factory=list)

    def at_ceiling(self) -> bool:
        return self.commit_charge >= self.commit_ceiling

    def process(self, pid: int) -> Process:
        return self.processes[pid]

    def clone(self) -> "World":
        return copy.deepcopy(self)


@dataclass
class Decision:
    pid: int
    action: str
    reason: str
    allowlist_match: str | None = None
    orphan: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "action": self.action,
            "reason": self.reason,
            "allowlist_match": self.allowlist_match,
            "orphan": dict(self.orphan),
        }


@dataclass
class Run:
    at_ceiling: bool
    commit_charge: float
    commit_ceiling: float
    ram_percent: float
    ram_percent_would_fire: bool
    kill_set: tuple[int, ...]
    decisions: list[Decision]
    allowlist_used: bool

    def decision_for(self, pid: int) -> Decision:
        for row in self.decisions:
            if row.pid == pid:
                return row
        raise KeyError(pid)


def _default_world(*, at_ceiling: bool) -> World:
    if FIXTURE.is_file():
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        procs = {}
        for row in doc.get("processes") or []:
            p = Process(
                pid=int(row["pid"]),
                name=str(row.get("name") or ""),
                rss=int(row.get("rss") or 0),
                alive=bool(row.get("alive", True)),
                allowlisted=bool(row.get("allowlisted", False)),
                death_signals=list(row.get("death_signals") or []),
            )
            procs[p.pid] = p
        charge = float(doc.get("commit_charge") or (100.0 if at_ceiling else 10.0))
        ceiling = float(doc.get("commit_ceiling") or 80.0)
        if not at_ceiling:
            charge = min(charge, ceiling / 4)
        return World(
            commit_charge=charge,
            commit_ceiling=ceiling,
            ram_percent=float(doc.get("ram_percent") or 12.0),
            processes=procs,
            allowlist=list(doc.get("allowlist") or [SHARED_NAME]),
        )
    procs = {
        8812: Process(
            8812,
            SHARED_NAME,
            rss=50,
            allowlisted=True,
            death_signals=["ppid-gone", "session-closed"],
        ),
        9001: Process(
            9001,
            "session-orphan",
            rss=900,
            death_signals=["ppid-gone", "session-closed"],
        ),
        9002: Process(9002, "session-live", rss=800, death_signals=[]),
        9003: Process(
            9003, "session-one-signal", rss=700, death_signals=["ppid-gone"]
        ),
    }
    ceiling = 80.0
    charge = 80.0 if at_ceiling else 10.0
    return World(
        commit_charge=charge,
        commit_ceiling=ceiling,
        ram_percent=12.0,
        processes=procs,
        allowlist=[SHARED_NAME],
    )


def load_ceiling_world() -> World:
    return _default_world(at_ceiling=True)


def load_below_ceiling_world() -> World:
    return _default_world(at_ceiling=False)


def drop_allowlist(world: World) -> World:
    clone = world.clone()
    clone.allowlist = []
    for proc in clone.processes.values():
        proc.allowlisted = False
    return clone


def _match_allowlist(world: World, proc: Process) -> str | None:
    if proc.name in world.allowlist or proc.allowlisted:
        return proc.name
    return None


def evaluate(world: World) -> Run:
    at = world.at_ceiling()
    ram_would = world.ram_percent >= world.commit_ceiling
    decisions: list[Decision] = []
    kill: list[int] = []
    allowlist_used = False
    for proc in world.processes.values():
        signals = list(proc.death_signals)
        match = _match_allowlist(world, proc)
        if not at:
            decisions.append(
                Decision(
                    pid=proc.pid,
                    action=ACTION_SPARE,
                    reason=REASON_BELOW_CEILING,
                    orphan={"signal_count": len(signals), "signals": signals},
                )
            )
            continue
        if match:
            allowlist_used = True
            decisions.append(
                Decision(
                    pid=proc.pid,
                    action=ACTION_SPARE,
                    reason=REASON_ALLOWLIST,
                    allowlist_match=match,
                    orphan={"signal_count": len(signals), "signals": signals},
                )
            )
            continue
        if len(signals) >= 2:
            kill.append(proc.pid)
            decisions.append(
                Decision(
                    pid=proc.pid,
                    action=ACTION_REAP,
                    reason=REASON_ORPHAN_PROVEN,
                    orphan={"signal_count": len(signals), "signals": signals},
                )
            )
            continue
        decisions.append(
            Decision(
                pid=proc.pid,
                action=ACTION_SPARE,
                reason=REASON_ORPHAN_NOT_PROVEN,
                orphan={"signal_count": len(signals), "signals": signals},
            )
        )
    return Run(
        at_ceiling=at,
        commit_charge=world.commit_charge,
        commit_ceiling=world.commit_ceiling,
        ram_percent=world.ram_percent,
        ram_percent_would_fire=ram_would,
        kill_set=tuple(kill),
        decisions=decisions,
        allowlist_used=allowlist_used,
    )


def apply_reaps(world: World, run: Run) -> World:
    clone = world.clone()
    for pid in run.kill_set:
        if pid in clone.processes:
            clone.processes[pid].alive = False
    return clone


def health_status(world: World, pid: int) -> dict[str, Any]:
    proc = world.processes.get(pid)
    if proc is None or not proc.alive:
        return {"ok": False, "code": 503, "pid": pid}
    return {"ok": True, "code": 200, "pid": pid}


def naive_rss_kill_set(world: World, n: int = 1) -> tuple[int, ...]:
    ranked = sorted(world.processes.values(), key=lambda p: p.rss, reverse=True)
    return tuple(p.pid for p in ranked[:n])


def shared_service_survives(world: World, run: Run, pid: int) -> bool:
    return pid not in run.kill_set
