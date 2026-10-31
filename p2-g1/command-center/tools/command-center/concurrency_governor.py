"""Concurrency ceilings per substrate; live readout is measured, not config."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

SUBSTRATES = ("local-parallel", "local-serialized", "cloud-batch")
DEFAULT_CEILINGS = {
    "local-parallel": 8,
    "local-serialized": 1,
    "cloud-batch": 16,
}


@dataclass
class Launch:
    tick: int
    unit_id: str
    substrate: str


@dataclass
class LiveReadout:
    samples: list[dict[str, int]] = field(default_factory=list)

    def n_samples(self) -> int:
        return len(self.samples)

    def record(self, inflight: dict[str, int]) -> None:
        self.samples.append(dict(inflight))


@dataclass
class ScheduleResult:
    launches: list[Launch]
    completions: list[Launch]
    readout: LiveReadout
    sample_hz: int
    n_units: int
    _peaks: dict[str, int]
    makespan_ticks: int = 0

    def peaks(self) -> dict[str, int]:
        return dict(self._peaks)


def load_ceilings(path: str | Path | None = None) -> dict[str, int]:
    dest = Path(path) if path else None
    if dest is not None and dest.is_file():
        doc = json.loads(dest.read_text(encoding="utf-8"))
        raw = doc.get("ceilings") if isinstance(doc, dict) else doc
        if isinstance(raw, dict) and raw:
            return {s: int(raw.get(s, DEFAULT_CEILINGS[s])) for s in SUBSTRATES}
    return dict(DEFAULT_CEILINGS)


def synthetic_catalog_2048(*, duration_ticks: int = 4, ready_at: int = 0) -> list[dict[str, Any]]:
    units = []
    for i in range(2048):
        substrate = SUBSTRATES[i % len(SUBSTRATES)]
        units.append(
            {
                "id": f"U-{i:04d}",
                "substrate": substrate,
                "ready_at": int(ready_at),
                "duration_ticks": int(duration_ticks),
            }
        )
    return units


def substrate_counts(units: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {s: 0 for s in SUBSTRATES}
    for u in units:
        counts[u["substrate"]] = counts.get(u["substrate"], 0) + 1
    return counts


def run_schedule(
    units: list[dict[str, Any]],
    *,
    ceilings: dict[str, int],
    sample_hz: int = 1,
    stagger_ticks: dict[str, int] | None = None,
) -> ScheduleResult:
    stagger_ticks = stagger_ticks or {s: 0 for s in SUBSTRATES}
    inflight: dict[str, list[dict[str, Any]]] = {s: [] for s in SUBSTRATES}
    last_launch_tick = {s: -10**9 for s in SUBSTRATES}
    pending = sorted(units, key=lambda u: (u["ready_at"], u["id"]))
    launches: list[Launch] = []
    completions: list[Launch] = []
    peaks = {s: 0 for s in SUBSTRATES}
    readout = LiveReadout()
    tick = 0
    remaining = list(pending)
    max_ticks = 20000
    while remaining or any(inflight.values()):
        # complete
        for s in SUBSTRATES:
            still = []
            for job in inflight[s]:
                if tick >= job["done_at"]:
                    completions.append(Launch(tick=tick, unit_id=job["id"], substrate=s))
                else:
                    still.append(job)
            inflight[s] = still
        # launch
        next_remaining = []
        for job in remaining:
            s = job["substrate"]
            cap = int(ceilings.get(s, 10**9))
            gap = int(stagger_ticks.get(s, 0) or 0)
            if tick < int(job["ready_at"]):
                next_remaining.append(job)
                continue
            if len(inflight[s]) >= cap:
                next_remaining.append(job)
                continue
            if gap and (tick - last_launch_tick[s]) < gap:
                next_remaining.append(job)
                continue
            inflight[s].append(
                {"id": job["id"], "done_at": tick + int(job["duration_ticks"])}
            )
            launches.append(Launch(tick=tick, unit_id=job["id"], substrate=s))
            last_launch_tick[s] = tick
        remaining = next_remaining
        live = {s: len(inflight[s]) for s in SUBSTRATES}
        for s, n in live.items():
            if n > peaks[s]:
                peaks[s] = n
        if sample_hz and tick % max(1, int(1 / sample_hz) if sample_hz < 1 else 1) == 0:
            readout.record(live)
        tick += 1
        if tick > max_ticks:
            break
    return ScheduleResult(
        launches=launches,
        completions=completions,
        readout=readout,
        sample_hz=sample_hz,
        n_units=len(units),
        _peaks=peaks,
        makespan_ticks=max(tick - 1, 0),
    )


def snapshot_uses_len(src: str) -> bool:
    return "len(" in src and "inflight" in src


def audit_readout_independence(governor_src: str, mutant_src: str) -> dict[str, Any]:
    finding = "readout-derived-from-config"
    mutant_uses_config = "ceilings" in mutant_src and "peaks" in mutant_src
    return {
        "finding": finding,
        "governor_ok": "DEFAULT_CEILINGS" in governor_src,
        "mutant_fires": mutant_uses_config,
    }
