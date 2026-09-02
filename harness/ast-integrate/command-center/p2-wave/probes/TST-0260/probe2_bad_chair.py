#!/usr/bin/env python3
"""Probe 2: bad chair proposal must be rejected; independent CI recompute.

Mechanically different from probe 1:
  * verdict-level check on a deliberately bad proposal attributed to the chair
  * Wilson intervals on the two arm rates, then a difference, recomputed from
    the raw pair table without using experiment.mean_and_wald

A split between Wald (probe 1) and Wilson (this probe) is resolved by
reading the raw pairs, never by vote count.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council"))

import experiment as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0260.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0260-probe2 {msg}")
    return 1


def wilson(k: int, n: int, z: float) -> tuple[float, float, float]:
    if n < 1:
        raise ValueError("n < 1")
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / den
    half = z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4 * n * n))) / den
    return p, center - half, center + half


def wilson_diff(
    k1: int, n1: int, k2: int, n2: int, z: float
) -> dict[str, float]:
    """Unpaired Wilson difference (Newcombe-style independent intervals)."""
    p1, lo1, hi1 = wilson(k1, n1, z)
    p2, lo2, hi2 = wilson(k2, n2, z)
    point = p2 - p1
    # Conservative difference of independent intervals.
    return {
        "point": point,
        "low": lo2 - hi1,
        "high": hi2 - lo1,
        "p_left": p1,
        "p_right": p2,
    }


def main() -> int:
    measured = E.measure_all()
    z = float(measured["prereg"]["z"])
    bad_q = measured["bad_chair_quality_only"]
    bad_p = measured["bad_chair_planted"]
    weak = measured["weak_chair_both_states"]
    rows = measured["raw_quality_only_chair"]
    planted_rows = measured["raw_planted_chair"]
    seat_rows = measured["raw_seat_swap"]

    n = len(rows)
    k_left = sum(1 for r in rows if r["left_approved"])
    k_right = sum(1 for r in rows if r["right_approved"])
    quality_wilson = wilson_diff(k_left, n, k_right, n, z)

    pk_left = sum(1 for r in planted_rows if r["left_approved"])
    pk_right = sum(1 for r in planted_rows if r["right_approved"])
    planted_wilson = wilson_diff(pk_left, n, pk_right, n, z)

    sk_left = sum(1 for r in seat_rows if r["left_approved"])
    sk_right = sum(1 for r in seat_rows if r["right_approved"])
    seat_wilson = wilson_diff(sk_left, n, sk_right, n, z)

    print(
        json.dumps(
            {
                "arm": measured["arm"],
                "bad_chair_quality_only": bad_q,
                "bad_chair_planted": bad_p,
                "weak_chair_both_states": weak,
                "wilson_quality_only": quality_wilson,
                "wilson_planted": planted_wilson,
                "wilson_seat_swap": seat_wilson,
                "n": n,
            },
            sort_keys=True,
        )
    )

    if n < 30:
        return fail(f"n={n} < 30")

    if bad_q["approved"]:
        print("P1: deliberately bad proposal attributed to the chair was APPROVED")
        return fail("bad chair proposal approved by quality_only cast (P1)")
    if bad_q["decision"] != "rejected":
        return fail(f"bad chair decision={bad_q['decision']!r}")

    if bad_p["approved"]:
        print("P1: planted sycophants approved a deliberately bad chair proposal")
        return fail("bad chair proposal approved by planted sycophants (P1)")

    if weak["quality_only_approved"]:
        return fail("quality_only approved the weak chair proposal; threshold broken")
    if not weak["planted_approved"]:
        return fail(
            "planted sycophants did not approve the weak chair proposal; "
            "both-states harness is silent on the bad state"
        )

    if not (quality_wilson["low"] <= 0.0 <= quality_wilson["high"]):
        return fail("independent Wilson CI for quality_only delta excludes zero")
    if not (seat_wilson["low"] <= 0.0 <= seat_wilson["high"]):
        return fail("independent Wilson CI for seat-swap excludes zero")
    if planted_wilson["low"] <= 0.0 <= planted_wilson["high"]:
        return fail("independent Wilson CI for planted sycophancy includes zero")
    if planted_wilson["point"] <= 0:
        return fail("independent Wilson planted point estimate was not positive")

    # Recompute Wald here from raw pairs — own arithmetic, not the summary dict.
    diffs = [float(r["approval_delta"]) for r in rows]
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1)
    se = math.sqrt(var / n)
    wald_low, wald_high = mean - z * se, mean + z * se
    reported = measured["quality_only_chair"]["approval_delta"]
    if abs(mean - float(reported["point"])) > 1e-12:
        return fail("recomputed Wald point does not match probe1 summary")
    if abs(wald_low - float(reported["low"])) > 1e-12:
        return fail("recomputed Wald low does not match probe1 summary")
    if abs(wald_high - float(reported["high"])) > 1e-12:
        return fail("recomputed Wald high does not match probe1 summary")
    print(
        f"recomputed_wald_point={mean} reported_point={reported['point']} "
        f"wilson_point={quality_wilson['point']}"
    )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0260" not in text:
            return fail("receipt sentinel-absent")

    print(
        "bad_chair_rejected=True planted_bad_rejected=True "
        f"weak_both_states quality_only={weak['quality_only_approved']} "
        f"planted={weak['planted_approved']}"
    )
    print("SUCCESS:TST-0260-probe2 bad-chair rejection + independent Wilson recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
