#!/usr/bin/env python3
"""Probe 1: recompute required N vs planned N and match the artifact printout."""
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
    printed = live["comparison"]["printed"]
    print(printed)
    print(
        f"required_n={live['required_n']} planned_n={live['comparison']['planned_n']} "
        f"verdict={live['comparison']['verdict']} sigma2={live['variance_parts']['sigma2']}"
    )
    if not OUT.is_file():
        print("FAILED:RES-0095-probe1 artifact missing")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    if art.get("printed_required_n_versus_planned_n") != printed:
        print(
            "FAILED:RES-0095-probe1 printed comparison drift "
            f"artifact={art.get('printed_required_n_versus_planned_n')!r} live={printed!r}"
        )
        return 1
    if int(art.get("required_n")) != int(live["required_n"]):
        print("FAILED:RES-0095-probe1 required_n drift")
        return 1
    if int(art.get("planned_n")) != int(live["comparison"]["planned_n"]):
        print("FAILED:RES-0095-probe1 planned_n drift")
        return 1
    if live["required_n"] < 2:
        print("FAILED:RES-0095-probe1 required_n implausibly small")
        return 1
    sentinel = (
        "SUCCESS:RES-0095 in the receipt AND a printed required-N versus planned-N "
        "comparison plus a sensitivity row for a halved effect size"
    )
    text = OUT.read_text(encoding="utf-8")
    if sentinel not in text or printed not in text:
        print("FAILED:RES-0095-probe1 sentinel or printed comparison absent from artifact")
        return 1
    print("SUCCESS:RES-0095-probe1 required-N versus planned-N")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
