#!/usr/bin/env python3
"""Probe 2: recompute interval arithmetic; noise-floor labeling; blocked design."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0052-probe2 {msg}")
    return 1


def close(a: float, b: float, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def check_stats(raw: list, stored: dict, tag: str) -> str | None:
    got = H.summarize(raw)
    for key in (
        "n",
        "median_ns",
        "iqr_ns",
        "mean_ns",
        "ci95_lo_ns",
        "ci95_hi_ns",
        "stdev_ns",
    ):
        if key == "n":
            if got["n"] != stored["n"]:
                return f"{tag} n {got['n']}!={stored['n']}"
            continue
        if not close(float(got[key]), float(stored[key])):
            return f"{tag} {key} recomputed={got[key]} stored={stored[key]}"
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if H.COMPLETION_SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("completion_sentinel absent")
    body = H.payload(doc)

    ia = body.get("interval_arithmetic") or {}
    if abs(float(ia.get("t_crit") or 0) - H.T_CRIT_DF10) > 1e-9:
        return fail("t_crit mismatch")
    if ia.get("df") != 10:
        return fail("df")
    for req in (
        "formula_mean",
        "formula_sample_variance",
        "formula_ci95",
        "identity",
        "regression_control",
    ):
        if req not in ia:
            return fail(f"missing interval_arithmetic.{req}")

    benches = {b["id"]: b for b in (body.get("benchmarks") or []) if isinstance(b, dict)}
    ident_b = benches.get("catalog-checksum-identity")
    reg_b = benches.get("catalog-checksum-regression-control")
    if not ident_b or not reg_b:
        return fail("named benchmarks missing")

    for bid, b in (("identity", ident_b), ("regression", reg_b)):
        arms = {a["id"]: a for a in b.get("arms") or []}
        for arm_id in ("A", "B"):
            err = check_stats(
                arms[arm_id]["raw_ns"], arms[arm_id]["statistics"], f"{bid}.{arm_id}"
            )
            if err:
                return fail(err)
        sa = H.summarize(arms["A"]["raw_ns"])
        sb = H.summarize(arms["B"]["raw_ns"])
        noise = float((b.get("comparison") or {}).get("noise_floor_ns") or sa["iqr_ns"])
        cls = H.classify(sa, sb, noise)
        stored = b.get("comparison") or {}
        if cls["label"] != stored.get("label"):
            return fail(
                f"{bid} label recomputed={cls['label']} stored={stored.get('label')}"
            )
        if (
            abs(cls["delta_median_ns"]) <= cls["noise_floor_ns"]
            and stored.get("label") == "improvement"
        ):
            return fail(f"{bid} inside-floor labeled improvement")

    ident_label = ident_b["comparison"]["label"]
    if ident_label == "improvement":
        return fail("identity pair labeled improvement")
    if ident_label != "no_measurable_change":
        delta = ident_b["comparison"]["delta_median_ns"]
        noise = ident_b["comparison"]["noise_floor_ns"]
        if abs(delta) <= noise:
            return fail("identity inside floor but not no_measurable_change")
        return fail(f"identity label={ident_label}")

    if reg_b["comparison"]["label"] != "regression":
        return fail(f"regression control label={reg_b['comparison']['label']}")

    fake_a = H.summarize([1000 + i for i in range(11)])
    fake_b = H.summarize([1005 + i for i in range(11)])
    fake_noise = max(fake_a["iqr_ns"], 50.0)
    fake = H.classify(fake_a, fake_b, fake_noise)
    if fake["label"] != "no_measurable_change":
        return fail(f"synthetic inside-floor label={fake['label']}")

    slow = H.summarize([10000 + 10 * i for i in range(11)])
    fast = H.summarize([1000 + i for i in range(11)])
    big = H.classify(fast, slow, fast["iqr_ns"])
    if big["label"] != "regression":
        return fail(f"synthetic regression label={big['label']}")

    rows = H.make_rows()
    blocked = H.run_blocked(H.snap_a, H.snap_b_slow, rows)
    if not blocked["blocked"] or blocked["interleaved"]:
        return fail("blocked runner did not produce blocked order")
    recorded = (body.get("interleaving") or {}).get("blocked_control") or {}
    if not recorded.get("rejected_as_confounded"):
        return fail("artifact did not reject blocked design")

    plug = (ia.get("identity") or {}).get("A") or {}
    if "plug_in" not in plug:
        return fail("missing CI plug-in string")

    out = {
        "blocked_rejected": True,
        "identity_label": ident_label,
        "pass": True,
        "probe": "probe2-interval-arithmetic",
        "regression_control_label": "regression",
        "synthetic_inside_floor": fake["label"],
        "synthetic_regression": big["label"],
        "t_crit": H.T_CRIT_DF10,
        "unit_id": H.UNIT,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0052-probe2 interval arithmetic and noise-floor rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
