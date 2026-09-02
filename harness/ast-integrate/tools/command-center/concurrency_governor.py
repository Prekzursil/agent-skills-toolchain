"""Concurrency governor: per-substrate ceilings with a MEASURED live readout.

``ConcurrencyGovernor.can_admit`` is the only place that reads the ceilings.
The live readout (``ConcurrencyGovernor.live_counts`` = ``len(_running)`` per
substrate, ``LiveReadout.peak`` = max of recorded live counts) never touches
the configuration, so raising a ceiling is visible as a higher measured peak
and a zero-sample readout reads zero, not the ceiling.
``audit_readout_independence`` is the static check for that property: it
flags any readout method whose body reads a ceiling/config attribute.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

SUBSTRATES = ("local-parallel", "local-serialized", "cloud-batch")
DEFAULT_CEILINGS: dict[str, int] = {
    "local-parallel": 8,
    "local-serialized": 1,
    "cloud-batch": 16,
}
FINDING_DERIVED = "readout-derived-from-config"
FINDING_CONSTANT = "readout-returns-constant"
READOUT_METHODS = frozenset(
    {"peak", "peaks", "live_at", "live_counts", "sample", "snapshot", "readout"}
)
CONFIG_ATTR_MARKERS = ("ceiling", "config", "limit", "cap")


@dataclass
class Launch:
    """One admission or completion event."""

    tick: int
    unit_id: str
    substrate: str


@dataclass(frozen=True)
class Sample:
    """Live and queued counts per substrate observed at one tick."""

    tick: int
    live: dict[str, int]
    queued: dict[str, int]


@dataclass
class LiveReadout:
    """Measured simultaneity: every value here comes from recorded samples."""

    samples: list[Sample] = field(default_factory=list)

    def n_samples(self) -> int:
        return len(self.samples)

    def record(
        self,
        tick: int | Mapping[str, int],
        live: Mapping[str, int] | None = None,
        queued: Mapping[str, int] | None = None,
    ) -> Sample:
        """Record one sample. Legacy one-argument form: ``record(live)``."""
        if isinstance(tick, Mapping):
            live, tick = tick, len(self.samples)
        if live is None:
            raise TypeError("record() needs the live counts")
        sample = Sample(
            tick=int(tick),
            live={str(k): int(v) for k, v in live.items()},
            queued={str(k): int(v) for k, v in (queued or {}).items()},
        )
        self.samples.append(sample)
        return sample

    def substrates(self) -> list[str]:
        seen = list(SUBSTRATES)
        for s in self.samples:
            for key in s.live:
                if key not in seen:
                    seen.append(key)
        return seen

    def peak(self, substrate: str) -> int:
        """Highest live count ever recorded for ``substrate`` (0 if unseen)."""
        return max((s.live.get(substrate, 0) for s in self.samples), default=0)

    def peaks(self) -> dict[str, int]:
        return {sub: self.peak(sub) for sub in self.substrates()}

    def live_at(self, tick: int, substrate: str) -> int:
        """Live count in the last sample recorded at or before ``tick``."""
        value = 0
        for s in self.samples:
            if s.tick <= int(tick):
                value = s.live.get(substrate, 0)
            else:
                break
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_samples": self.n_samples(),
            "peaks": self.peaks(),
            "samples": [
                {"tick": s.tick, "live": dict(s.live), "queued": dict(s.queued)}
                for s in self.samples
            ],
        }


class ConcurrencyGovernor:
    """Admits jobs under per-substrate ceilings; reports what is running."""

    def __init__(
        self,
        ceilings: Mapping[str, int],
        stagger_ticks: Mapping[str, int] | None = None,
    ) -> None:
        self.ceilings: dict[str, int] = {str(k): int(v) for k, v in ceilings.items()}
        self.stagger_ticks: dict[str, int] = {
            str(k): int(v or 0) for k, v in (stagger_ticks or {}).items()
        }
        self._running: dict[str, list[dict[str, Any]]] = {s: [] for s in SUBSTRATES}
        self._last_launch: dict[str, int] = {}

    def live_counts(self) -> dict[str, int]:
        """Measured live simultaneity: the size of each running set."""
        return {substrate: len(jobs) for substrate, jobs in self._running.items()}

    def can_admit(self, substrate: str, tick: int) -> bool:
        """Admission reads the ceiling and the stagger; nothing else does."""
        running = self._running.setdefault(substrate, [])
        ceiling = self.ceilings.get(substrate)
        if ceiling is not None and len(running) >= ceiling:
            return False
        gap = self.stagger_ticks.get(substrate, 0)
        last = self._last_launch.get(substrate)
        if gap and last is not None and (tick - last) < gap:
            return False
        return True

    def admit(self, job: Mapping[str, Any], tick: int) -> Launch:
        substrate = str(job["substrate"])
        if not self.can_admit(substrate, tick):
            raise RuntimeError(f"{substrate} is at its ceiling at tick {tick}")
        self._running.setdefault(substrate, []).append(
            {"id": str(job["id"]), "done_at": tick + int(job.get("duration_ticks", 1))}
        )
        self._last_launch[substrate] = tick
        return Launch(tick=tick, unit_id=str(job["id"]), substrate=substrate)

    def retire(self, tick: int) -> list[Launch]:
        """Complete every running job whose duration has elapsed."""
        done: list[Launch] = []
        for substrate, jobs in self._running.items():
            still = []
            for job in jobs:
                if tick >= job["done_at"]:
                    done.append(Launch(tick=tick, unit_id=job["id"], substrate=substrate))
                else:
                    still.append(job)
            self._running[substrate] = still
        return done

    def busy(self) -> bool:
        return any(self._running.values())


@dataclass
class ScheduleResult:
    """Outcome of ``run_schedule``; peaks come from the readout, never config."""

    launches: list[Launch]
    completions: list[Launch]
    readout: LiveReadout
    ceilings: dict[str, int]
    sample_hz: float
    n_units: int
    makespan_ticks: int = 0
    _enforced: dict[str, int] = field(default_factory=dict, repr=False)

    def peaks(self) -> dict[str, int]:
        return self.readout.peaks()

    def held(self) -> bool:
        """True iff every measured peak stayed at or under the enforced ceiling."""
        enforced = self._enforced or self.ceilings
        return all(
            peak <= int(enforced.get(sub, 10**9)) for sub, peak in self.peaks().items()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_units": self.n_units,
            "sample_hz": self.sample_hz,
            "makespan_ticks": self.makespan_ticks,
            "ceilings": dict(self.ceilings),
            "peaks": self.peaks(),
            "held": self.held(),
            "n_launches": len(self.launches),
            "n_completions": len(self.completions),
            "n_samples": self.readout.n_samples(),
        }


def load_ceilings(path: str | Path | None = None) -> dict[str, int]:
    """Ceilings from the JSON config (``{"ceilings": {...}}`` or flat), else defaults."""
    dest = Path(path) if path else None
    if dest is not None and dest.is_file():
        doc = json.loads(dest.read_text(encoding="utf-8"))
        raw = doc.get("ceilings") if isinstance(doc, dict) and "ceilings" in doc else doc
        if isinstance(raw, dict) and raw:
            out = {s: int(raw.get(s, DEFAULT_CEILINGS[s])) for s in SUBSTRATES}
            for key, val in raw.items():
                if key not in out and isinstance(val, (int, float)):
                    out[str(key)] = int(val)
            return out
    return dict(DEFAULT_CEILINGS)


def synthetic_catalog_2048(*, duration_ticks: int = 4, ready_at: int = 0) -> list[dict[str, Any]]:
    """2048 units round-robined over the substrates, all ready at ``ready_at``."""
    return [
        {
            "id": f"U-{i:04d}",
            "substrate": SUBSTRATES[i % len(SUBSTRATES)],
            "ready_at": int(ready_at),
            "duration_ticks": int(duration_ticks),
        }
        for i in range(2048)
    ]


def substrate_counts(units: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {s: 0 for s in SUBSTRATES}
    for unit in units:
        sub = str(unit["substrate"])
        counts[sub] = counts.get(sub, 0) + 1
    return counts


def _sample_period(sample_hz: float) -> int:
    if not sample_hz or sample_hz <= 0:
        return 0
    return 1 if sample_hz >= 1 else max(1, int(round(1.0 / float(sample_hz))))


def run_schedule(
    units: list[dict[str, Any]],
    *,
    ceilings: Mapping[str, int],
    sample_hz: float = 1,
    stagger_ticks: Mapping[str, int] | None = None,
    max_ticks: int = 200_000,
) -> ScheduleResult:
    """Simulate admission tick by tick; one tick is one second of wall time."""
    governor = ConcurrencyGovernor(ceilings, stagger_ticks)
    readout = LiveReadout()
    period = _sample_period(sample_hz)
    remaining = sorted(units, key=lambda u: (int(u["ready_at"]), str(u["id"])))
    launches: list[Launch] = []
    completions: list[Launch] = []
    tick = 0
    while remaining or governor.busy():
        completions.extend(governor.retire(tick))
        deferred: list[dict[str, Any]] = []
        queued = {s: 0 for s in SUBSTRATES}
        for job in remaining:
            substrate = str(job["substrate"])
            if tick < int(job["ready_at"]) or not governor.can_admit(substrate, tick):
                deferred.append(job)
                queued[substrate] = queued.get(substrate, 0) + 1
                continue
            launches.append(governor.admit(job, tick))
        remaining = deferred
        if period and tick % period == 0:
            readout.record(tick, governor.live_counts(), queued)
        tick += 1
        if tick > max_ticks:
            raise RuntimeError(f"schedule did not drain within {max_ticks} ticks")
    return ScheduleResult(
        launches=launches,
        completions=completions,
        readout=readout,
        ceilings=dict(governor.ceilings),
        sample_hz=sample_hz,
        n_units=len(units),
        makespan_ticks=max(tick - 1, 0),
        _enforced=dict(governor.ceilings),
    )


def _self_attr_names(node: ast.AST) -> list[tuple[str, int]]:
    names: list[tuple[str, int]] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
            if sub.value.id in {"self", "cls"}:
                names.append((sub.attr, getattr(sub, "lineno", 0)))
        elif isinstance(sub, ast.Name):
            names.append((sub.id, getattr(sub, "lineno", 0)))
    return names


def _looks_like_config(name: str) -> bool:
    low = name.lower()
    return any(marker in low for marker in CONFIG_ATTR_MARKERS)


def _readout_methods(tree: ast.AST) -> list[tuple[str, ast.FunctionDef]]:
    found: list[tuple[str, ast.FunctionDef]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name in READOUT_METHODS:
                        found.append((node.name, item))
    return found


def snapshot_uses_len(src: str) -> bool:
    """True iff the live-count snapshot is the cardinality of a running set."""
    tree = ast.parse(src)
    for _cls, fn in _readout_methods(tree):
        if fn.name not in {"live_counts", "snapshot"}:
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "len":
                    return True
    return False


def audit_readout_independence(src: str, *, label: str = "<source>") -> list[dict[str, Any]]:
    """Static audit: readout methods must not read ceiling/config state.

    Returns one finding per offending method (``readout-derived-from-config``)
    plus ``readout-returns-constant`` for readouts that only return literals.
    An honest readout yields ``[]``.
    """
    tree = ast.parse(src)
    findings: list[dict[str, Any]] = []
    for cls_name, fn in _readout_methods(tree):
        offenders = sorted(
            {name for name, _ in _self_attr_names(fn) if _looks_like_config(name)}
        )
        if offenders:
            findings.append(
                {
                    "id": FINDING_DERIVED,
                    "label": label,
                    "class": cls_name,
                    "method": fn.name,
                    "line": fn.lineno,
                    "detail": f"{cls_name}.{fn.name} reads {offenders} instead of measured samples",
                }
            )
        returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None]
        if returns and all(isinstance(r.value, ast.Constant) for r in returns):
            findings.append(
                {
                    "id": FINDING_CONSTANT,
                    "label": label,
                    "class": cls_name,
                    "method": fn.name,
                    "line": fn.lineno,
                    "detail": f"{cls_name}.{fn.name} returns a literal, measuring nothing",
                }
            )
    return findings
