#!/usr/bin/env python3
"""Probe 2: negative control + independent recount.

FIRES on the planted-bad homogeneous unanchored_guess panel (arguments
mode still collapses variance with no reliability differential).
SILENT on the known-good heterogeneous arguments run (revision).

Reviewer recount: recompute variance via the second-moment identity from
the fixture estimates, not from the author's prose. A numeric disagreement
with the design note blocks the unit.
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


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0035-probe2 {msg}")
    return 1


def line_for(tag: str, panel_id: str, mode: str, run: dict) -> str:
    g = run["gate_round1"]
    s0, s1 = run["rounds"][0], run["rounds"][1]
    fire = "FIRE" if g["herding"] else "SILENT"
    return (
        f"{tag} panel={panel_id} mode={mode} check=herding_gate {fire} "
        f"herding={g['herding']} verdict={g['verdict']} reason={g['reason']} "
        f"var0={s0['variance']:.12f} var1={s1['variance']:.12f} "
        f"mae0={s0['mae']:.12f} mae1={s1['mae']:.12f}"
    )


def main() -> int:
    bad_panel = D.load_named("panel_homogeneous_guesses.json")
    good_panel = D.load_named("panel_heterogeneous.json")
    bad = D.run_mode(bad_panel, "arguments")
    good = D.run_mode(good_panel, "arguments")

    bad_line = line_for("NEGATIVE_CONTROL rejected_state", bad_panel["id"], "arguments", bad)
    good_line = line_for("NEGATIVE_CONTROL known_good", good_panel["id"], "arguments", good)
    print(bad_line)
    print(good_line)

    if not bad["gate_round1"]["herding"]:
        return fail("check did not FIRE on homogeneous arguments (planted-bad)")
    if good["gate_round1"]["herding"]:
        return fail("check was not SILENT on heterogeneous arguments (known-good)")
    print("fired_on_bad=True silent_on_good=True")

    # Independent recount: second-moment variance from fixture private signals.
    xs = D.private_signals(good_panel)
    recount_var = D.second_moment_variance(xs)
    author_var = D.population_variance(xs)
    print(f"recount_var0_second_moment={recount_var:.12f} author_pop_var={author_var:.12f}")
    if abs(recount_var - author_var) > TOL:
        return fail("reviewer recount disagrees with population variance on fixture")

    if not OUT.is_file():
        return fail("design note absent; cannot recount artifact numbers")
    note = json.loads(OUT.read_text(encoding="utf-8"))
    verbatim = ((note.get("negative_control") or {}).get("verbatim")) or ""
    if "FIRE" not in verbatim or "SILENT" not in verbatim:
        # also accept negative_controls list
        ctrls = note.get("negative_controls") or []
        blob = verbatim + json.dumps(ctrls)
        if "FIRE" not in blob or "SILENT" not in blob:
            return fail("artifact negative control missing FIRE/SILENT verbatim")

    het = (note.get("herding_experiment") or {}).get("heterogeneous") or {}
    hom = (note.get("herding_experiment") or {}).get("homogeneous") or {}
    live_het = D.run_mode(good_panel, "arguments")
    live_hom = D.run_mode(bad_panel, "arguments")
    for label, row, run in (
        ("het.arguments", het.get("arguments") or {}, live_het),
        ("hom.arguments", hom.get("arguments") or {}, live_hom),
    ):
        if not row:
            return fail(f"artifact missing {label}")
        claimed_var0 = float(row["var0"])
        live_var0 = run["rounds"][0]["variance"]
        recount = D.second_moment_variance(run["rounds"][0]["estimates"])
        print(
            f"recount {label} claimed_var0={claimed_var0:.12f} "
            f"live={live_var0:.12f} second_moment={recount:.12f}"
        )
        if abs(claimed_var0 - live_var0) > TOL or abs(claimed_var0 - recount) > TOL:
            return fail(f"reviewer recount mismatch on {label}")
        if bool(row.get("herding")) != bool(run["gate_round1"]["herding"]):
            return fail(f"artifact herding flag mismatch on {label}")

    print("SUCCESS:CNL-0035-probe2 negative control and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
