#!/usr/bin/env python3
"""Named probe 1: zero egress / zero real spawn during simulation, measured.

Signal 1: InstrumentedPorts monkeypatch of socket/subprocess/os.system.
Signal 2: FakeRail spawn_count / egress_count ledgers.
Disagreement is failure, not a picked winner.

Both-states: a rail that escapes to subprocess.Popen must increment the spawn
counter (detector fires on the broken state); the honest rail stays at zero.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import AGENTSPEC_ROOT, load_workflow  # noqa: E402

from agentspec.evals.fake_rail import FakeRail  # noqa: E402
from agentspec.evals.instrumented_ports import InstrumentedPorts, SpawnBlocked  # noqa: E402
from agentspec.evals.pytest_live import LIVE_CALLS, reset as reset_live  # noqa: E402
from agentspec.evals.simulator import simulate  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0199.json"
SIM_PY = AGENTSPEC_ROOT / "agentspec" / "evals" / "simulator.py"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0199-probe1 {msg}")
    return 1


def _ast_no_pytest_live() -> str | None:
    tree = ast.parse(SIM_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "pytest_live" in alias.name:
                    return alias.name
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if "pytest_live" in mod:
                return mod
            for alias in node.names:
                if "pytest_live" in alias.name:
                    return alias.name
    return None


class EscapingRail(FakeRail):
    """Broken twin: attempts a real spawn while 'simulating' a node."""

    def execute_node(self, node, **kwargs):  # noqa: ANN001
        try:
            subprocess.Popen(["/bin/true"])
        except SpawnBlocked:
            pass
        return super().execute_node(node, **kwargs)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0199" not in text:
        return _fail("sentinel-absent")

    leaked = _ast_no_pytest_live()
    if leaked:
        return _fail(f"simulator imports live rail {leaked}")

    reset_live()
    wf = load_workflow("emulatable.json")
    rail = FakeRail()
    with InstrumentedPorts() as ports:
        result = simulate(wf, rail=rail, ports=ports)
        good_egress = ports.egress_attempts
        good_spawns = ports.real_spawns
        good_snap = ports.snapshot()

    if result.status != "RAN":
        return _fail(f"emulatable status={result.status} msg={result.refusal_message}")
    if result.gates_evaluated < 1:
        return _fail("gate never evaluated")
    if result.stopping_rules_evaluated < 1:
        return _fail("stopping rule never evaluated")
    if "loop.refine" not in result.visited:
        return _fail("loop node not visited")
    if good_egress != 0 or good_spawns != 0:
        return _fail(
            f"honest run leaked egress={good_egress} spawns={good_spawns} "
            f"attempts={good_snap}"
        )
    if rail.spawn_count != 0 or rail.egress_count != 0:
        return _fail(
            f"rail ledger spawn={rail.spawn_count} egress={rail.egress_count}"
        )
    if rail.spawn_count != good_spawns or rail.egress_count != good_egress:
        return _fail("port/rail disagreement")
    if LIVE_CALLS:
        return _fail(f"pytest_live invoked {LIVE_CALLS}")

    # Broken state: escaped spawn must be counted (and blocked).
    bad_rail = EscapingRail()
    with InstrumentedPorts() as ports:
        try:
            simulate(wf, rail=bad_rail, ports=ports)
        except SpawnBlocked:
            pass
        bad_spawns = ports.real_spawns
        bad_egress = ports.egress_attempts

    if bad_spawns < 1:
        return _fail("spawn detector silent on escaping rail")
    if bad_egress != 0:
        return _fail(f"escaping rail also made egress={bad_egress}")

    payload = {
        "probe": "probe1-zero-egress-spawn",
        "unit_id": "IMP-0199",
        "pass": True,
        "honest": {
            "status": result.status,
            "egress_attempts": good_egress,
            "real_spawns": good_spawns,
            "rail_spawn_count": rail.spawn_count,
            "rail_egress_count": rail.egress_count,
            "gates_evaluated": result.gates_evaluated,
            "stopping_rules_evaluated": result.stopping_rules_evaluated,
            "visited": result.visited,
            "steps": result.steps,
            "pytest_live_calls": len(LIVE_CALLS),
        },
        "broken_escape": {
            "real_spawns": bad_spawns,
            "detector_fired": bad_spawns >= 1,
        },
        "signals": ["instrumented-ports", "fake-rail-ledger"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"honest_egress={good_egress} honest_spawns={good_spawns} "
        f"escape_spawns={bad_spawns} gates={result.gates_evaluated} "
        f"stops={result.stopping_rules_evaluated}"
    )
    print("SUCCESS:IMP-0199-probe1 zero egress/spawn measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
