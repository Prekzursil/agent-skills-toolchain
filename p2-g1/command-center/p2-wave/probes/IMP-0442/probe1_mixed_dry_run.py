"""40-unit mixed dry run: local-serialized stays flat at one (IMP-0442)."""
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
    assignments, swaps = dsp.build_assignments(substrates)
    assert len(assignments) == 40, len(assignments)
    per = {}
    for uid, s in assignments.items():
        per.setdefault(s, []).append(uid)
    assert all(len(v) == 10 for v in per.values()), {k: len(v) for k, v in per.items()}

    run = dsp.run_dry_run(assignments, duration_ticks=8, serial_lock=True)
    peaks = run["peaks"]
    assert peaks["local-serialized"] == 1, peaks
    for s in ("cloud-batch", "local-parallel", "worktree-isolated"):
        assert peaks[s] == 10, (s, peaks[s])
    t0 = run["time_series"][0]["concurrent"]
    assert t0["local-serialized"] == 1

    flat = [row["concurrent"]["local-serialized"] for row in run["time_series"]]
    assert all(v <= 1 for v in flat), flat

    print(json.dumps({
        "probe": "probe1-mixed-dry-run",
        "unit_id": "IMP-0442",
        "unit_count": 40,
        "per_substrate": {s: len(v) for s, v in per.items()},
        "peaks": peaks,
        "local_serialized_series": flat,
        "receipt_id_swaps": swaps,
        "substrate_source": "live WORK-UNIT-CATALOG execution_substrate fields",
        "sentinel": "SENTINEL:IMP-0442:DISPATCH-SUBSTRATE-HONORED",
    }, indent=2))
    print("SUCCESS:IMP-0442-probe1 local-serialized flat at one; others at cap 10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
