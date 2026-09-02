#!/usr/bin/env python3
"""Probe 2: if one node escapes dry-run, the zero-spawn counter goes red.

Both states:
  honest dry-run -> spawn_count == 0 (silent on good)
  one unit calls rail.spawn -> spawn_count >= 1 (fires on bad)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS / "agentrail"))
sys.path.insert(0, str(TOOLS / "agentspec"))
sys.path.insert(0, str(HERE))

from agentrail.ports import InstrumentedPorts  # noqa: E402
from agentspec.dispatchpolicy import dry_run  # noqa: E402
from largest import dry_run_params, largest_workflow  # noqa: E402

OUT = HERE / "probe2-escape-mutation.raw.json"
ESCAPE = "u00"


def _run(*, escape: str | None, scratch: Path):
    ports = InstrumentedPorts.for_dry_run(scratch)
    plan = dry_run(
        largest_workflow(),
        dry_run_params(),
        ports=ports,
        escape_unit_id=escape,
    )
    return ports, plan


def main() -> int:
    wf_units = len(largest_workflow()["units"])
    with tempfile.TemporaryDirectory(prefix="imp0142-p2-") as tmp:
        good_scratch = Path(tmp) / "good"
        bad_scratch = Path(tmp) / "bad"
        good_ports, good_plan = _run(escape=None, scratch=good_scratch)
        bad_ports, bad_plan = _run(escape=ESCAPE, scratch=bad_scratch)

    silent_on_good = good_ports.zero_spawns() and good_plan.spawn_count == 0
    fired_on_bad = (not bad_ports.zero_spawns()) and bad_plan.spawn_count >= 1
    zero_spawn_predicate_red = not (bad_plan.spawn_count == 0)
    escaped = any(p.get("escaped_dry_run") for p in bad_plan.planned_units)
    still_zero_egress = (
        good_ports.zero_egress()
        and bad_ports.zero_egress()
        and good_plan.egress_count == 0
        and bad_plan.egress_count == 0
    )
    passed = bool(
        silent_on_good
        and fired_on_bad
        and zero_spawn_predicate_red
        and escaped
        and still_zero_egress
        and wf_units == 64
    )
    doc = {
        "probe": "probe2-escape-mutation",
        "unit_id": "IMP-0142",
        "escape_unit_id": ESCAPE,
        "silent_on_good": silent_on_good,
        "fired_on_bad": fired_on_bad,
        "zero_spawn_counter_went_red": zero_spawn_predicate_red,
        "escaped_unit_flagged": escaped,
        "good_spawn_count": good_plan.spawn_count,
        "bad_spawn_count": bad_plan.spawn_count,
        "good_egress_count": good_plan.egress_count,
        "bad_egress_count": bad_plan.egress_count,
        "still_zero_egress": still_zero_egress,
        "pass": passed,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"silent_on_good={silent_on_good} fired_on_bad={fired_on_bad} "
        f"zero_spawn_red={zero_spawn_predicate_red} escaped={escaped} "
        f"good_spawns={good_plan.spawn_count} bad_spawns={bad_plan.spawn_count}"
    )
    if not passed:
        print("FAILED:IMP-0142-probe2 escape mutation did not turn zero-spawn red")
        print(json.dumps(doc, indent=2, sort_keys=True))
        return 1
    print("SUCCESS:IMP-0142-probe2 escape mutation turns zero-spawn counter red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
