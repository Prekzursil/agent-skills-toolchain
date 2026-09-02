#!/usr/bin/env python3
"""Probe 1: dispersion AND accuracy per round on the scored set (signal a).

PASS requires:
  * honest anonymous Delphi publishes raw IQR and individual MAE every round
  * first-to-last IQR falls and MAE falls (not a dispersion-only story)
  * every scored item classifies CONVERGENCE
  * the runtime allows confident consensus only on that joint condition
  * the first-round spread is load-bearing (not a vacuous already-tight panel)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0291.json"
SENTINEL = "SUCCESS:TST-0291"


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def fail(msg: str) -> int:
    print(f"FAILED:TST-0291-probe1 {msg}")
    return 1


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    qs = E.load_questions()
    if len(qs) < 8:
        return fail(f"scored set too small n={len(qs)}")

    panel = E.run_panel(qs, planted=False, mode="anonymous")
    panel_b = E.run_panel(qs, planted=False, mode="anonymous")
    if panel["transcript_sha256"] != panel_b["transcript_sha256"]:
        return fail("same-input re-run hash mismatch (simulator not deterministic)")

    counts = panel["kind_counts"]
    if counts[E.KIND_CONVERGENCE] != len(qs):
        return fail(f"honest panel not all CONVERGENCE counts={counts}")
    if counts[E.KIND_HERDING] != 0:
        return fail(f"honest panel herding_items={counts[E.KIND_HERDING]}")
    if not panel["panel_classification"]["allow_confident_consensus"]:
        return fail("honest panel withheld consensus")

    means = panel["per_round_means"]
    if len(means) != E.N_ROUNDS:
        return fail(f"missing per-round rows n={len(means)}")
    for row in means:
        for key in ("mean_iqr", "mean_individual_mae", "mean_group_abs_error"):
            if key not in row or not isinstance(row[key], (int, float)):
                return fail(f"per-round raw {key} absent")
    first, last = means[0], means[-1]
    if first["mean_relative_iqr"] < 0.05:
        return fail("first-round relative IQR too small (vacuous spread)")
    if not (last["mean_iqr"] < first["mean_iqr"] * E.TIGHTEN_RATIO):
        return fail(
            f"dispersion did not fall iqr0={first['mean_iqr']} iqr1={last['mean_iqr']}"
        )
    if not (last["mean_individual_mae"] < first["mean_individual_mae"] * E.IMPROVE_RATIO):
        return fail(
            f"accuracy did not improve mae0={first['mean_individual_mae']} "
            f"mae1={last['mean_individual_mae']}"
        )

    per_q = []
    for item in panel["per_question"]:
        cls = item["classification"]
        cons = item["consensus"]
        if cls["kind"] != E.KIND_CONVERGENCE:
            return fail(f"{item['question_id']} kind={cls['kind']}")
        if not cons["confident_consensus"]:
            return fail(f"{item['question_id']} consensus withheld")
        if not cls["dispersion_fell"] or not cls["mae_improved"]:
            return fail(f"{item['question_id']} joint condition failed {cls}")
        # Group error must be published even when it is flat.
        r0, r1 = item["rounds"][0], item["rounds"][-1]
        per_q.append(
            {
                "id": item["question_id"],
                "iqr0": r0["iqr"],
                "iqr1": r1["iqr"],
                "mae0": r0["individual_mae"],
                "mae1": r1["individual_mae"],
                "group_abs_error0": r0["group_abs_error"],
                "group_abs_error1": r1["group_abs_error"],
            }
        )

    out = {
        "pass": True,
        "probe": "probe1-dispersion-and-accuracy",
        "unit_id": "TST-0291",
        "n_questions": len(qs),
        "kind_counts": counts,
        "allow_confident_consensus": True,
        "deterministic_rerun": True,
        "transcript_sha256": panel["transcript_sha256"],
        "per_round_means": means,
        "per_question_raw": per_q,
        "iqr_first": first["mean_iqr"],
        "iqr_last": last["mean_iqr"],
        "mae_first": first["mean_individual_mae"],
        "mae_last": last["mean_individual_mae"],
        "relative_iqr_first": first["mean_relative_iqr"],
        "relative_iqr_last": last["mean_relative_iqr"],
        "relative_mae_first": first["mean_relative_mae"],
        "relative_mae_last": last["mean_relative_mae"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "honest_anonymous CONVERGENCE="
        f"{counts[E.KIND_CONVERGENCE]}/{len(qs)} "
        f"iqr={first['mean_relative_iqr']:.4f}->{last['mean_relative_iqr']:.4f} "
        f"mae={first['mean_relative_mae']:.4f}->{last['mean_relative_mae']:.4f} "
        "consensus=allowed"
    )
    print("SUCCESS:TST-0291-probe1 dispersion and accuracy per round")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
