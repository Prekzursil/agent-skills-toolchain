#!/usr/bin/env python3
"""TST-0181 probe2 -- detector controls: a removed hook file drops the count and
errors LOUDLY; the $schema-crash regression seed is visible to the probe.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hooks_loader as HL  # noqa: E402

UNIT = "TST-0181"
RUN = HERE / ".run-p2"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    (RUN / "hooks").mkdir(parents=True)
    for i in range(3):
        (RUN / "hooks" / ("h%d.py" % i)).write_text("# hook %d\n" % i)
    cfg = {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "hooks": {
            "alpha": {"command": "run-alpha", "file": "h0.py"},
            "beta": {"command": "run-beta", "file": "h1.py"},
            "gamma": {"command": "run-gamma", "file": "h2.py"},
        },
    }
    (RUN / "cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    base = HL.load_hooks(RUN / "cfg.json", RUN / "hooks")
    n0 = len(base["loaded"])

    # (a) remove one hook file -> count drops AND the missing hook is a LOUD error
    (RUN / "hooks" / "h1.py").unlink()
    after = HL.load_hooks(RUN / "cfg.json", RUN / "hooks")
    count_dropped = len(after["loaded"]) == n0 - 1
    loud_error = bool(after["errors"]) and any("beta" in e and "missing" in e for e in after["errors"])

    # (b) regression seed: the crash-on-$schema client loads ZERO hooks with $schema
    crashed = HL.load_hooks(RUN / "cfg.json", RUN / "hooks", crash_on_schema=True)
    seed_visible = crashed.get("crashed_on_schema") is True and len(crashed["loaded"]) == 0

    payload = {
        "probe": "probe2-detector-controls",
        "unit_id": UNIT,
        "pass": count_dropped and loud_error and seed_visible,
        "detector_control": {
            "baseline_count": n0,
            "count_after_file_removal": len(after["loaded"]),
            "count_probe_drops": count_dropped,
            "loud_error_listing_missing": after["errors"],
        },
        "regression_seed": {
            "seed": "hooks.json $schema made a client load ZERO hooks (_USER-PROMPTS.md:11014 layer 26)",
            "crash_variant_loaded_zero": len(crashed["loaded"]) == 0,
            "detector_sees_the_zero": seed_visible,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 count_drop=%s loud=%s seed_zero_visible=%s"
              % (UNIT, count_dropped, loud_error, seed_visible))
        return 0
    print("FAILED:%s-probe2 drop=%s loud=%s seed=%s" % (UNIT, count_dropped, loud_error, seed_visible))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
