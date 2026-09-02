#!/usr/bin/env python3
"""Scenario evals for the process-hygiene supervisor (eval-driven development).

Each JSON scenario under ``scenarios/`` replays a process table through the REAL
engine for ``rounds`` five-minute samples (so idle confirmations accrue exactly as
they would on the box) and grades the resulting plan with deterministic code:

* ``expect.tier``            - the pressure tier the final sample must land on
* ``expect.stop_pids``       - the EXACT set of pids in stop trees (any tier)
* ``expect.never_touched``   - pids that must not appear in any stop tree
* ``expect.rules_present``   - rules that must surface (stop or report)
* ``expect.rules_absent``    - rules that must not surface
* ``expect.delegate_reaper`` / ``expect.wsl_shutdown``

The engine is deterministic, so ``pass^3`` (three consecutive trials) doubles as
a stability check; ``pass@1`` is the first-trial success rate. Both are printed in
the EVAL REPORT and the CLI exits 1 on any failure, so CI can gate on it.

Scenario process rows are written for humans: ``age_seconds`` (relative to the
final sample) instead of absolute creation times, ``private_mib`` instead of bytes,
``active: true`` for a process whose CPU keeps advancing, and ``count`` to expand a
row into N consecutive pids (70 chrome renderers, 42 msedge, ...).
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
TOOL_ROOT = HERE.parent
sys.path.insert(0, str(TOOL_ROOT))

import hygiene  # noqa: E402

SCENARIO_DIR = HERE / "scenarios"
NOW = 5_000_000
STEP = 300
MIB = 1024**2


class ScenarioError(ValueError):
    """Raised when a scenario file does not follow the eval schema."""


@dataclass
class Result:
    name: str
    kind: str
    trials_passed: int
    trials: int
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.trials_passed == self.trials


def _policy(overrides: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(
        (TOOL_ROOT / "policy.example.json").read_text(encoding="utf-8")
    )
    for dotted, value in overrides.items():
        node = payload
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value
    return hygiene.validate_policy(payload)


def _expand_processes(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise ScenarioError("scenario needs a non-empty 'processes' list")
    expanded: list[dict[str, Any]] = []
    for row in rows:
        count = int(row.get("count", 1))
        if count < 1:
            raise ScenarioError("process 'count' must be >= 1")
        for offset in range(count):
            item = dict(row)
            item.pop("count", None)
            item["pid"] = int(row["pid"]) + offset
            expanded.append(item)
    return expanded


def _snapshot(
    scenario: dict[str, Any],
    processes: list[dict[str, Any]],
    round_index: int,
    rounds: int,
) -> dict[str, Any]:
    taken = NOW - (rounds - 1 - round_index) * STEP
    host = scenario.get(
        "host",
        {
            "physical_bytes": 32 * 1024**3,
            "free_bytes": 8 * 1024**3,
            "commit_total_bytes": 20 * 1024**3,
            "commit_limit_bytes": 64 * 1024**3,
        },
    )
    rows = []
    for item in processes:
        cpu = float(item.get("cpu", 1.0))
        if item.get("active"):
            cpu += round_index
        private = int(item.get("private_mib", 100)) * MIB
        rows.append(
            {
                "pid": item["pid"],
                "ppid": item.get("ppid", 1),
                "name": item.get("name", "node.exe"),
                "executable": item.get(
                    "executable", "C:\\Program Files\\nodejs\\node.exe"
                ),
                "command_line": item.get("command_line", item.get("name", "node")),
                "created_unix": NOW - int(item.get("age_seconds", 3600)),
                "cpu_seconds": cpu,
                "io_bytes": int(item.get("io_bytes", 10)),
                "working_set_bytes": private,
                "private_bytes": private,
            }
        )
    listeners = [
        {"port": int(port), "pid": int(pid)}
        for port, pid in scenario.get("listeners", {}).items()
    ]
    return {
        "schema": hygiene.SCHEMA_SNAPSHOT,
        "taken_unix": taken,
        "host": host,
        "wsl": scenario.get("wsl", {"available": True, "running_distros": []}),
        "listeners": listeners,
        "supervisor_pids": scenario.get("supervisor_pids", []),
        "processes": rows,
    }


def _grade(plan: hygiene.Plan, expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    stop_pids = {
        member.pid
        for decision in plan.decisions
        if decision.action == "stop"
        for member in decision.tree
    }
    rules = {decision.rule for decision in plan.decisions}
    if "tier" in expect and plan.tier != expect["tier"]:
        failures.append(f"tier: expected {expect['tier']}, got {plan.tier}")
    if "stop_pids" in expect:
        wanted = set(expect["stop_pids"])
        if stop_pids != wanted:
            failures.append(
                f"stop_pids: expected {sorted(wanted)}, got {sorted(stop_pids)}"
            )
    touched = stop_pids & set(expect.get("never_touched", []))
    if touched:
        failures.append(f"never_touched: {sorted(touched)} appear in a stop tree")
    missing = set(expect.get("rules_present", [])) - rules
    if missing:
        failures.append(f"rules_present: missing {sorted(missing)}")
    present = set(expect.get("rules_absent", [])) & rules
    if present:
        failures.append(f"rules_absent: unexpectedly present {sorted(present)}")
    if (
        "delegate_reaper" in expect
        and plan.delegate_reaper != expect["delegate_reaper"]
    ):
        failures.append(f"delegate_reaper: expected {expect['delegate_reaper']}")
    if "wsl_shutdown" in expect and plan.wsl_shutdown != expect["wsl_shutdown"]:
        failures.append(f"wsl_shutdown: expected {expect['wsl_shutdown']}")
    return failures


def run_scenario(scenario: dict[str, Any], *, trials: int = 3) -> Result:
    processes = _expand_processes(scenario.get("processes"))
    rounds = int(scenario.get("rounds", 4))
    expect = scenario.get("expect", {})
    fleet = hygiene.load_fleet(hygiene.DEFAULT_FLEET_PATH)
    registry = json.loads(hygiene.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    policy = _policy(scenario.get("policy", {}))
    result = Result(
        name=str(scenario.get("name", "unnamed")),
        kind=str(scenario.get("kind", "capability")),
        trials_passed=0,
        trials=trials,
    )
    for _trial in range(trials):
        engine = hygiene.Engine(policy, {}, fleet=fleet, registry=registry)
        plan = None
        for index in range(rounds):
            plan = engine.evaluate(
                hygiene.parse_snapshot(_snapshot(scenario, processes, index, rounds)),
                reaper_available=bool(scenario.get("reaper_available", True)),
            )
        failures = _grade(plan, expect)
        if failures:
            result.failures = failures
        else:
            result.trials_passed += 1
    return result


def load_scenarios(directory: pathlib.Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def run_all(*, trials: int = 3, directory: pathlib.Path = SCENARIO_DIR) -> list[Result]:
    return [
        run_scenario(copy.deepcopy(s), trials=trials) for s in load_scenarios(directory)
    ]


def render_report(results: list[Result]) -> str:
    lines = ["EVAL REPORT: process-hygiene-supervisor", "=" * 40]
    for kind, title in (
        ("capability", "Capability Evals"),
        ("regression", "Regression Evals"),
    ):
        rows = [r for r in results if r.kind == kind]
        if not rows:
            continue
        lines.append(f"{title}:")
        for r in rows:
            verdict = "PASS" if r.passed else "FAIL"
            lines.append(f"  {r.name:<40} {verdict} ({r.trials_passed}/{r.trials})")
            for failure in r.failures:
                lines.append(f"      - {failure}")
        lines.append(f"  Overall: {sum(r.passed for r in rows)}/{len(rows)} passed")
    first_trial = sum(1 for r in results if r.trials_passed >= 1) if results else 0
    stable = sum(1 for r in results if r.passed)
    total = len(results)
    pct = lambda n: f"{(100 * n / total):.0f}%" if total else "n/a"  # noqa: E731
    lines.append("Metrics:")
    lines.append(f"  pass@1: {pct(first_trial)} ({first_trial}/{total})")
    lines.append(f"  pass^3: {pct(stable)} ({stable}/{total})")
    lines.append(f"Status: {'READY' if stable == total else 'FAILING'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenarios", default=str(SCENARIO_DIR))
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args(argv)
    results = run_all(trials=args.trials, directory=pathlib.Path(args.scenarios))
    print(render_report(results))
    return 0 if results and all(r.passed for r in results) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
