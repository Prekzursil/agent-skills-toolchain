#!/usr/bin/env python3
"""Arrival-staggered confirmation scheduler with per-unit pipelines.

Discrete-event simulated time. A hung unit occupies one slot until TIMEOUT
and is not a global barrier. Per-vendor token waits keep arrivals inside the
declared cap (SimulatedVendor records 0 x 429 at the configured rate). A
provider 529 retries without lowering concurrency.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "cohort.json"
FORBIDDEN_REDUCE = (
    "reduce_concurrency",
    "shrink_pool",
    "lower_parallelism",
    "cut_concurrency",
    "reduce concurrency",
)


@dataclass(frozen=True)
class SchedulerConfig:
    concurrency: int = 4
    stagger_s: float = 0.06
    per_unit_timeout_s: float = 0.5
    healthy_work_s: float = 0.01
    vendor_min_interval_s: float = 0.05
    retry_529_s: float = 0.02
    histogram_bin_s: float = 0.05


@dataclass
class Job:
    unit_id: str
    vendor: str
    hung: bool = False
    inject_529: bool = False
    already_got_529: bool = False
    not_before: float = 0.0
    queued_at: float = 0.0


@dataclass
class Inflight:
    job: Job
    start_t: float
    finish_t: float
    is_timeout: bool


@dataclass
class TerminalRow:
    unit_id: str
    vendor: str
    terminal_state: str
    queued_at_s: float
    started_at_s: float
    finished_at_s: float
    blank: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "vendor": self.vendor,
            "terminal_state": self.terminal_state,
            "queued_at_s": round(self.queued_at_s, 9),
            "started_at_s": round(self.started_at_s, 9),
            "finished_at_s": round(self.finished_at_s, 9),
            "blank": False,
        }


@dataclass
class RunResult:
    mode: str
    config: SchedulerConfig
    terminals: list[TerminalRow]
    rejections: Counter
    arrivals: list[tuple[str, str, float]]
    actions: list[dict[str, Any]]
    concurrency_cap_start: int
    concurrency_cap_end: int
    started_ids: list[str] = field(default_factory=list)

    @property
    def concurrency_reductions(self) -> int:
        n = 0
        last = self.concurrency_cap_start
        for act in self.actions:
            cap = int(act["concurrency_cap"])
            if cap < last:
                n += 1
            last = cap
        if self.concurrency_cap_end < self.concurrency_cap_start:
            n += 1
        return n

    def forbidden_reduce_actions(self) -> int:
        n = 0
        for act in self.actions:
            name = str(act.get("action") or "").lower()
            if any(tok in name for tok in FORBIDDEN_REDUCE):
                n += 1
        return n


class SimulatedVendor:
    """Independent of the scheduler: 429 if arrivals beat min_interval."""

    def __init__(self, min_interval_s: float) -> None:
        self.min_interval_s = min_interval_s
        self.last_accept: dict[str, float] = {}

    def submit(self, vendor: str, t: float, inject_529: bool, already_got_529: bool) -> str:
        if inject_529 and not already_got_529:
            return "529"
        last = self.last_accept.get(vendor, -1e18)
        if t + 1e-12 < last + self.min_interval_s:
            return "429"
        self.last_accept[vendor] = t
        return "200"


def load_cohort(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    live = repo / "command-center/confirmation/CNF-0003-sampling-frame.json"
    if live.is_file():
        try:
            data = json.loads(live.read_text(encoding="utf-8"))
            jobs = _jobs_from_sampling_frame(data)
            if len(jobs) >= 3:
                return {
                    "source": "CNF-0003",
                    "path": "command-center/confirmation/CNF-0003-sampling-frame.json",
                    "present": True,
                    "cohort_size": len(jobs),
                    "note": (
                        "Loaded live CNF-0003 sampling frame; hung/529 flags "
                        "applied for CNF-0011 controls."
                    ),
                    "jobs": jobs,
                }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            pass
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    jobs = [
        Job(
            unit_id=str(row["id"]),
            vendor=str(row["vendor"]),
            hung=bool(row.get("hung")),
            inject_529=bool(row.get("inject_529")),
        )
        for row in fixture["units"]
    ]
    return {
        "source": "fixture",
        "path": "command-center/p2-wave/probes/CNF-0011/fixtures/cohort.json",
        "present": False,
        "cohort_size": len(jobs),
        "note": fixture["note"],
        "jobs": jobs,
    }


def _jobs_from_sampling_frame(data: dict[str, Any]) -> list[Job]:
    raw = data.get("drawn_ids") or data.get("sample") or data.get("units") or []
    jobs: list[Job] = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            uid = item
            vendor = "anthropic" if i % 3 else "openai"
            hung = inject = False
        elif isinstance(item, dict):
            uid = str(item.get("id") or item.get("unit_id") or f"S{i:02d}")
            vendor = str(item.get("vendor") or ("anthropic" if i % 3 else "openai"))
            hung = bool(item.get("hung"))
            inject = bool(item.get("inject_529"))
        else:
            continue
        jobs.append(Job(unit_id=uid, vendor=vendor, hung=hung, inject_529=inject))
    if jobs and not any(j.hung for j in jobs):
        jobs[min(3, len(jobs) - 1)].hung = True
    if jobs and not any(j.inject_529 for j in jobs):
        for j in jobs:
            if not j.hung:
                j.inject_529 = True
                break
    return jobs


def clone_jobs(jobs: list[Job]) -> list[Job]:
    return [
        Job(unit_id=j.unit_id, vendor=j.vendor, hung=j.hung, inject_529=j.inject_529)
        for j in jobs
    ]


def arrival_histogram(
    arrivals: list[tuple[str, str, float]], bin_s: float
) -> list[dict[str, Any]]:
    if not arrivals:
        return [{"bin_start_s": 0.0, "bin_end_s": bin_s, "arrivals": 0}]
    times = [a[2] for a in arrivals]
    max_t = max(times)
    n_bins = max(1, int(max_t / bin_s) + 1)
    counts = [0] * n_bins
    for t in times:
        counts[min(int(t / bin_s), n_bins - 1)] += 1
    return [
        {
            "bin_start_s": round(i * bin_s, 9),
            "bin_end_s": round((i + 1) * bin_s, 9),
            "arrivals": c,
        }
        for i, c in enumerate(counts)
    ]


def run_scheduler(
    jobs: list[Job],
    config: SchedulerConfig | None = None,
    *,
    mode: str = "configured",
    resume_completed: set[str] | None = None,
    stop_after_n_terminals: int | None = None,
) -> RunResult:
    cfg = config or SchedulerConfig()
    if cfg.concurrency < 2:
        raise ValueError("concurrency must be >= 2 so a hung slot cannot be a global barrier")
    pending = [j for j in clone_jobs(jobs) if j.unit_id not in set(resume_completed or ())]
    vendor = SimulatedVendor(cfg.vendor_min_interval_s)
    inflight: list[Inflight] = []
    terminals: list[TerminalRow] = []
    actions: list[dict[str, Any]] = []
    arrivals: list[tuple[str, str, float]] = []
    started_ids: list[str] = []
    rejections: Counter = Counter()
    t = 0.0
    last_dispatch = -1e18
    vendor_next_ok: dict[str, float] = defaultdict(float)
    cap = cfg.concurrency
    steps = 0

    def log(action: str, unit_id: str = "", detail: str = "") -> None:
        row: dict[str, Any] = {
            "t_s": round(t, 9),
            "action": action,
            "concurrency_cap": cap,
        }
        if unit_id:
            row["unit_id"] = unit_id
        if detail:
            row["detail"] = detail
        actions.append(row)

    def finish_due() -> None:
        keep: list[Inflight] = []
        for fl in inflight:
            if fl.finish_t <= t + 1e-15:
                state = "TIMEOUT" if fl.is_timeout else "SUCCESS"
                if state == "TIMEOUT":
                    rejections["timeout"] += 1
                terminals.append(
                    TerminalRow(
                        unit_id=fl.job.unit_id,
                        vendor=fl.job.vendor,
                        terminal_state=state,
                        queued_at_s=fl.job.queued_at,
                        started_at_s=fl.start_t,
                        finished_at_s=fl.finish_t,
                    )
                )
                log("terminal_" + state.lower(), fl.job.unit_id)
            else:
                keep.append(fl)
        inflight[:] = keep

    def can_consider(job: Job) -> bool:
        if t + 1e-15 < job.not_before:
            return False
        if mode != "burst" and t + 1e-15 < last_dispatch + cfg.stagger_s:
            return False
        if mode != "burst" and t + 1e-15 < vendor_next_ok[job.vendor]:
            return False
        return True

    def dispatch_one() -> bool:
        nonlocal last_dispatch
        if len(inflight) >= cap:
            return False
        idx = next((i for i, job in enumerate(pending) if can_consider(job)), None)
        if idx is None:
            return False
        job = pending.pop(idx)
        status = vendor.submit(job.vendor, t, job.inject_529, job.already_got_529)
        if status == "529":
            rejections["529"] += 1
            job.already_got_529 = True
            job.not_before = t + cfg.retry_529_s
            pending.insert(idx, job)
            log(
                "retry_after_529_concurrency_unchanged",
                job.unit_id,
                detail="provider-overload; concurrency cap not reduced",
            )
            return True
        if status == "429":
            rejections["429"] += 1
            last_acc = vendor.last_accept.get(job.vendor, t)
            job.not_before = max(t, last_acc) + cfg.vendor_min_interval_s
            pending.append(job)
            log("vendor_429_requeue", job.unit_id)
            return True
        last_dispatch = t
        vendor_next_ok[job.vendor] = t + cfg.vendor_min_interval_s
        arrivals.append((job.unit_id, job.vendor, t))
        started_ids.append(job.unit_id)
        if job.hung:
            inflight.append(
                Inflight(
                    job=job,
                    start_t=t,
                    finish_t=t + cfg.per_unit_timeout_s,
                    is_timeout=True,
                )
            )
            log("start_hung", job.unit_id)
        else:
            inflight.append(
                Inflight(
                    job=job,
                    start_t=t,
                    finish_t=t + cfg.healthy_work_s,
                    is_timeout=False,
                )
            )
            log("start_ok", job.unit_id)
        return True

    def next_time() -> float | None:
        cand: list[float] = []
        for fl in inflight:
            if fl.finish_t > t + 1e-15:
                cand.append(fl.finish_t)
        if pending and len(inflight) < cap:
            stagger_ready = 0.0 if mode == "burst" else last_dispatch + cfg.stagger_s
            for job in pending:
                ready = max(job.not_before, t)
                if mode != "burst":
                    ready = max(ready, stagger_ready, vendor_next_ok[job.vendor])
                if ready > t + 1e-15:
                    cand.append(ready)
        if cand:
            return min(cand)
        if pending and len(inflight) >= cap:
            finishes = [fl.finish_t for fl in inflight if fl.finish_t > t + 1e-15]
            return min(finishes) if finishes else None
        if pending:
            extra: list[float] = []
            for job in pending:
                extra.append(job.not_before)
                if mode != "burst":
                    extra.append(last_dispatch + cfg.stagger_s)
                    extra.append(vendor_next_ok[job.vendor])
            future = [x for x in extra if x > t + 1e-15]
            return min(future) if future else None
        return None

    log("run_start", detail=mode)
    while pending or inflight:
        steps += 1
        if steps > 100000:
            raise RuntimeError("scheduler exceeded step bound (deadlock)")
        finish_due()
        if stop_after_n_terminals is not None and len(terminals) >= stop_after_n_terminals:
            break
        while dispatch_one():
            finish_due()
            if stop_after_n_terminals is not None and len(terminals) >= stop_after_n_terminals:
                break
        if stop_after_n_terminals is not None and len(terminals) >= stop_after_n_terminals:
            break
        if not pending and not inflight:
            break
        nxt = next_time()
        if nxt is None:
            finish_due()
            if pending or inflight:
                raise RuntimeError(
                    f"deadlock t={t} pending={[j.unit_id for j in pending]} inflight={len(inflight)}"
                )
            break
        if nxt <= t + 1e-15:
            raise RuntimeError(f"time did not advance t={t} nxt={nxt}")
        t = nxt

    log("run_end", detail=mode)
    rejections.setdefault("429", 0)
    rejections.setdefault("529", 0)
    rejections.setdefault("timeout", 0)
    return RunResult(
        mode=mode,
        config=cfg,
        terminals=terminals,
        rejections=rejections,
        arrivals=arrivals,
        actions=actions,
        concurrency_cap_start=cfg.concurrency,
        concurrency_cap_end=cap,
        started_ids=started_ids,
    )


def hung_proof(result: RunResult) -> dict[str, Any]:
    hung_rows = [r for r in result.terminals if r.terminal_state == "TIMEOUT"]
    if len(hung_rows) != 1:
        raise AssertionError(f"expected exactly one TIMEOUT hung unit, got {len(hung_rows)}")
    hung = hung_rows[0]
    survivors = [r for r in result.terminals if r.unit_id != hung.unit_id]
    before = [r for r in survivors if r.finished_at_s + 1e-15 < hung.finished_at_s]
    if not survivors or not before:
        raise AssertionError(
            "survivors did not finish before hung timeout; looks like a global barrier"
        )
    if any(r.blank or not r.terminal_state for r in result.terminals):
        raise AssertionError("blank terminal row")
    if len(result.terminals) < 3:
        raise AssertionError("cohort too small")
    return {
        "injected_unit_id": hung.unit_id,
        "hung_terminal_state": "TIMEOUT",
        "surviving_cohort_size": len(survivors),
        "surviving_completed": len(survivors),
        "survivors_finished_before_hung_timeout": len(before),
        "barrier_kind": "per-unit-pipeline",
        "global_barrier_refuted": True,
    }


def rate_caps(cfg: SchedulerConfig, vendors: set[str]) -> dict[str, Any]:
    rps = 1.0 / cfg.vendor_min_interval_s
    return {
        v: {
            "max_arrivals_per_second": rps,
            "min_interval_seconds": cfg.vendor_min_interval_s,
        }
        for v in sorted(vendors)
    }


def artifact_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report for schema; probes accept either layout."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged: dict[str, Any] = dict(report)
    for key, value in doc.items():
        if key != "report":
            merged[key] = value
    return merged
