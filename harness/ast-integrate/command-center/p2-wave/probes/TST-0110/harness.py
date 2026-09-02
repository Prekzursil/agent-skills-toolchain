"""Instrumented stand-ins for the four TST-0025 surfaces plus one planted gameable.

Primary metrics are exact counters (compare-ops, spawn log length, work units,
collected test steps, stage count). Wall-clock is not the gaming verdict:
n=7 wall-clock on a shared box is unbanded and would manufacture GAMEABLE.

Empty input fails closed. A zero-cardinality run must not emit a number.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "workflows"

SEED = 11059
N_RUNS = 7


class EmptyInputError(ValueError):
    """Harness refused to emit a metric because the input set is empty."""


def _require_inputs(name: str, inputs: list) -> None:
    if not inputs:
        raise EmptyInputError(f"{name}: n_inputs=0 refused (not a number)")


def _packets(n: int = 12) -> list[dict[str, str]]:
    out = []
    for i in range(n):
        out.append(
            {
                "id": f"p{i}",
                "src": f"n{i % 4}",
                "dst": f"n{(i + 1) % 5}",
            }
        )
    return out


def _table(null_comment: bool = False) -> list[dict[str, Any]]:
    rows = [
        {"id": "r0", "src": "n0", "dst": "n1"},
        {"id": "r1", "src": "n1", "dst": "n2"},
        {"id": "r2", "src": "n2", "dst": "n3"},
        {"id": "r3", "src": "n3", "dst": "n4"},
        {"id": "r4", "src": "n0", "dst": "n2"},
        {"id": "r5", "src": "n1", "dst": "n3"},
        {"id": "r6", "src": "n2", "dst": "n4"},
        {"id": "r7", "src": "n3", "dst": "n1"},
    ]
    if null_comment:
        rows[0] = dict(rows[0])
        rows[0]["comment"] = "null rename; not on the scoring path"
    return rows


def router_ops(packets: list[dict[str, str]], extra_pass: bool = False, null_comment: bool = False) -> int:
    _require_inputs("router_latency", packets)
    table = _table(null_comment=null_comment)
    ops = 0
    scans = 2 if extra_pass else 1
    for pkt in packets:
        best_score = -1
        for _ in range(scans):
            for rule in table:
                ops += 1
                score = 0
                if rule["dst"] == pkt["dst"]:
                    score += 2
                if rule["src"] == pkt["src"]:
                    score += 1
                if score > best_score:
                    best_score = score
    return ops


def _events(n: int = 9) -> list[dict[str, str]]:
    kinds = ("pre-tool", "post-tool", "status")
    return [{"id": f"e{i}", "kind": kinds[i % 3]} for i in range(n)]


def hook_spawns(
    events: list[dict[str, str]],
    extra_spawn: bool = False,
    null_comment: bool = False,
) -> int:
    _require_inputs("hook_overhead", events)
    spawn_log: list[str] = []
    comments: list[str] = []
    for ev in events:
        spawn_log.append(f"dispatch:{ev['kind']}")
        if null_comment:
            comments.append(f"note:{ev['id']}")
        if extra_spawn:
            spawn_log.append("jq-shim")
    return len(spawn_log)


def _items(n: int = 16) -> list[str]:
    return [f"job-{i}" for i in range(n)]


def fanout_cost(items: list[str], work_per_item: int = 1, unused_tag: bool = False) -> int:
    _require_inputs("fanout_throughput", items)
    cost = 0
    tag = "unused" if unused_tag else ""
    for item in items:
        _ = tag  # null: bind unused metadata, do not charge the metric
        for _step in range(work_per_item):
            cost += 1
            cost += (len(item) & 0)  # keep the item live without adding noise
    return cost


def _tests(extra_uncollected: bool = False) -> list[dict[str, Any]]:
    rows = [
        {"id": "t-router", "collect": True, "steps": 4},
        {"id": "t-hook", "collect": True, "steps": 3},
        {"id": "t-fanout", "collect": True, "steps": 5},
    ]
    if extra_uncollected:
        rows.append({"id": "t-dead", "collect": False, "steps": 99})
    return rows


def suite_steps(tests: list[dict[str, Any]], inflate: bool = False) -> int:
    _require_inputs("suite_wallclock", tests)
    cost = 0
    for t in tests:
        if not t.get("collect"):
            continue
        n = int(t["steps"]) * (10 if inflate else 1)
        cost += n
    if cost <= 0:
        raise EmptyInputError("suite_wallclock: collected set empty (not a number)")
    return cost


def _load_wf(name: str) -> dict[str, Any]:
    path = FIX / name
    return json.loads(path.read_text(encoding="utf-8"))


def stage_count(workflow: dict[str, Any]) -> int:
    stages = list(workflow.get("stages") or [])
    _require_inputs("workflow_stage_count", stages)
    return len(stages)


def workflow_work(workflow: dict[str, Any]) -> int:
    stages = list(workflow.get("stages") or [])
    _require_inputs("workflow_work", stages)
    return sum(int(s.get("work") or 0) for s in stages)


def run_named(name: str, state: str) -> tuple[int, int]:
    """Return (n_inputs, metric). state in {baseline, null, mechanism}."""
    if state not in {"baseline", "null", "mechanism"}:
        raise ValueError(f"unknown state {state}")
    if name == "router_latency":
        pk = _packets()
        val = router_ops(
            pk,
            extra_pass=(state == "mechanism"),
            null_comment=(state == "null"),
        )
        return len(pk), val
    if name == "hook_overhead":
        ev = _events()
        val = hook_spawns(
            ev,
            extra_spawn=(state == "mechanism"),
            null_comment=(state == "null"),
        )
        return len(ev), val
    if name == "fanout_throughput":
        items = _items()
        work = 8 if state == "mechanism" else 1
        val = fanout_cost(items, work_per_item=work, unused_tag=(state == "null"))
        return len(items), val
    if name == "suite_wallclock":
        tests = _tests(extra_uncollected=(state == "null"))
        val = suite_steps(tests, inflate=(state == "mechanism"))
        collected = sum(1 for t in tests if t.get("collect"))
        return collected, val
    if name == "workflow_stage_count":
        fname = {
            "baseline": "baseline.json",
            "null": "null_padding_stage.json",
            "mechanism": "mechanism_real_stage.json",
        }[state]
        wf = _load_wf(fname)
        stages = list(wf.get("stages") or [])
        return len(stages), stage_count(wf)
    raise KeyError(name)


BENCHMARKS: list[dict[str, Any]] = [
    {
        "name": "router_latency",
        "metric_id": "route_compare_ops",
        "surface": "router latency (TST-0025)",
        "expected": "HONEST",
        "null_change": "comment field on a route row (not scored)",
        "mechanism_change": "second scoring pass over the table",
    },
    {
        "name": "hook_overhead",
        "metric_id": "spawn_log_len",
        "surface": "hook overhead (TST-0025 / TST-0107 spawn count)",
        "expected": "HONEST",
        "null_change": "comment list append that is not a spawn",
        "mechanism_change": "extra jq-shim spawn per event",
    },
    {
        "name": "fanout_throughput",
        "metric_id": "work_units",
        "surface": "fan-out throughput (TST-0025); reported as cost, not items/sec",
        "expected": "HONEST",
        "null_change": "unused tag bind (not charged)",
        "mechanism_change": "8x work per item",
    },
    {
        "name": "suite_wallclock",
        "metric_id": "collected_test_steps",
        "surface": "suite wall-clock (TST-0025); instrument is collected steps",
        "expected": "HONEST",
        "null_change": "uncollected dead test (steps=99, collect=false)",
        "mechanism_change": "10x steps on collected tests",
    },
    {
        "name": "workflow_stage_count",
        "metric_id": "stage_count",
        "surface": "merged-workflow acceptance by stage count (:11170)",
        "expected": "GAMEABLE",
        "null_change": "insert comment/padding stage with work=0",
        "mechanism_change": "insert a real validate stage with work=8",
        "planted": True,
        "replace_with": "workflow_work (sum of stage.work; padding does not move it)",
    },
]


def empty_input_control(name: str) -> str:
    """Run the known-broken empty state. Returns the exception type name."""
    try:
        if name == "router_latency":
            router_ops([])
        elif name == "hook_overhead":
            hook_spawns([])
        elif name == "fanout_throughput":
            fanout_cost([])
        elif name == "suite_wallclock":
            suite_steps([])
        elif name == "workflow_stage_count":
            stage_count({"stages": []})
        else:
            raise KeyError(name)
    except EmptyInputError:
        return "EmptyInputError"
    return "DID-NOT-FIRE"


def sample_runs(name: str, state: str, n: int = N_RUNS) -> tuple[int, list[int]]:
    n_inputs = 0
    raw: list[int] = []
    for _ in range(n):
        n_inputs, val = run_named(name, state)
        raw.append(int(val))
    return n_inputs, raw
