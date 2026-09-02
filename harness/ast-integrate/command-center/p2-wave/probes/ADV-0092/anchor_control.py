#!/usr/bin/env python3
"""Anchor-pair both-states control.

clean: deliberately collapsed vs deliberately diverse must separate (exit 0).
diverse-cloned-from-collapsed: replacing diverse with collapsed must go red (exit 1).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import measure_probe1  # noqa: E402
from metrics import fmt  # noqa: E402

DEFAULT_CLEAN = HERE / "anchor-control-clean.raw.txt"
DEFAULT_RED = HERE / "anchor-control-red.raw.txt"


def render(mode: str, live: dict, expected_green: bool) -> str:
    gate = live["gate"]
    actual_green = bool(gate["passed"])
    expected_state = "GREEN" if expected_green else "RED"
    actual_state = "GREEN" if actual_green else "RED"
    met = actual_green is expected_green
    lines = [
        "anchor pair required: a deliberately collapsed council (all "
        "participants given the same role) and a deliberately diverse one, "
        "with the measured statistic separating them before any real council "
        "is scored"
        if expected_green
        else "negative control: replace the deliberately diverse anchor with "
        "the collapsed anchor; the separation gate must go red with exit 1",
        f"mode={mode}",
        f"collapsed_mean_combined_divergence={fmt(gate['collapsed_mean_combined_divergence'])}",
        f"diverse_mean_combined_divergence={fmt(gate['diverse_mean_combined_divergence'])}",
        f"anchor_margin={fmt(gate['anchor_margin'])}",
        f"required_margin={fmt(gate['threshold']['min_margin'])}",
        f"anchor_separation_gate={str(actual_green).lower()}",
        f"actual_control_state={actual_state}",
        f"expected_control_state={expected_state}",
        f"expectation_met={str(met).lower()}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("clean", "diverse-cloned-from-collapsed"),
        default="clean",
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    clone = args.mode == "diverse-cloned-from-collapsed"
    live = measure_probe1(clone_diverse_from_collapsed=clone)
    expected_green = not clone
    text = render(args.mode, live, expected_green)
    out = Path(args.output) if args.output else (
        DEFAULT_RED if clone else DEFAULT_CLEAN
    )
    out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    met = bool(live["gate"]["passed"]) is expected_green
    if not met:
        sys.stdout.write("FAILED:ADV-0092-anchor-separation-control\n")
        return 1
    if expected_green:
        sys.stdout.write("exit_code=0\n")
        sys.stdout.write("SUCCESS:ADV-0092-anchor-separation-control\n")
        return 0
    # Negative control: the gate is correctly red. This process exits 1 so a
    # wrapper can distinguish RED from silent-pass. expectation_met is true.
    sys.stdout.write("exit_code=1\n")
    sys.stdout.write("FAILED:ADV-0092-anchor-separation-control\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
