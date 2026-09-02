"""Domain models for taskwatch_monitor.

The core vocabulary shared by every sub-package:

TaskSpec         — one declarative task entry from the TOML registry.
TaskStatus       — the lifecycle verdict (includes first-class BLIND).
Provenance       — where an ETA came from (measured | prior | none).
ProgressSnapshot — one accepted record of the optional progress.json heartbeat.
EtaEstimate      — a p50/p90 seconds-remaining RANGE plus its provenance.
PollResult       — the uniform shape every source adapter's poll() returns.

Everything here is a plain, fully-typed dataclass/enum with no I/O so the whole
module is trivially unit-testable to 100% branch coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    """Lifecycle verdict for a monitored task.

    BLIND is first-class (grill S7): a poll/tool error keeps the last-known
    verdict alive with an age stamp — absence of signal is never rendered as
    ``DONE``.
    """

    PENDING = "pending"
    RUNNING = "running"
    STALLED = "stalled"
    DONE = "done"
    FAILED = "failed"
    BLIND = "blind"

    @classmethod
    def from_str(cls, value: str) -> "TaskStatus":
        """Parse a status string, defaulting to BLIND for anything unknown."""
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.BLIND


class Provenance(str, Enum):
    """Where an ETA estimate's numbers came from (grill S8)."""

    MEASURED = "measured"  # derived from live signal for THIS run
    PRIOR = "prior"  # derived from historical priors for this task-type
    NONE = "none"  # not estimable (e.g. unknown total, no progress yet)


@dataclass
class TaskSpec:
    """One declarative task from the registry: ``{id, adapter, parser, ...}``."""

    id: str
    adapter: str
    parser: str = ""
    eta_model: str = "linear-frac"
    notify: list[str] = field(default_factory=list)
    remediate: bool = False  # two-tier: opt-in per task (grill S3/G-3)
    task_type: str = ""  # history/prior key; defaults to adapter when empty
    config: dict[str, object] = field(default_factory=dict)

    @property
    def history_key(self) -> str:
        """The key under which priors are stored/looked up for this task."""
        return self.task_type or self.adapter

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "adapter": self.adapter,
            "parser": self.parser,
            "eta_model": self.eta_model,
            "notify": list(self.notify),
            "remediate": self.remediate,
            "task_type": self.history_key,
            "config": dict(self.config),
        }


@dataclass
class ProgressSnapshot:
    """One accepted record of the progress.json heartbeat (grill S5/S6).

    ``total`` is ``None`` when the job cannot know its denominator; callers must
    then show elapsed+rate and NOT a fake percentage (grill S8).
    """

    schema: str
    done: float
    total: float | None
    phase: str
    ts: float
    seq: int

    def fraction(self) -> float | None:
        """done/total as a raw fraction — NOT clamped to [0, 1] (grill S6a).

        Returns ``None`` when the total is unknown or non-positive. An overshoot
        (>1.0) is preserved so downstream ETA models can WIDEN their band rather
        than a hidden clamp masking that the model is off.
        """
        if self.total is None or self.total <= 0:
            return None
        return self.done / self.total

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "done": self.done,
            "total": self.total,
            "phase": self.phase,
            "ts": self.ts,
            "seq": self.seq,
            "fraction": self.fraction(),
        }


@dataclass
class EtaEstimate:
    """A seconds-remaining RANGE (p50/p90) plus provenance (grill S8).

    ``p50``/``p90`` are ``None`` together when the ETA is not estimable. When
    present, ``p90 >= p50`` by construction of every model in ``core.eta``.
    """

    p50: float | None
    p90: float | None
    provenance: Provenance

    @property
    def estimable(self) -> bool:
        return self.p50 is not None and self.p90 is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "p50": self.p50,
            "p90": self.p90,
            "provenance": self.provenance.value,
            "estimable": self.estimable,
        }


@dataclass
class PollResult:
    """Uniform result every source adapter's ``poll()`` returns (grill S5).

    The four load-bearing fields are ``exists``, ``mtime``, ``lines`` and
    ``liveness``; ``size``/``count`` carry the universal-liveness signals and
    ``error`` (when set) drives the BLIND state — never discards the last
    verdict.
    """

    exists: bool
    mtime: float | None
    lines: list[str] = field(default_factory=list)
    size: int | None = None
    count: int | None = None
    liveness: bool = False
    error: str | None = None
    raw: dict[str, object] = field(default_factory=dict)

    @property
    def blind(self) -> bool:
        """True when the poll itself failed — the caller must hold last verdict."""
        return self.error is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "exists": self.exists,
            "mtime": self.mtime,
            "line_count": len(self.lines),
            "size": self.size,
            "count": self.count,
            "liveness": self.liveness,
            "error": self.error,
            "blind": self.blind,
        }
