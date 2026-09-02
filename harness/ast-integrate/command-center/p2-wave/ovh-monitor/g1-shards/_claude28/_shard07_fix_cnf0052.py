#!/usr/bin/env python3
"""shard-07 repair: rebuild CNF-0052 interleaving + interval_arithmetic blocks.

Rebuilt from the artifact's own surviving benchmark arms (raw_ns, orders,
comparisons) using the unit's harness functions, mirroring emit.py exactly.
The envelope rewrite had dropped both top-level blocks.
"""
import sys

sys.path.insert(0, r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\CNF-0052")
sys.path.insert(0, r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_claude28")

import harness as H  # noqa: E402
from _shard07_lib import load, save, refresh_manifest  # noqa: E402

ART = "command-center/confirmation/CNF-0052-benchmark-regression.json"
N = H.N_REPS


def interval_block(name, order, raw_a, raw_b, noise):
    sa = H.summarize(raw_a)
    sb = H.summarize(raw_b)
    cls = H.classify(sa, sb, noise)
    def arm(s):
        return {
            "ci95": [s["ci95_lo_ns"], s["ci95_hi_ns"]],
            "iqr_ns": s["iqr_ns"],
            "mean_ns": s["mean_ns"],
            "median_ns": s["median_ns"],
            "plug_in": (
                f"{s['mean_ns']:.6f} \u00b1 {s['t_crit']:.9f} * "
                f"{s['stdev_ns']:.6f} / sqrt({s['n']})"
            ),
            "stdev_ns": s["stdev_ns"],
        }
    return {
        "A": arm(sa),
        "B": arm(sb),
        "benchmark": name,
        "ci_overlap": cls["ci_overlap"],
        "delta_median_ns": cls["delta_median_ns"],
        "formula_ci95": sa["formula_ci95"],
        "formula_mean": sa["formula_mean"],
        "formula_sample_variance": sa["formula_sample_variance"],
        "interleaving_order": order,
        "label": cls["label"],
        "n": sa["n"],
        "noise_floor_ns": cls["noise_floor_ns"],
        "raw_A_ns": raw_a,
        "raw_B_ns": raw_b,
        "t_crit": sa["t_crit"],
        "t_crit_df": sa["n"] - 1,
    }


def main() -> None:
    doc = load(ART)
    benches = {b["id"]: b for b in doc["benchmarks"]}
    ident = benches["catalog-checksum-identity"]
    reg = benches["catalog-checksum-regression-control"]
    arms_i = {a["id"]: a for a in ident["arms"]}
    arms_r = {a["id"]: a for a in reg["arms"]}

    doc["interleaving"] = {
        "blocked_control": {
            "blocked": True,
            "interleaved": False,
            "order": ["A"] * N + ["B"] * N,
            "reason": (
                "blocked A-then-B confounds thermal and memory drift with the change"
            ),
            "rejected_as_confounded": True,
        },
        "identity_interleaved": True,
        "identity_order": ident["interleaving"]["order"],
        "regression_control_interleaved": True,
        "regression_control_order": reg["interleaving"]["order"],
        "required": "A B A B, not blocked A..A B..B",
    }
    doc["interval_arithmetic"] = {
        "df": 10,
        "t_crit": H.T_CRIT_DF10,
        "formula_ci95": "mean \u00b1 t_{n-1,0.975} * s / sqrt(n)",
        "formula_iqr": "quantile(0.75)-quantile(0.25)",
        "formula_mean": "sum(x_i)/n",
        "formula_median": "linear-interpolated quantile p=0.5",
        "formula_sample_variance": "sum((x_i-mean)^2)/(n-1)",
        "identity": interval_block(
            "catalog-checksum-identity",
            ident["interleaving"]["order"],
            arms_i["A"]["raw_ns"],
            arms_i["B"]["raw_ns"],
            float(ident["comparison"]["noise_floor_ns"]),
        ),
        "regression_control": interval_block(
            "catalog-checksum-regression-control",
            reg["interleaving"]["order"],
            arms_r["A"]["raw_ns"],
            arms_r["B"]["raw_ns"],
            float(reg["comparison"]["noise_floor_ns"]),
        ),
    }
    doc["field_restoration"] = (
        "interleaving and interval_arithmetic rebuilt 2026-08-28 from the "
        "artifact's own benchmark arms via harness.summarize/classify after an "
        "envelope rewrite dropped them"
    )
    save(ART, doc)

    ident_lbl = doc["interval_arithmetic"]["identity"]["label"]
    reg_lbl = doc["interval_arithmetic"]["regression_control"]["label"]
    stored_i = ident["comparison"]["label"]
    stored_r = reg["comparison"]["label"]
    print(f"identity label rebuilt={ident_lbl} stored={stored_i}")
    print(f"regression label rebuilt={reg_lbl} stored={stored_r}")
    assert ident_lbl == stored_i and reg_lbl == stored_r, "label drift on rebuild"
    refresh_manifest("CNF-0052", [ART])


if __name__ == "__main__":
    main()
