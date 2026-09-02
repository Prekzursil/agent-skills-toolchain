#!/usr/bin/env python3
"""Probe 2: herding control, anonymity contrast, independent recount (signal b).

Mechanically different from probe 1:
  * does not PASS on the honest anonymous scored-set trajectory
  * plants one confident-but-wrong seat and requires HERDING + withheld consensus
  * naive dispersion-only claim must disagree (the overclaim this unit forbids)
  * attributed vs unattributed feedback on the same plant must differ
  * IQR and MAE are re-derived from raw per-seat estimates with local arithmetic
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0291.json"
SENTINEL = "SUCCESS:TST-0291"

NEGATIVE_CONTROL_VERBATIM = (
    "NEGATIVE CONTROL (dispersion-only convergence claim): On the planted "
    "attributed panel, IQR falls while individual MAE and |median-truth| rise. "
    "A claim that treats falling dispersion as convergence therefore returns "
    "CONVERGENCE and would allow a confident consensus. The check is meant to "
    "reject that claim: classify_trajectory must return HERDING and "
    "maybe_report_consensus must set confident_consensus=false with "
    "withheld_reason=herding."
)


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
    print(f"FAILED:TST-0291-probe2 {msg}")
    return 1


def recount_percentile(xs: list[float], p: float) -> float:
    """Linear-interpolated percentile, local copy (not engine.percentile)."""
    ys = sorted(float(v) for v in xs)
    if not ys:
        raise ValueError("empty")
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return ys[lo]
    w = k - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def recount_median(xs: list[float]) -> float:
    ys = sorted(float(v) for v in xs)
    n = len(ys)
    mid = n // 2
    if n % 2:
        return ys[mid]
    return 0.5 * (ys[mid - 1] + ys[mid])


def recount_iqr(xs: list[float]) -> float:
    return recount_percentile(xs, 0.75) - recount_percentile(xs, 0.25)


def recount_mae(xs: list[float], truth: float) -> float:
    return sum(abs(float(v) - truth) for v in xs) / len(xs)


def recount_item(item: dict) -> dict:
    rows = []
    for rnd in item["rounds"]:
        est = [float(s["estimate"]) for s in rnd["estimates"]]
        truth = float(item["truth"])
        iqr_v = recount_iqr(est)
        mae_v = recount_mae(est, truth)
        gerr = abs(recount_median(est) - truth)
        if abs(iqr_v - float(rnd["iqr"])) > 1e-9:
            raise AssertionError(
                f"iqr recount mismatch {item['question_id']} r={rnd['round']} "
                f"{iqr_v} vs {rnd['iqr']}"
            )
        if abs(mae_v - float(rnd["individual_mae"])) > 1e-9:
            raise AssertionError(
                f"mae recount mismatch {item['question_id']} r={rnd['round']} "
                f"{mae_v} vs {rnd['individual_mae']}"
            )
        if abs(gerr - float(rnd["group_abs_error"])) > 1e-9:
            raise AssertionError(
                f"group-error recount mismatch {item['question_id']} r={rnd['round']}"
            )
        rows.append({"round": rnd["round"], "iqr": iqr_v, "mae": mae_v, "group_abs_error": gerr})
    first, last = rows[0], rows[-1]
    disp_fell = last["iqr"] < first["iqr"] * E.TIGHTEN_RATIO
    mae_improved = last["mae"] < first["mae"] * E.IMPROVE_RATIO
    mae_worsened = last["mae"] > first["mae"] * E.WORSEN_RATIO
    group_worsened = last["group_abs_error"] > first["group_abs_error"] * E.WORSEN_RATIO
    if not disp_fell:
        kind = E.KIND_NO_TIGHTENING
        allow = False
    elif mae_improved and not group_worsened:
        kind = E.KIND_CONVERGENCE
        allow = True
    else:
        kind = E.KIND_HERDING
        allow = False
    return {
        "question_id": item["question_id"],
        "kind": kind,
        "allow_confident_consensus": allow,
        "iqr0": first["iqr"],
        "iqr1": last["iqr"],
        "mae0": first["mae"],
        "mae1": last["mae"],
        "group0": first["group_abs_error"],
        "group1": last["group_abs_error"],
        "disp_fell": disp_fell,
        "mae_improved": mae_improved,
        "mae_worsened": mae_worsened,
        "group_worsened": group_worsened,
    }


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    qs = E.load_questions()
    honest = E.run_panel(qs, planted=False, mode="anonymous")
    planted_attr = E.run_panel(qs, planted=True, mode="attributed")
    planted_anon = E.run_panel(qs, planted=True, mode="anonymous")

    # Both-states: detector silent on honest, fires on planted attributed.
    if honest["kind_counts"][E.KIND_HERDING] != 0:
        return fail("herding detector fired on honest anonymous panel")
    if not honest["panel_classification"]["allow_confident_consensus"]:
        return fail("honest panel consensus not allowed")
    if planted_attr["kind_counts"][E.KIND_HERDING] != len(qs):
        return fail(
            f"planted attributed herding_items="
            f"{planted_attr['kind_counts'][E.KIND_HERDING]} expected={len(qs)}"
        )
    if planted_attr["panel_classification"]["allow_confident_consensus"]:
        return fail("planted attributed panel reported confident consensus")

    naive_agrees = 0
    naive_overclaims = 0
    recounted = []
    try:
        for item in planted_attr["per_question"]:
            rec = recount_item(item)
            recounted.append(rec)
            if rec["kind"] != E.KIND_HERDING:
                return fail(f"recount {item['question_id']} kind={rec['kind']}")
            if rec["allow_confident_consensus"]:
                return fail(f"recount {item['question_id']} allowed consensus")
            if rec["kind"] != item["classification"]["kind"]:
                return fail(f"recount/engine kind mismatch {item['question_id']}")
            if not rec["disp_fell"]:
                return fail(f"{item['question_id']} IQR did not fall")
            if not (rec["mae_worsened"] or rec["group_worsened"] or not rec["mae_improved"]):
                return fail(f"{item['question_id']} accuracy did not degrade/flat")
            naive = item["naive_dispersion_only"]
            if naive["kind"] == E.KIND_CONVERGENCE and naive["allow_confident_consensus"]:
                naive_overclaims += 1
            if naive["kind"] == item["classification"]["kind"]:
                naive_agrees += 1
            cons = item["consensus"]
            if cons["confident_consensus"] or not cons["withheld"]:
                return fail(f"{item['question_id']} consensus not withheld")
            if cons["withheld_reason"] != "herding":
                return fail(
                    f"{item['question_id']} withheld_reason={cons['withheld_reason']}"
                )
            if not item["overclaim_disagreement"]:
                return fail(f"{item['question_id']} naive claim agreed with classifier")
    except AssertionError as exc:
        return fail(str(exc))

    if naive_overclaims != len(qs):
        return fail(f"naive overclaim count={naive_overclaims} expected={len(qs)}")
    if naive_agrees != 0:
        return fail("naive dispersion-only unexpectedly matched real classifier")

    # Anonymity: same plant, attributed vs unattributed.
    if planted_anon["kind_counts"][E.KIND_HERDING] != 0:
        return fail(
            f"anonymous plant unexpectedly herded "
            f"{planted_anon['kind_counts']}"
        )
    if not planted_anon["panel_classification"]["allow_confident_consensus"]:
        return fail("anonymous plant (median feedback) withheld consensus")
    if planted_anon["transcript_sha256"] == planted_attr["transcript_sha256"]:
        return fail("attributed and anonymous transcripts are identical")

    last_anon = planted_anon["per_round_means"][-1]
    last_attr = planted_attr["per_round_means"][-1]
    first_anon = planted_anon["per_round_means"][0]
    first_attr = planted_attr["per_round_means"][0]
    if abs(first_anon["mean_relative_mae"] - first_attr["mean_relative_mae"]) > 1e-12:
        return fail("round-0 MAE differs across feedback modes (confound)")
    delta_mae = last_attr["mean_relative_mae"] - last_anon["mean_relative_mae"]
    if delta_mae <= 0:
        return fail(f"attributed MAE not worse than anonymous delta={delta_mae}")
    delta_g = last_attr["mean_group_abs_error"] - last_anon["mean_group_abs_error"]
    if delta_g <= 0:
        return fail(f"attributed group error not worse than anonymous delta={delta_g}")

    # Effect-size interval from per-question mae ratios on the planted attributed arm.
    ratios = [float(it["classification"]["mae_ratio"]) for it in planted_attr["per_question"]]
    ratios_sorted = sorted(ratios)
    effect = {
        "mae_ratio_min": ratios_sorted[0],
        "mae_ratio_median": ratios_sorted[len(ratios_sorted) // 2],
        "mae_ratio_max": ratios_sorted[-1],
        "n": len(ratios),
    }

    out = {
        "pass": True,
        "probe": "probe2-herding-and-anonymity",
        "unit_id": "TST-0291",
        "negative_control_verbatim": NEGATIVE_CONTROL_VERBATIM,
        "both_states": {
            "honest_anonymous_herding_items": honest["kind_counts"][E.KIND_HERDING],
            "honest_anonymous_allow_consensus": honest["panel_classification"][
                "allow_confident_consensus"
            ],
            "planted_attributed_herding_items": planted_attr["kind_counts"][E.KIND_HERDING],
            "planted_attributed_allow_consensus": planted_attr["panel_classification"][
                "allow_confident_consensus"
            ],
        },
        "naive_overclaims": naive_overclaims,
        "naive_agrees_with_classifier": naive_agrees,
        "anonymity": {
            "anonymous_herding_items": planted_anon["kind_counts"][E.KIND_HERDING],
            "attributed_herding_items": planted_attr["kind_counts"][E.KIND_HERDING],
            "anonymous_allow_consensus": planted_anon["panel_classification"][
                "allow_confident_consensus"
            ],
            "attributed_allow_consensus": planted_attr["panel_classification"][
                "allow_confident_consensus"
            ],
            "delta_final_relative_mae_attributed_minus_anonymous": delta_mae,
            "delta_final_group_abs_error_attributed_minus_anonymous": delta_g,
            "round0_relative_mae_anonymous": first_anon["mean_relative_mae"],
            "round0_relative_mae_attributed": first_attr["mean_relative_mae"],
            "final_relative_mae_anonymous": last_anon["mean_relative_mae"],
            "final_relative_mae_attributed": last_attr["mean_relative_mae"],
        },
        "effect_size_from_raw_recount": effect,
        "recounted_items": len(recounted),
        "planted_attributed_per_round_means": planted_attr["per_round_means"],
        "planted_anonymous_per_round_means": planted_anon["per_round_means"],
    }
    print(json.dumps(out, sort_keys=True, default=str))
    print(
        "herding_items="
        f"{planted_attr['kind_counts'][E.KIND_HERDING]}/{len(qs)} "
        f"naive_overclaims={naive_overclaims} "
        f"anon_herding={planted_anon['kind_counts'][E.KIND_HERDING]} "
        f"delta_rel_mae={delta_mae:.4f} "
        f"mae_ratio=[{effect['mae_ratio_min']:.3f},{effect['mae_ratio_max']:.3f}]"
    )
    print("SUCCESS:TST-0291-probe2 herding flagged; anonymity differs; recount matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
