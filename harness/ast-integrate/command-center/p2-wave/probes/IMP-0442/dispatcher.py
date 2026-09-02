"""Work-unit dispatcher that routes by declared execution_substrate.

local-serialized means a serial lock: observed simultaneity on that
substrate is at most one. The other three substrates may run in parallel.
A discrete-event dry run records a per-tick concurrent-count time-series.

The serial lock is a real gate on start(), not a post-hoc clip of the
readout. Removing it (serial_lock=False) is the contracted mutation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

FOUR_SUBSTRATES: tuple[str, ...] = (
    "local-serialized",
    "local-parallel",
    "worktree-isolated",
    "cloud-batch",
)

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


class DispatchError(ValueError):
    """Declared substrate is missing or not one of the four lanes."""


@dataclass(frozen=True)
class WorkUnit:
    id: str
    execution_substrate: str
    duration_ticks: int = 8
    ready_at: int = 0


@dataclass
class DispatchOpts:
    serial_lock: bool = True
    honor_declared_substrate: bool = True
    dump_substrate: str = "local-parallel"


@dataclass
class Running:
    unit: WorkUnit
    dest: str
    start: int
    end: int
    slot: str | None = None


@dataclass
class DispatchResult:
    units: list[WorkUnit]
    opts: DispatchOpts
    samples: list[dict[str, Any]]
    assignments: dict[str, str]
    peaks: dict[str, int]
    completed_ids: list[str]
    isolation_violations: list[dict[str, str]]
    worktree_slot_collisions: int
    ticks: int

    def concurrent_series(self, substrate: str) -> list[int]:
        return [int((s.get("concurrent") or {}).get(substrate) or 0) for s in self.samples]

    def peak(self, substrate: str) -> int:
        return int(self.peaks.get(substrate) or 0)

    def serial_never_exceeds_one(self) -> bool:
        return max(self.concurrent_series("local-serialized") or [0]) <= 1

    def serial_flat_at_one(self) -> bool:
        series = self.concurrent_series("local-serialized")
        if not series:
            return False
        if max(series) != 1:
            return False
        if min(series) < 0:
            return False
        if any(v not in (0, 1) for v in series):
            return False
        return 1 in series

    def isolation_ok(self) -> bool:
        return not self.isolation_violations and self.worktree_slot_collisions == 0


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    target = path or (REPO / CATALOG_REL)
    return json.loads(target.read_text(encoding="utf-8"))


def catalog_units(catalog: dict[str, Any] | None = None) -> list[WorkUnit]:
    data = catalog if catalog is not None else load_catalog()
    rows = data.get("work_units") or []
    out: list[WorkUnit] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        uid = str(row.get("id") or "")
        sub = str(row.get("execution_substrate") or "")
        if not uid:
            continue
        out.append(WorkUnit(id=uid, execution_substrate=sub))
    return out


def census(units: Iterable[WorkUnit]) -> dict[str, int]:
    counts = {s: 0 for s in FOUR_SUBSTRATES}
    other = 0
    for u in units:
        if u.execution_substrate in counts:
            counts[u.execution_substrate] += 1
        else:
            other += 1
    counts["other"] = other
    return counts


def mixed_dry_run_units(
    n_per_substrate: int = 10,
    duration_ticks: int = 8,
    catalog: dict[str, Any] | None = None,
) -> list[WorkUnit]:
    """Forty-unit mixed catalog: ten units from each of the four substrates.

    All units arrive at tick 0 so local-serialized *would* overlap without
    the serial lock. IDs are taken from the live WORK-UNIT-CATALOG.
    """
    by_sub: dict[str, list[str]] = {s: [] for s in FOUR_SUBSTRATES}
    for u in catalog_units(catalog):
        if u.execution_substrate in by_sub:
            by_sub[u.execution_substrate].append(u.id)
    selected: list[WorkUnit] = []
    for sub in FOUR_SUBSTRATES:
        ids = sorted(by_sub[sub])
        if len(ids) < n_per_substrate:
            raise DispatchError(
                f"catalog has only {len(ids)} {sub} units; need {n_per_substrate}"
            )
        for uid in ids[:n_per_substrate]:
            selected.append(
                WorkUnit(
                    id=uid,
                    execution_substrate=sub,
                    duration_ticks=duration_ticks,
                    ready_at=0,
                )
            )
    return selected


def route(unit: WorkUnit, opts: DispatchOpts) -> str:
    if not opts.honor_declared_substrate:
        return opts.dump_substrate
    dest = unit.execution_substrate
    if dest not in FOUR_SUBSTRATES:
        raise DispatchError(
            f"{unit.id} declares execution_substrate={dest!r} "
            f"which is not one of {list(FOUR_SUBSTRATES)}"
        )
    return dest


def _can_start(dest: str, concurrent: dict[str, int], opts: DispatchOpts) -> bool:
    if dest == "local-serialized" and opts.serial_lock:
        return concurrent.get(dest, 0) < 1
    return True


def dispatch(units: list[WorkUnit], opts: DispatchOpts | None = None) -> DispatchResult:
    opts = opts or DispatchOpts()
    pending = list(units)
    inflight: list[Running] = []
    assignments: dict[str, str] = {}
    samples: list[dict[str, Any]] = []
    slot_seq = 0
    tick = 0
    max_ticks = max((u.ready_at + u.duration_ticks for u in units), default=1) * (
        len(units) + 2
    )

    def concurrent_now() -> dict[str, int]:
        c = {s: 0 for s in FOUR_SUBSTRATES}
        for r in inflight:
            c[r.dest] = c.get(r.dest, 0) + 1
        return c

    while tick <= max_ticks:
        inflight = [r for r in inflight if r.end > tick]
        conc = concurrent_now()
        progressed = True
        while progressed:
            progressed = False
            for u in list(pending):
                if u.ready_at > tick:
                    continue
                dest = route(u, opts)
                if not _can_start(dest, conc, opts):
                    continue
                slot = None
                if dest == "worktree-isolated":
                    slot = f"wt-{slot_seq}"
                    slot_seq += 1
                inflight.append(
                    Running(
                        unit=u,
                        dest=dest,
                        start=tick,
                        end=tick + u.duration_ticks,
                        slot=slot,
                    )
                )
                assignments[u.id] = dest
                pending.remove(u)
                conc[dest] = conc.get(dest, 0) + 1
                progressed = True
        slots = [r.slot for r in inflight if r.slot]
        samples.append(
            {
                "tick": tick,
                "concurrent": dict(conc),
                "running_ids": [r.unit.id for r in inflight],
                "running_dest": [r.dest for r in inflight],
                "worktree_slots": list(slots),
            }
        )
        if not pending and not inflight:
            break
        tick += 1

    peaks = {s: 0 for s in FOUR_SUBSTRATES}
    for sample in samples:
        for sub, n in (sample.get("concurrent") or {}).items():
            peaks[sub] = max(peaks.get(sub, 0), int(n))

    violations: list[dict[str, str]] = []
    for u in units:
        dest = assignments.get(u.id)
        if dest is None:
            violations.append(
                {"unit_id": u.id, "declared": u.execution_substrate, "routed": "<never>"}
            )
        elif dest != u.execution_substrate:
            violations.append(
                {"unit_id": u.id, "declared": u.execution_substrate, "routed": dest}
            )

    slot_collisions = 0
    for sample in samples:
        slots = list(sample.get("worktree_slots") or [])
        if len(slots) != len(set(slots)):
            slot_collisions += 1

    completed = [u.id for u in units if u.id in assignments]
    return DispatchResult(
        units=list(units),
        opts=opts,
        samples=samples,
        assignments=assignments,
        peaks=peaks,
        completed_ids=completed,
        isolation_violations=violations,
        worktree_slot_collisions=slot_collisions,
        ticks=tick + 1,
    )


def isolation_per_substrate(result: DispatchResult) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for sub in FOUR_SUBSTRATES:
        declared = [u.id for u in result.units if u.execution_substrate == sub]
        routed_here = [uid for uid, dest in result.assignments.items() if dest == sub]
        foreign = [uid for uid in routed_here if uid not in declared]
        missing = [uid for uid in declared if uid not in routed_here]
        report[sub] = {
            "declared_count": len(declared),
            "routed_count": len(routed_here),
            "foreign_ids": foreign,
            "missing_ids": missing,
            "isolated": not foreign and not missing,
        }
    return report


def compact_series(result: DispatchResult) -> list[dict[str, Any]]:
    """Keep a sample when concurrent counts change, plus the first and last ticks."""
    out: list[dict[str, Any]] = []
    prev: dict[str, int] | None = None
    for i, sample in enumerate(result.samples):
        conc = dict(sample.get("concurrent") or {})
        last = i == len(result.samples) - 1
        if prev is None or conc != prev or last:
            out.append({"tick": sample["tick"], "concurrent": conc})
            prev = conc
    return out


def summary(result: DispatchResult) -> dict[str, Any]:
    return {
        "unit_count": len(result.units),
        "substrates_present": sorted(
            {u.execution_substrate for u in result.units}
        ),
        "peaks": dict(result.peaks),
        "serial_never_exceeds_one": result.serial_never_exceeds_one(),
        "serial_flat_at_one": result.serial_flat_at_one(),
        "serial_series": result.concurrent_series("local-serialized"),
        "isolation_ok": result.isolation_ok(),
        "isolation_violations": list(result.isolation_violations),
        "worktree_slot_collisions": result.worktree_slot_collisions,
        "isolation_per_substrate": isolation_per_substrate(result),
        "ticks": result.ticks,
        "serial_lock": result.opts.serial_lock,
        "honor_declared_substrate": result.opts.honor_declared_substrate,
        "completed": len(result.completed_ids),
    }
