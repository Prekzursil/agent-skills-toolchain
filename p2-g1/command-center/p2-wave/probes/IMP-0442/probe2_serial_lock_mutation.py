"""Mutation control: removing the serial lock MUST push the series above one (IMP-0442)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import dispatcher as dsp  # noqa: E402


def main() -> int:
    substrates = dsp.load_substrates()
    assignments, _swaps = dsp.build_assignments(substrates)

    control = dsp.run_dry_run(assignments, duration_ticks=8, serial_lock=True)
    mutant = dsp.run_dry_run(assignments, duration_ticks=8, serial_lock=False)

    control_peak = control["peaks"]["local-serialized"]
    mutant_peak = mutant["peaks"]["local-serialized"]
    assert control_peak == 1, control_peak
    assert mutant_peak > 1, (
        "serial-lock mutation must show concurrency above one, got %s" % mutant_peak)

    # can_start() gates the real loop identically: lock armed refuses a second
    # start while one is in flight; disarmed admits it.
    assert dsp.can_start("local-serialized", 1, serial_lock=True) is False
    assert dsp.can_start("local-serialized", 1, serial_lock=False) is True

    print(json.dumps({
        "probe": "probe2-serial-lock-mutation",
        "unit_id": "IMP-0442",
        "control_peak_local_serialized": control_peak,
        "mutant_peak_local_serialized": mutant_peak,
        "mutation_detected": mutant_peak > 1,
        "can_start_armed_refuses_second": True,
        "can_start_disarmed_admits_second": True,
        "sentinel": "SENTINEL:IMP-0442:DISPATCH-SUBSTRATE-HONORED",
    }, indent=2))
    print("SUCCESS:IMP-0442-probe2 serial-lock removal turns the series above one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
