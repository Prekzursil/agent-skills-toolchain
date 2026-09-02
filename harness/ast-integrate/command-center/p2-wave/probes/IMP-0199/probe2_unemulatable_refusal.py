#!/usr/bin/env python3
"""Named probe 2: unemulatable capability refused by name (both-states).

Good twin: emulatable workflow runs (structure, gates, stopping rules).
Bad twin: same graph plus live-model-infer is REFUSED and the refusal names
the capability. A silently faked success for that capability is the defect.

Defense in depth: a rail that lies in can_honestly_emulate still cannot
produce a live-model-infer receipt — execute_node refuses by name.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import load_workflow  # noqa: E402

from agentspec.evals.fake_rail import FakeRail, UnemulatableCapability  # noqa: E402
from agentspec.evals.instrumented_ports import InstrumentedPorts  # noqa: E402
from agentspec.evals.simulator import simulate  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0199.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0199-probe2 {msg}")
    return 1


class DishonestRail(FakeRail):
    """Claims it can emulate live-model-infer. It cannot — no emulator exists."""

    def can_honestly_emulate(self, capability: str) -> bool:
        if capability == "live-model-infer":
            return True
        return super().can_honestly_emulate(capability)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0199" not in text:
        return _fail("sentinel-absent")

    good_wf = load_workflow("emulatable.json")
    bad_wf = load_workflow("unemulatable.json")
    owner_wf = load_workflow("owner_checkpoint.json")

    with InstrumentedPorts() as ports:
        good = simulate(good_wf, rail=FakeRail(), ports=ports)
        good_spawns = ports.real_spawns
        good_egress = ports.egress_attempts

    if good.status != "RAN":
        return _fail(f"emulatable twin status={good.status} {good.refusal_message}")
    if good_spawns != 0 or good_egress != 0:
        return _fail(f"emulatable twin leaked spawn={good_spawns} egress={good_egress}")
    if good.gates_evaluated < 1 or good.stopping_rules_evaluated < 1:
        return _fail("emulatable twin did not exercise gate/stop")

    with InstrumentedPorts() as ports:
        bad = simulate(bad_wf, rail=FakeRail(), ports=ports)
        bad_spawns = ports.real_spawns
        bad_egress = ports.egress_attempts

    if bad.status != "REFUSED":
        return _fail(f"unemulatable twin status={bad.status} (silent fake?)")
    if "live-model-infer" not in bad.refused_capabilities:
        return _fail(f"refusal did not name live-model-infer: {bad.refused_capabilities}")
    if "live-model-infer" not in bad.refusal_message:
        return _fail(f"refusal message omitted capability: {bad.refusal_message}")
    if bad.steps != 0 or bad.receipts:
        return _fail("unemulatable twin started executing (must refuse pre-run)")
    if bad_spawns != 0 or bad_egress != 0:
        return _fail(f"refused run leaked spawn={bad_spawns} egress={bad_egress}")

    owner = simulate(owner_wf, rail=FakeRail())
    if owner.status != "REFUSED" or "owner-interactive" not in owner.refused_capabilities:
        return _fail(
            f"human_checkpoint not refused by name: {owner.status} {owner.refused_capabilities}"
        )

    # Liar rail: pretends live-model-infer is emulatable. Simulator would start;
    # execute_node must still refuse rather than emit a fake receipt.
    liar = DishonestRail()
    if not liar.can_honestly_emulate("live-model-infer"):
        return _fail("DishonestRail control did not lie")
    named = liar.unemulatable_in(bad_wf)
    if "live-model-infer" in named:
        return _fail("DishonestRail still listed live-model-infer as unemulatable")
    liar_result = simulate(bad_wf, rail=liar)
    if liar_result.status != "REFUSED":
        return _fail(f"liar rail silent-faked status={liar_result.status}")
    if "live-model-infer" not in liar_result.refused_capabilities:
        return _fail(f"liar rail refusal unnamed: {liar_result.refused_capabilities}")
    fake_receipts = [
        r for r in liar_result.receipts if "live-model-infer" in r.get("capabilities", [])
    ]
    if fake_receipts:
        return _fail("liar rail emitted a live-model-infer receipt")

    # Direct execute_node on the unemulatable node must raise with the name.
    tick = next(n for n in bad_wf["nodes"] if n["id"] == "unit.tick")
    raised = None
    try:
        FakeRail().execute_node(tick, predecessors={}, step=1, params={})
    except UnemulatableCapability as exc:
        raised = exc
    if raised is None or "live-model-infer" not in raised.capabilities:
        return _fail(f"execute_node did not name capability: {raised}")

    payload = {
        "probe": "probe2-unemulatable-refusal",
        "unit_id": "IMP-0199",
        "pass": True,
        "emulatable_twin": {
            "status": good.status,
            "visited": good.visited,
            "gates_evaluated": good.gates_evaluated,
            "stopping_rules_evaluated": good.stopping_rules_evaluated,
        },
        "unemulatable_twin": {
            "status": bad.status,
            "refused_capabilities": bad.refused_capabilities,
            "refusal_message": bad.refusal_message,
            "steps": bad.steps,
        },
        "owner_checkpoint": {
            "status": owner.status,
            "refused_capabilities": owner.refused_capabilities,
        },
        "dishonest_rail": {
            "status": liar_result.status,
            "refused_capabilities": liar_result.refused_capabilities,
            "no_faked_receipt": not fake_receipts,
        },
        "both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"good={good.status} bad={bad.status} named={bad.refused_capabilities} "
        f"liar={liar_result.status} owner={owner.refused_capabilities}"
    )
    print("SUCCESS:IMP-0199-probe2 unemulatable refused by name")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
