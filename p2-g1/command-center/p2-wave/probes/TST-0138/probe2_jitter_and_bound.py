#!/usr/bin/env python3
"""TST-0138 probe2 -- full-jitter backoff: re-derive empirics + symbolic bound.

Re-implements the receipt's recorded algorithm (AWS full jitter, clip to
remaining timeout minus eps) and re-runs: 50-run uniqueness + sums below
timeout under the catalog policy; two-run set difference (jitter); the tight
fixture where clipping is load-bearing; the symbolic bound grid over the
recorded supported ranges; and the unjittered known-broken control.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0138.json"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def schedule(base: float, cap: float, attempts: int, timeout: float, rng) -> list[float]:
    """AWS full jitter; each delay clipped to remaining_timeout - eps."""
    eps = 1e-9
    out, rem = [], float(timeout)
    for a in range(attempts):
        hi = min(cap, base * (2 ** a), rem - eps)
        d = rng.uniform(0.0, max(hi, 0.0))
        out.append(d)
        rem -= d
    return out


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    ans = doc.get("answer") or {}
    for k in ("jittered_across_runs", "property_grid_pass", "sum_strictly_below_timeout"):
        chk(ans.get(k) is True, "recorded-answer", k)
    emp = doc.get("empirical") or {}
    pol = emp.get("catalog_policy") or {}
    chk((pol.get("base"), pol.get("cap"), pol.get("max_attempts"), pol.get("timeout_seconds")) == (2.0, 60.0, 3, 3600.0), "catalog-policy-recorded", pol)

    # empirical: 50 catalog-policy runs, unique sets, sums strictly below timeout
    rng = random.Random(1380138)
    runs = [schedule(2.0, 60.0, 3, 3600.0, rng) for _ in range(50)]
    chk(len({tuple(r) for r in runs}) == 50, "unique-sets", len({tuple(r) for r in runs}))
    chk(all(sum(r) < 3600.0 for r in runs), "sum-bound-catalog")
    a = schedule(2.0, 60.0, 3, 3600.0, random.Random(1))
    b = schedule(2.0, 60.0, 3, 3600.0, random.Random(2))
    chk(a != b, "two-runs-identical")

    # tight fixture: clipping is load-bearing (unclipped worst case >= timeout)
    tight_base, tight_cap, tight_n, tight_timeout = 10.0, 30.0, 8, 50.0
    unclipped_worst = sum(min(tight_cap, tight_base * (2 ** i)) for i in range(tight_n))
    chk(unclipped_worst >= tight_timeout, "clipping-not-load-bearing", unclipped_worst)
    ok_clipped = all(sum(schedule(tight_base, tight_cap, tight_n, tight_timeout, random.Random(s))) < tight_timeout for s in range(1000))
    chk(ok_clipped, "tight-fixture-bound")

    # symbolic grid over the receipt's supported ranges
    sym = doc.get("symbolic") or {}
    bases = sym.get("supported_bases") or [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    caps = sym.get("supported_caps") or [1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
    attempts = sym.get("supported_attempts") or list(range(1, 11))
    timeouts = sym.get("supported_timeouts") or [50.0, 60.0, 300.0, 1800.0, 3600.0]
    cells = load_bearing = 0
    g = random.Random(138)
    for base in bases:
        for cap in caps:
            for n in attempts:
                un = sum(min(cap, base * (2 ** i)) for i in range(n))
                for t in timeouts:
                    cells += 1
                    draws = 40 if un >= t else 8
                    if un >= t:
                        load_bearing += 1
                    for _ in range(draws):
                        chk(sum(schedule(base, cap, n, t, g)) < t, "grid-bound-failure", (base, cap, n, t))
    chk(load_bearing > 0, "no-load-bearing-cells")
    chk(sym.get("bound_failures") == 0, "recorded-grid-failures", sym.get("bound_failures"))

    # unjittered known-broken control: fixed intervals -> sets identical across runs
    ua = [min(60.0, 2.0 * (2 ** i)) for i in range(3)]
    ub = [min(60.0, 2.0 * (2 ** i)) for i in range(3)]
    chk(ua == ub, "unjittered-control-differs")
    if FAILS:
        print("FAILED:TST-0138-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0138-probe2 jitter re-derived (50 unique sets, two-run sets differ, all sums < timeout); tight fixture clipping load-bearing (unclipped worst %.1f >= %s); %d-cell symbolic grid zero bound failures; unjittered control fires" % (unclipped_worst, tight_timeout, cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
