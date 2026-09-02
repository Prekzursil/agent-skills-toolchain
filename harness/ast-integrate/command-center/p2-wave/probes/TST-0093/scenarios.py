"""Live measurements for TST-0093: Retry-After, no duplicate work, no self-throttle."""
from __future__ import annotations

from clock import VirtualClock
from dispatcher import Dispatcher, RunResult
from mock_limiter import MockLimiter, Response

RETRY_AFTER_S = 5.0
STORM_RETRY_AFTER_S = 2.0
FALLBACK_S = 1.0
STORM_UNITS = [f"u{i:02d}" for i in range(8)]
STORM_CONCURRENCY = 4


def _gaps_after_429(events: list[dict[str, object]], unit_id: str) -> list[float]:
    rows = [e for e in events if e["unit_id"] == unit_id]
    gaps: list[float] = []
    for i, ev in enumerate(rows[:-1]):
        if int(ev["status"]) == 429:
            nxt = rows[i + 1]
            gaps.append(float(nxt["t"]) - float(ev["t"]))
    return gaps


def retry_after_case(*, honor: bool) -> dict[str, object]:
    clock = VirtualClock()
    mock = MockLimiter(clock)
    mock.set_plan(
        "unit-a",
        [
            Response(429, {"Retry-After": str(int(RETRY_AFTER_S))}),
            Response(200, {}),
        ],
    )
    disp = Dispatcher(
        mock,
        clock,
        concurrency=1,
        honor_retry_after=honor,
        fallback_backoff=FALLBACK_S,
    )
    result: RunResult = disp.run(["unit-a"])
    gaps = _gaps_after_429(result.events, "unit-a")
    gap = gaps[0] if gaps else None
    honoured = gap is not None and gap + 1e-12 >= RETRY_AFTER_S
    return {
        "honor_retry_after": honor,
        "retry_after_s": RETRY_AFTER_S,
        "gap_s": gap,
        "honoured": honoured,
        "completed": result.completed,
        "work_runs": result.work_runs,
        "events": result.events,
        "now": result.now,
    }


def duplicate_case(*, allow_duplicate: bool) -> dict[str, object]:
    clock = VirtualClock()
    mock = MockLimiter(clock)
    mock.set_plan(
        "unit-b",
        [
            Response(429, {"Retry-After": "1"}),
            Response(429, {"Retry-After": "1"}),
            Response(200, {}),
        ],
    )
    disp = Dispatcher(
        mock,
        clock,
        concurrency=2,
        honor_retry_after=True,
        allow_duplicate_retry_workers=allow_duplicate,
        fallback_backoff=FALLBACK_S,
    )
    result = disp.run(["unit-b"])
    runs = int(result.work_runs.get("unit-b") or 0)
    workers = sorted({str(e["worker_id"]) for e in result.events})
    return {
        "allow_duplicate_retry_workers": allow_duplicate,
        "work_runs": runs,
        "worker_ids": workers,
        "n_workers": len(workers),
        "completed": result.completed,
        "events": result.events,
        "duplicate": runs > 1 or len(workers) > 1,
    }


def concurrency_case(*, self_throttle: bool) -> dict[str, object]:
    clock = VirtualClock()
    mock = MockLimiter(clock)
    for uid in STORM_UNITS:
        mock.set_plan(
            uid,
            [
                Response(429, {"Retry-After": str(int(STORM_RETRY_AFTER_S))}),
                Response(529, {"X-Overload": "1"}),
                Response(200, {}),
            ],
        )
    disp = Dispatcher(
        mock,
        clock,
        concurrency=STORM_CONCURRENCY,
        honor_retry_after=True,
        self_throttle_on_overload=self_throttle,
        fallback_backoff=FALLBACK_S,
    )
    result = disp.run(list(STORM_UNITS))
    runs = result.work_runs
    duplicate_units = [u for u, n in runs.items() if n != 1]
    missing = [u for u in STORM_UNITS if u not in result.completed]
    statuses = [int(e["status"]) for e in result.events]
    return {
        "self_throttle_on_overload": self_throttle,
        "concurrency_initial": result.concurrency_initial,
        "concurrency_final": result.concurrency_final,
        "unchanged": result.concurrency_final == result.concurrency_initial,
        "completed": result.completed,
        "failed": result.failed,
        "work_runs": runs,
        "duplicate_units": duplicate_units,
        "missing": missing,
        "n_429": statuses.count(429),
        "n_529": statuses.count(529),
        "n_200": statuses.count(200),
        "events": result.events,
        "now": result.now,
    }


def test_retry_after_is_honoured() -> dict[str, object]:
    good = retry_after_case(honor=True)
    bad = retry_after_case(honor=False)
    ok = (
        good["honoured"] is True
        and bad["honoured"] is False
        and good["completed"] == ["unit-a"]
        and good["work_runs"] == {"unit-a": 1}
        and bad["work_runs"] == {"unit-a": 1}
    )
    return {"id": "test_retry_after_is_honoured", "pass": ok, "good": good, "mutant": bad}


def test_no_duplicate_execution_after_a_429_storm() -> dict[str, object]:
    good = duplicate_case(allow_duplicate=False)
    bad = duplicate_case(allow_duplicate=True)
    storm = concurrency_case(self_throttle=False)
    ok = (
        good["work_runs"] == 1
        and good["n_workers"] == 1
        and good["duplicate"] is False
        and bad["duplicate"] is True
        and bad["work_runs"] > 1
        and storm["duplicate_units"] == []
        and storm["missing"] == []
        and storm["n_429"] >= len(STORM_UNITS)
        and all(storm["work_runs"].get(u) == 1 for u in STORM_UNITS)
    )
    return {
        "id": "test_no_duplicate_execution_after_a_429_storm",
        "pass": ok,
        "good": good,
        "mutant": bad,
        "storm": {
            "duplicate_units": storm["duplicate_units"],
            "missing": storm["missing"],
            "n_429": storm["n_429"],
            "n_200": storm["n_200"],
            "work_runs": storm["work_runs"],
        },
    }


def test_concurrency_setting_is_not_self_throttled() -> dict[str, object]:
    good = concurrency_case(self_throttle=False)
    bad = concurrency_case(self_throttle=True)
    ok = (
        good["unchanged"] is True
        and good["concurrency_final"] == STORM_CONCURRENCY
        and good["n_529"] >= 1
        and good["missing"] == []
        and bad["unchanged"] is False
        and bad["concurrency_final"] < bad["concurrency_initial"]
    )
    return {
        "id": "test_concurrency_setting_is_not_self_throttled",
        "pass": ok,
        "good": good,
        "mutant": {
            "concurrency_initial": bad["concurrency_initial"],
            "concurrency_final": bad["concurrency_final"],
            "unchanged": bad["unchanged"],
            "n_529": bad["n_529"],
        },
        "storm_timeline": good["events"],
    }


def all_required_tests() -> list[dict[str, object]]:
    return [
        test_retry_after_is_honoured(),
        test_no_duplicate_execution_after_a_429_storm(),
        test_concurrency_setting_is_not_self_throttled(),
    ]
