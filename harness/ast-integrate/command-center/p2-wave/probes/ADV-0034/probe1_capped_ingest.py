#!/usr/bin/env python3
"""Probe 1: feed each vector under a hard rlimit and record who fires first."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import dumps, measure_probe1  # noqa: E402


def main() -> int:
    doc = measure_probe1()
    print(dumps(doc))
    print(
        "control_ok={control_ok} json_unbounded={json_unbounded_at_program} "
        "tar_unbounded={tar_unbounded_at_program} wf_bound={subworkflow_app_bound} "
        "fanout_capped={fanout_production_capped}".format(**doc)
    )
    if not doc.get("pass"):
        print("FAILED:ADV-0034-probe1 capped ingest did not hold")
        return 1
    print("SUCCESS:ADV-0034-probe1 capped ingest under enforced rlimits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
