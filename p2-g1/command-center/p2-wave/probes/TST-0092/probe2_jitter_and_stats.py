#!/usr/bin/env python3
"""TST-0092 probe2: jitter both-states + IQR re-derivation (live, fail-closed).

Rebuild 2026-10-26 (shard19-w3 resume): prior probe lost to the mid-flight
builder death. Verifies:
  * jitter is actually applied: jitter_frac>0 gives unique timestamps and
    non-constant inter-arrival; jitter_frac=0 gives constant deltas and is
    still within cap (both-states discriminator); burst twin has identical
    timestamps (known-broken);
  * the statistics-reviewer obligation: q1/median/q3/IQR re-derived from the
    receipt's raw 1000-value max_window_count list (linear-interpolation
    quartiles), matching the recorded band (4, 8, 20, IQR 16; min 1, max 100).
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "TST-0092"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def main() -> int:
    try:
        sys.path.insert(0, str(REPO))
        from tools.arrival_scheduler import scheduler as S
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 scheduler-import:" + type(exc).__name__)
        return 1
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1

    # --- Jitter both-states, live (recorded conditions: seed MASTER_SEED+7, n=80, cap=10).
    seed = S.MASTER_SEED + 7
    jit = S.schedule_arrivals(80, 10, seed=seed, jitter_frac=0.4).times_ticks
    chk(len(set(jit)) == len(jit), "jittered-timestamps-not-unique")
    deltas = [jit[i] - jit[i - 1] for i in range(1, len(jit))]
    chk(len(set(deltas)) > 1, "jittered-deltas-constant")
    chk(S.max_sliding_window_count(jit, S.WINDOW_TICKS) <= 10, "jittered-over-cap")
    stag = S.schedule_arrivals(80, 10, seed=seed, jitter_frac=0.0).times_ticks
    sdeltas = [stag[i] - stag[i - 1] for i in range(1, len(stag))]
    chk(len(set(sdeltas)) == 1, "zero-jitter-deltas-not-constant")
    chk(S.max_sliding_window_count(stag, S.WINDOW_TICKS) <= 10, "zero-jitter-over-cap")
    burst = S.naive_burst(80, 10).times_ticks
    chk(len(set(burst)) == 1, "burst-not-identical")
    print("jitter both-states: jittered unique/non-constant within cap; zero-jitter constant within cap; burst identical timestamps (fires)")

    # --- Stats: re-derive the band from the receipt's raw list, not from a summary.
    nf = doc.get("noise_floor") or {}
    raw = nf.get("raw") or []
    chk(len(raw) == 1000, "raw-count", str(len(raw)))
    q1, q2, q3 = statistics.quantiles(raw, n=4, method="inclusive")
    med = statistics.median(raw)
    iqr = q3 - q1
    chk(close(q1, 4.0), "q1-mismatch", repr(q1))
    chk(close(med, 8.0), "median-mismatch", repr(med))
    chk(close(q3, 20.0), "q3-mismatch", repr(q3))
    chk(close(iqr, 16.0), "iqr-mismatch", repr(iqr))
    chk(close(float(min(raw)), 1.0), "min-mismatch", repr(min(raw)))
    chk(close(float(max(raw)), 100.0), "max-mismatch", repr(max(raw)))
    nf_ok = (close(float(nf.get("q1", 0)), q1) and close(float(nf.get("median", 0)), med)
             and close(float(nf.get("q3", 0)), q3) and close(float(nf.get("iqr", 0)), iqr))
    chk(nf_ok, "noise-floor-fields-mismatch")
    claims = doc.get("claims") or []
    chk(len(claims) >= 1, "claims-absent")
    meas = claims[0].get("measured") or {}
    chk(claims[0].get("verdict") == "REPRODUCED", "claim0-verdict", str(claims[0].get("verdict")))
    chk(meas.get("raw") == raw, "claim0-raw-not-identical-to-noise-floor")
    for key, val in (("q1", q1), ("median", med), ("q3", q3), ("iqr", iqr)):
        chk(close(float(meas.get(key, 0)), val), "claim0-" + key + "-mismatch", repr(meas.get(key)))
    rev = doc.get("reviewer") or {}
    vb = rev.get("variance_band") or {}
    chk(rev.get("verdict") == "PASS" and rev.get("independent") is True, "reviewer-closure-absent")
    chk(int(vb.get("n", -1)) == 1000 and close(float(vb.get("min", -1)), 1.0)
        and close(float(vb.get("max", -1)), 100.0) and close(float(vb.get("iqr", -1)), 16.0),
        "reviewer-band-mismatch", json.dumps(vb))
    print("stats re-derived from raw list: q1=%s median=%s q3=%s IQR=%s min=%s max=%s n=%d matches recorded band"
          % (q1, med, q3, iqr, min(raw), max(raw), len(raw)))

    # --- Distinctness from TST-0093 is stated in the receipt.
    chk("TST-0093" in str(doc.get("answer", "")) + str(doc.get("question", "")), "distinctness-absent")

    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe2 jitter both-states live (unique/non-constant vs constant vs identical-burst); IQR band re-derived from the 1000-value raw list (4/8/20, IQR 16, min 1, max 100) matches claim, noise floor and independent reviewer band; distinct from TST-0093")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
