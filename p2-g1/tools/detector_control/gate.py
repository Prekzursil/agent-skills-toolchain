"""Gate CLI for TST-0014: fail while uncontrolled detectors exist.

Order is load-bearing: the enumerator's OWN known-present fixture control fires
first (detector-on-detector control); absence of controls is only trusted after
that control has fired. Exit 0 = census-only or uncontrolled <= threshold;
exit 1 = uncontrolled-detectors (names the ids).

    python -B tools/detector_control/gate.py --census-only
    python -B tools/detector_control/gate.py [--root R] [--threshold N] [--registry R.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from controls import census as census_of, load_registry
from enumerate import enumerate_detectors, enumerator_control


def run_gate(
    root: Path,
    registry: Path | None = None,
    threshold: int = 0,
    census_only: bool = False,
) -> tuple[int, dict]:
    control = enumerator_control(None)  # detector-on-detector: planted must fire first
    if not control["fired"]:
        return 2, {"error": "enumerator-known-present-control-did-not-fire", "control": control}
    detectors = enumerate_detectors(root)
    reg = load_registry(registry)
    counts = census_of(detectors, reg)
    counts["known_present_control"] = control
    uncontrolled = int(counts["uncontrolled_count"])
    if census_only:
        return 0, {"exit_code": 0, "mode": "census-only", **counts}
    exit_code = 0 if uncontrolled <= threshold else 1
    return exit_code, {
        "exit_code": exit_code,
        "mode": "gate",
        "threshold": threshold,
        "reason": None if exit_code == 0 else "uncontrolled-detectors",
        "named_uncontrolled": counts["uncontrolled_ids"],
        **counts,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TST-0014 detector-control gate")
    ap.add_argument("--root", default=".")
    ap.add_argument("--threshold", type=int, default=0)
    ap.add_argument("--registry", default=None)
    ap.add_argument("--census-only", action="store_true")
    args = ap.parse_args(argv)
    code, report = run_gate(Path(args.root).resolve(), None if args.registry is None else Path(args.registry), args.threshold, args.census_only)
    print(json.dumps(report, indent=1))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
