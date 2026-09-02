#!/usr/bin/env python3
"""Probe 1: herding control across Delphi feedback modes.

Compares estimate variance and MAE vs theta after one feedback round
under median_only, full_distribution, and arguments on the heterogeneous
wrong-majority panel. Collapse without accuracy gain is herding.

A second, independent measurement (second-moment variance identity)
must agree with the population-variance column or this probe fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import delphi as D  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0035-delphi-topology-iterated-anonymous-estimates-with-controll.md"
)
TOL = 1e-9
NAMED = ("median_only", "full_distribution", "arguments")


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0035-probe1 {msg}")
    return 1


def main() -> int:
    panel = D.load_named("panel_heterogeneous.json")
    live = {mode: D.run_mode(panel, mode) for mode in NAMED}
    for mode, run in live.items():
        for i, rnd in enumerate(run["rounds"]):
            a = rnd["variance"]
            b = rnd["variance_second_moment"]
            print(
                f"identity mode={mode} round={i} "
                f"pop_var={a:.12f} second_moment={b:.12f}"
            )
            if abs(a - b) > TOL:
                return fail(f"variance-identity {mode} round {i}")
        g = run["gate_round1"]
        s0, s1 = run["rounds"][0], run["rounds"][1]
        print(
            f"mode={mode} herding={g['herding']} verdict={g['verdict']} "
            f"reason={g['reason']} var0={s0['variance']:.12f} "
            f"var1={s1['variance']:.12f} mae0={s0['mae']:.12f} "
            f"mae1={s1['mae']:.12f} median0={s0['median']:.12f} "
            f"median1={s1['median']:.12f}"
        )
    if not live["median_only"]["gate_round1"]["herding"]:
        return fail("median_only must herd on wrong-majority median")
    if not live["full_distribution"]["gate_round1"]["herding"]:
        return fail("full_distribution must herd when median stays labeled")
    arg = live["arguments"]["gate_round1"]
    if arg["herding"] or arg["verdict"] != "REVISION":
        return fail("arguments must revise (not herd) when evidence differs")
    if live["arguments"]["rounds"][1]["mae"] >= live["median_only"]["rounds"][1]["mae"]:
        return fail("arguments MAE must beat median_only MAE")
    if live["full_distribution"]["rounds"][1]["mae"] <= live["arguments"]["rounds"][1]["mae"]:
        return fail("full_distribution MAE must be worse than arguments MAE")

    if OUT.is_file():
        note = json.loads(OUT.read_text(encoding="utf-8"))
        table = (note.get("herding_experiment") or {}).get("heterogeneous") or {}
        if not table:
            return fail("artifact missing herding_experiment.heterogeneous")
        for mode in NAMED:
            row = table.get(mode) or {}
            run = live[mode]
            for key, live_v in (
                ("var0", run["rounds"][0]["variance"]),
                ("var1", run["rounds"][1]["variance"]),
                ("mae0", run["rounds"][0]["mae"]),
                ("mae1", run["rounds"][1]["mae"]),
            ):
                claimed = float(row[key])
                if abs(claimed - live_v) > TOL:
                    return fail(f"artifact {mode}.{key} {claimed} != live {live_v}")
            if bool(row.get("herding")) != bool(run["gate_round1"]["herding"]):
                return fail(f"artifact {mode}.herding disagrees with live gate")
        print("artifact_table_matches_live=True")
    else:
        print("artifact_absent_skip_table_check=True")

    print("SUCCESS:CNL-0035-probe1 herding control across feedback modes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
