#!/usr/bin/env python3
"""Probe 2: halved-δ sensitivity; known-broken constant calculator must not move."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import inputs as I  # noqa: E402
import power as P  # noqa: E402

OUT = REPO / "command-center/research/RES-0095.json"


def main() -> int:
    bundle = I.gather()
    live = P.report(int(bundle["planned"]["planned_n"]), float(bundle["residual_variance_used"]))
    sens = live["sensitivity_halved_effect_size"]
    broken = live["known_broken_constant_calculator"]
    print(sens["printed"])
    print(
        f"good_moved={sens['moved']} ratio={sens['ratio']} "
        f"n={sens['required_n']} n_halved={sens['required_n_halved']}"
    )
    print(f"broken_moved={broken['moved']} broken_printed={broken['printed']}")
    if not sens["moved"]:
        print("FAILED:RES-0095-probe2 good calculator silent when δ halved")
        return 1
    if not (3.0 <= float(sens["ratio"]) <= 5.0):
        print(f"FAILED:RES-0095-probe2 ratio {sens['ratio']} not near 4")
        return 1
    if broken["moved"] is not False:
        print("FAILED:RES-0095-probe2 known-broken constant calculator moved")
        return 1
    if broken["required_n"] != broken["required_n_halved"]:
        print("FAILED:RES-0095-probe2 broken n changed")
        return 1
    if not OUT.is_file():
        print("FAILED:RES-0095-probe2 artifact missing")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    rec = art.get("printed_sensitivity_row_halved_effect_size")
    if rec != sens["printed"]:
        print(f"FAILED:RES-0095-probe2 sensitivity print drift artifact={rec!r}")
        return 1
    neg = (art.get("negative_controls") or [{}])[0]
    if not neg.get("fired_on_bad_state") or not neg.get("silent_on_good_state"):
        print("FAILED:RES-0095-probe2 negative control flags")
        return 1
    text = OUT.read_text(encoding="utf-8")
    if sens["printed"] not in text:
        print("FAILED:RES-0095-probe2 sensitivity row absent from artifact")
        return 1
    print("SUCCESS:RES-0095-probe2 halved-effect sensitivity and broken-calculator control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
