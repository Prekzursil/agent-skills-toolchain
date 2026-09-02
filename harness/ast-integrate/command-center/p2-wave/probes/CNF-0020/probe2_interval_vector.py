#!/usr/bin/env python3
"""Probe 2: independent interval arithmetic + full n=50 vector + discard control.

Recomputes Wilson (and Clopper-Pearson) from the stored outcome vector.
A summarised verdict (no vector) must be rejected by the overlay.
Last-run-only on 6 red + 1 green must be rejected; honest report is 1/7 green.
A failure reported as deterministic must be 50 of 50.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import validate as V  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0020-flake-frequency.json"
Z95 = 1.959963984540054


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0020-probe2 {msg}")
    return 1


def wilson_independent(k: int, n: int) -> tuple[float, float]:
    """Wilson score interval, inlined so this reviewer does not import interval.py."""
    p = k / n
    z2 = Z95 * Z95
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    rad = (Z95 * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)) / denom
    return max(0.0, center - rad), min(1.0, center + rad)


def binom_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    total = 0.0
    q = 1.0 - p
    for i in range(k + 1):
        total += math.comb(n, i) * (p**i) * (q ** (n - i))
    return total


def binom_sf(k: int, n: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return 1.0 - binom_cdf(k - 1, n, p)


def invert(fn, target: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def clopper_independent(k: int, n: int) -> tuple[float, float]:
    half = 0.025
    if k == 0:
        low = 0.0
    else:
        low = invert(lambda p: binom_sf(k, n, p), half)
    if k == n:
        high = 1.0
    else:
        high = invert(lambda p: -binom_cdf(k, n, p), -half)
    if low > high:
        low, high = high, low
    return max(0.0, min(1.0, low)), max(0.0, min(1.0, high))


def r6(x: float) -> float:
    return float(f"{x:.6f}")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = (
        "SUCCESS:CNF-0020 emitted only when the artifact at output_path exists, "
        "is non-empty, parses against output_schema, and every failure has a full "
        "n=50 outcome vector attached, not a summarised verdict. Any other terminal "
        "state is FAILED:CNF-0020 <classification> with the diagnostic tail attached."
    )
    if sentinel not in text:
        return fail("completion sentinel absent")

    cat_errs = V.catalog_errors(doc)
    if cat_errs:
        print("schema errors", cat_errs[0])
        return fail("artifact failed flake-report schema")
    ov_errs = V.overlay_errors(doc)
    if ov_errs:
        print("overlay errors", ov_errs[0])
        return fail("artifact failed outcome-vector overlay")

    payload = V.flake_payload(doc)
    failures = payload.get("failures") or []
    if not failures:
        return fail("no failures measured")

    table = {row["id"]: row for row in (payload.get("k_of_n_table") or [])}
    saw_intermittent = False
    saw_deterministic = False
    for row in failures:
        fid = row.get("id")
        vec = row.get("outcome_vector") or []
        if len(vec) != 50:
            return fail(f"{fid} outcome_vector length {len(vec)} != 50")
        reds = sum(1 for o in vec if o.get("outcome") == "RED")
        greens = sum(1 for o in vec if o.get("outcome") == "GREEN")
        if reds + greens != 50:
            return fail(f"{fid} outcomes not all RED/GREEN")
        if reds != int(row.get("k")):
            return fail(f"{fid} k={row.get('k')} != vector reds {reds}")
        if int(row.get("n")) != 50:
            return fail(f"{fid} n!=50")
        runs = [o.get("run") for o in vec]
        if runs != list(range(1, 51)):
            return fail(f"{fid} run index not 1..50 complete")
        wlo, whi = wilson_independent(reds, 50)
        clo, chi = clopper_independent(reds, 50)
        iv = row.get("interval") or {}
        if r6(wlo) != float(iv.get("low")) or r6(whi) != float(iv.get("high")):
            return fail(
                f"{fid} wilson mismatch live=({r6(wlo)},{r6(whi)}) "
                f"art=({iv.get('low')},{iv.get('high')})"
            )
        cp = iv.get("clopper_pearson") or {}
        if r6(clo) != float(cp.get("low")) or r6(chi) != float(cp.get("high")):
            return fail(
                f"{fid} clopper-pearson mismatch live=({r6(clo)},{r6(chi)}) "
                f"art=({cp.get('low')},{cp.get('high')})"
            )
        cls = row.get("classification")
        if reds == 50 and cls != "deterministic":
            return fail(f"{fid} k=50 but classification={cls}")
        if 0 < reds < 50 and cls != "intermittent":
            return fail(f"{fid} mixed vector classified {cls}")
        if reds == 0 and cls != "not-reproduced":
            return fail(f"{fid} k=0 classified {cls} (not deterministic)")
        if row.get("claimed_deterministic") and reds != 50:
            return fail(f"{fid} claimed deterministic but k={reds}")
        trow = table.get(fid)
        if not trow or int(trow.get("k")) != reds or int(trow.get("n")) != 50:
            return fail(f"{fid} missing or wrong k_of_n_table row")
        if cls == "intermittent":
            saw_intermittent = True
        if cls == "deterministic":
            saw_deterministic = True
        print(
            f"{fid} k={reds}/50 class={cls} wilson=[{r6(wlo)},{r6(whi)}] "
            f"cp=[{r6(clo)},{r6(chi)}]"
        )

    if not saw_deterministic:
        return fail("no deterministic 50/50 row; classification rule untested")
    if not saw_intermittent:
        return fail("no intermittent row; mixed-vector keep-reds untested")

    dc = payload.get("discard_control") or {}
    live_dc = H.discard_control(list(dc.get("mixed_vector") or H.DISCARD_MIXED))
    if not live_dc["last_run_only_rejected"]:
        return fail("live discard control did not reject last-run-only")
    if dc.get("last_run_only_rejected") is not True:
        return fail("artifact discard_control.last_run_only_rejected is not true")
    honest = dc.get("honest") or {}
    if honest.get("k_red") != 6 or honest.get("n") != 7:
        return fail("honest 6/7 reds not recorded")
    if honest.get("reported_as_catalog_example") != "1/7":
        return fail("catalog 1/7 green example not recorded")
    cheat = dc.get("last_run_only") or {}
    if cheat.get("discarded_reds", 0) < 6:
        return fail("last-run-only did not discard the 6 reds")

    mutant = json.loads(text)
    mpay = V.flake_payload(mutant)
    mpay["failures"][0] = {
        "id": mpay["failures"][0]["id"],
        "k": mpay["failures"][0]["k"],
        "n": 50,
        "classification": mpay["failures"][0]["classification"],
        "interval": mpay["failures"][0]["interval"],
        "conditions": mpay["failures"][0].get("conditions") or {},
    }
    m_errs = V.overlay_errors(mutant)
    if not m_errs:
        return fail("schema accepted summarised verdict after dropping outcome_vector")
    print("summarised-verdict-rejected=True")
    print("last-run-only-rejected=True honest=6/7-red 1/7-green")
    print("SUCCESS:CNF-0020-probe2 interval arithmetic and full n=50 vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
