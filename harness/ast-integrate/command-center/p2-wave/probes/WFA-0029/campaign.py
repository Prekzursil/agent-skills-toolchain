"""Measured campaign for WFA-0029: both-states, resume, histogram, provider 429s, lint."""
from __future__ import annotations

import random
import tempfile
from pathlib import Path
from typing import Any

from acquire import credentialed_call
from lint_call_sites import evaluate as lint_evaluate
from mock_provider import ProviderSurface
from scheduler import Scheduler, VirtualClock, load_config, max_in_window

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONFIG_PATH = HERE / "providers.json"


def _spec(tpm: float, jitter: float = 0.0, cap: float = 1.0, inflight: int = 1) -> dict:
    return {
        "tokens_per_minute": tpm,
        "burst_capacity": cap,
        "jitter_seconds": jitter,
        "max_inflight": inflight,
    }


def both_states_rate() -> dict[str, Any]:
    """1/min actually waits ~60s (virtual); 1000/min does not (wait << 1s)."""
    clock_lo = VirtualClock()
    sched_lo = Scheduler({"p": _spec(1.0, jitter=0.0)}, clock=clock_lo, rng=random.Random(29))
    a1 = sched_lo.admit("p")
    snap_held = sched_lo.gate("p").snapshot()
    a1.release()
    snap_after = sched_lo.gate("p").snapshot()
    a2 = sched_lo.admit("p")
    wait_1_per_min = a2.waited_seconds
    a2.release()

    clock_hi = VirtualClock()
    sched_hi = Scheduler(
        {"p": _spec(1000.0, jitter=0.0)}, clock=clock_hi, rng=random.Random(29)
    )
    b1 = sched_hi.admit("p")
    b1.release()
    b2 = sched_hi.admit("p")
    wait_1000_per_min = b2.waited_seconds
    b2.release()

    # Logical count vs simultaneous concurrency stay distinct after one admit.
    concurrency_held_exhausted = snap_held["concurrency_available"] is False
    tokens_held_exhausted = snap_held["tokens_available"] is False
    concurrency_freed_after_release = snap_after["concurrency_available"] is True
    tokens_still_exhausted_after_release = snap_after["tokens_available"] is False

    blocks = wait_1_per_min >= 59.0
    does_not_block = wait_1000_per_min < 1.0
    return {
        "wait_1_per_min": wait_1_per_min,
        "wait_1000_per_min": wait_1000_per_min,
        "blocks_at_1_per_min": blocks,
        "does_not_block_at_1000_per_min": does_not_block,
        "logical_vs_concurrency": {
            "while_lease_held": {
                "concurrency_available": snap_held["concurrency_available"],
                "tokens_available": snap_held["tokens_available"],
            },
            "after_release_tokens_not_refilled": {
                "concurrency_available": snap_after["concurrency_available"],
                "tokens_available": snap_after["tokens_available"],
            },
            "separated": bool(
                concurrency_held_exhausted
                and tokens_held_exhausted
                and concurrency_freed_after_release
                and tokens_still_exhausted_after_release
            ),
        },
        "pass": bool(
            blocks
            and does_not_block
            and concurrency_held_exhausted
            and tokens_held_exhausted
            and concurrency_freed_after_release
            and tokens_still_exhausted_after_release
        ),
    }


def resume_test(tmp: Path) -> dict[str, Any]:
    """Kill mid-job: inflight+queued survive on a new Scheduler."""
    qpath = tmp / "queue.json"
    clock = VirtualClock()
    cfg = {"github": _spec(1000.0, jitter=0.0)}
    surface = ProviderSurface("github", 1000, clock)
    sched = Scheduler(cfg, clock=clock, rng=random.Random(29), queue_path=qpath)
    ids = [f"j{i}" for i in range(5)]
    for jid in ids:
        sched.queue.enqueue(jid, "github", {"id": jid})

    def transport(job: dict[str, Any]) -> dict[str, Any]:
        return surface.handle(job)

    sched.drain(transport, stop_after=2)
    done_before = sched.queue.ids("done")
    pending_before_crash = [j["id"] for j in sched.queue.pending()]
    crash_id = pending_before_crash[0]
    sched.drain(transport, crash_before_complete_id=crash_id)
    inflight_on_disk = json_jobs(qpath)

    sched2 = Scheduler(cfg, clock=VirtualClock(clock.now()), rng=random.Random(7), queue_path=qpath)
    recovered = [j["id"] for j in sched2.queue.pending()]
    recovered_flags = [
        bool(j.get("recovered_from_inflight")) for j in sched2.queue.jobs if j["id"] == crash_id
    ]
    lost = [i for i in ids if i not in sched2.queue.ids()]
    sched2.drain(transport)
    done_after = sched2.queue.ids("done")
    return {
        "enqueued": ids,
        "done_before_kill": done_before,
        "crash_id": crash_id,
        "disk_after_kill": inflight_on_disk,
        "recovered_pending": recovered,
        "crash_recovered_from_inflight": any(recovered_flags),
        "lost_ids": lost,
        "done_after_resume": done_after,
        "all_done": set(done_after) == set(ids),
        "pass": (not lost) and set(done_after) == set(ids) and any(recovered_flags),
    }


def json_jobs(path: Path) -> list[dict[str, Any]]:
    import json

    return list(json.loads(path.read_text(encoding="utf-8")).get("jobs") or [])


def dry_run() -> dict[str, Any]:
    """Scheduled vs naive burst against an independent provider limiter."""
    tpm = 10
    n = 20
    clock = VirtualClock()
    cfg = {
        "github": _spec(float(tpm), jitter=0.0),
        "exa": _spec(5.0, jitter=0.0),
    }
    sched = Scheduler(cfg, clock=clock, rng=random.Random(29))
    github = ProviderSurface("github", tpm, clock)
    exa = ProviderSurface("exa", 5, clock)
    surfaces = {"github": github, "exa": exa}

    def transport_for(name: str):
        def _t(req: dict[str, Any]) -> dict[str, Any]:
            return surfaces[name].handle(req)

        return _t

    scheduled_resps = []
    for i in range(n):
        scheduled_resps.append(
            credentialed_call("github", transport_for("github"), {"i": i}, sched)
        )
    for i in range(8):
        credentialed_call("exa", transport_for("exa"), {"i": i}, sched)

    hist = sched.arrival_histogram()
    sched_github_429 = github.http_429
    sched_github_200 = github.http_200

    # Independent naive herd on a FRESH surface (same limit, own clock instant).
    naive_clock = VirtualClock()
    naive = ProviderSurface("github", tpm, naive_clock)
    naive_resps = naive.burst_unscheduled(n)
    naive_429 = naive.http_429
    naive_200 = naive.http_200

    scheduler_within = all(row["within_configured_rate"] for row in hist.values() if row["n"])
    provider_throttled_scheduled = sched_github_429 > 0 or exa.http_429 > 0
    detector_failure = bool(scheduler_within and provider_throttled_scheduled)
    if detector_failure:
        winner = "provider"
        compliance = False
    elif provider_throttled_scheduled:
        winner = "provider"
        compliance = False
    else:
        winner = "agree"
        compliance = bool(scheduler_within)

    gh_max = hist["github"]["max_in_window_s60"]
    exa_max = hist["exa"]["max_in_window_s60"]
    call_count_matches = sched_github_200 + sched_github_429 == n

    # Retry through scheduler: one planted 503 then 200.
    retry_clock = VirtualClock()
    retry_sched = Scheduler({"github": _spec(1000.0, jitter=0.0)}, clock=retry_clock)
    retry_surface = ProviderSurface("github", 1000, retry_clock)
    retry_surface.plant_one_503()
    retry_resp = credentialed_call(
        "github", retry_surface.handle, {"k": "retry"}, retry_sched, max_attempts=3
    )
    retry_ok = (
        retry_resp.get("status") == 200
        and int(retry_resp.get("attempts") or 0) == 2
        and retry_sched.gate("github").logical_count == 2
    )

    return {
        "scheduled": {
            "n_github": n,
            "n_exa": 8,
            "histogram": hist,
            "github_max_in_window": gh_max,
            "exa_max_in_window": exa_max,
            "github_provider": github.report(),
            "exa_provider": exa.report(),
            "within_configured_rate": scheduler_within,
            "call_count_matches_jobs": call_count_matches,
        },
        "naive_burst": {
            "n": n,
            "http_200": naive_200,
            "http_429": naive_429,
            "produced_429s": naive_429 > 0,
            "sample_429_headers": naive.report()["sample_429_headers"],
            "statuses": [r.get("status") for r in naive_resps],
        },
        "detector": {
            "scheduler_within_rate": scheduler_within,
            "provider_429_on_scheduled_path": provider_throttled_scheduled,
            "detector_failure": detector_failure,
            "winner": winner,
            "compliance": compliance,
            "rule": (
                "If the scheduler reports compliance while the provider reports "
                "throttling, the provider counter wins."
            ),
        },
        "retry_through_scheduler": {
            "status": retry_resp.get("status"),
            "attempts": retry_resp.get("attempts"),
            "admits": retry_sched.gate("github").logical_count,
            "pass": retry_ok,
        },
        "pass": bool(
            compliance
            and not detector_failure
            and naive_429 > 0
            and sched_github_429 == 0
            and gh_max <= tpm
            and exa_max <= 5
            and call_count_matches
            and retry_ok
        ),
    }


def token_never_negative(n: int = 40, tpm: float = 10.0) -> dict[str, Any]:
    clock = VirtualClock()
    sched = Scheduler({"p": _spec(tpm, jitter=0.0)}, clock=clock)
    saw_negative = False
    waits = []
    for _ in range(n):
        adm = sched.admit("p")
        waits.append(adm.waited_seconds)
        if adm.tokens_after < -1e-9:
            saw_negative = True
        adm.release()
    mx = max_in_window(sched.gate("p").arrivals)
    return {
        "n": n,
        "negative": saw_negative,
        "max_in_window": mx,
        "limit": tpm,
        "pass": (not saw_negative) and mx <= tpm,
    }


def fingerprint(campaign: dict[str, Any]) -> dict[str, Any]:
    d = campaign["dry_run"]
    b = campaign["both_states"]
    r = campaign["resume"]
    l = campaign["lint"]
    return {
        "wait_1_per_min_ge_59": b["wait_1_per_min"] >= 59.0,
        "wait_1000_per_min_lt_1": b["wait_1000_per_min"] < 1.0,
        "resume_lost": len(r["lost_ids"]),
        "resume_all_done": r["all_done"],
        "github_max": d["scheduled"]["github_max_in_window"],
        "exa_max": d["scheduled"]["exa_max_in_window"],
        "sched_github_429": d["scheduled"]["github_provider"]["http_429"],
        "naive_429": d["naive_burst"]["http_429"],
        "detector_failure": d["detector"]["detector_failure"],
        "winner": d["detector"]["winner"],
        "lint_pass": l["pass"],
        "tokens_ok": campaign["token_bucket"]["pass"],
    }


def run_campaign(tmp: Path | None = None) -> dict[str, Any]:
    own_tmp = tmp is None
    if tmp is None:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="wfa0029-")
        tmp = Path(tmp_ctx.name)
    else:
        tmp_ctx = None
    try:
        both = both_states_rate()
        resume = resume_test(tmp)
        dry = dry_run()
        lint = lint_evaluate(REPO)
        tokens = token_never_negative()
        tests = [
            {
                "id": "both-states-rate",
                "required": (
                    "set a limit to 1/min and confirm the scheduler actually "
                    "blocks; set it to 1000/min and confirm it does not"
                ),
                "pass": both["pass"],
            },
            {
                "id": "resume-no-lost-work",
                "required": "a killed scheduler must not lose queued work",
                "pass": resume["pass"],
            },
            {
                "id": "call-site-lint",
                "required": (
                    "the scheduler must never be bypassable by a direct call - "
                    "a lint asserts every external call site routes through it"
                ),
                "pass": lint["pass"],
            },
            {
                "id": "histogram-within-rate",
                "required": (
                    "measured arrival histogram from a dry run showing no "
                    "provider exceeds its configured rate"
                ),
                "pass": dry["scheduled"]["within_configured_rate"] and dry["pass"],
            },
            {
                "id": "provider-429-independent",
                "required": (
                    "providers' own 429 counters and rate-limit headers; "
                    "provider wins on disagreement"
                ),
                "pass": (
                    dry["naive_burst"]["produced_429s"]
                    and not dry["detector"]["detector_failure"]
                    and dry["detector"]["winner"] in {"agree", "provider"}
                ),
            },
        ]
        ok = all(t["pass"] for t in tests) and tokens["pass"]
        campaign = {
            "both_states": both,
            "resume": resume,
            "dry_run": dry,
            "lint": lint,
            "token_bucket": tokens,
            "tests": tests,
            "config_path": "command-center/p2-wave/probes/WFA-0029/providers.json",
            "config": load_config(CONFIG_PATH),
            "ok": ok,
        }
        campaign["fingerprint"] = fingerprint(campaign)
        return campaign
    finally:
        if own_tmp and tmp_ctx is not None:
            tmp_ctx.cleanup()
