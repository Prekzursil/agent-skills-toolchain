#!/usr/bin/env python3
"""Named probe 1: independent n recompute + sensitivity table must move.

Hand-check uses ln/ceil and a local binomial SF, not calculator.n_min.
Halving p must increase n_any; a table that does not move fails.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import calculator as C  # noqa: E402
import inputs as I  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0138.json"


def local_n_any(p_obs: float, beta: float) -> int:
    n = int(math.ceil(math.log(beta) / math.log(1.0 - p_obs)))
    n = max(n, 1)
    while (1.0 - p_obs) ** n > beta:
        n += 1
    while n > 1 and (1.0 - p_obs) ** (n - 1) <= beta:
        n -= 1
    return n


def local_sf(k: int, n: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    total = 0.0
    for i in range(k, n + 1):
        logc = math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
        total += math.exp(logc + i * math.log(p) + (n - i) * math.log(1.0 - p))
    return total


def local_n_min(p_obs: float, tau: float, beta: float, nmax: int = 600) -> int:
    target = 1.0 - beta
    for n in range(1, nmax + 1):
        kcrit = math.floor(n * tau) + 1
        if local_sf(kcrit, n, p_obs) >= target:
            return n
    raise AssertionError("local n_min did not converge")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0138-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if doc.get("unit_id") != "CNF-0138" or "SUCCESS:CNF-0138" not in blob:
        print("FAILED:CNF-0138-probe1 sentinel/unit")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0138-probe1 self-declared", doc.get("state"))
        return 1

    inp = doc["inputs"]
    p, beta, phi, tau = inp["p"], inp["beta"], inp["phi"], inp["tau"]
    p_obs = p * (1.0 - phi)
    tool = doc["worked_example"]["tool"]
    hand_any = local_n_any(p_obs, beta)
    hand_min = local_n_min(p_obs, tau, beta)
    if hand_any != tool["n_any"]:
        print(f"FAILED:CNF-0138-probe1 n_any hand={hand_any} tool={tool['n_any']}")
        return 1
    if hand_min != tool["n_min"]:
        print(f"FAILED:CNF-0138-probe1 n_min hand={hand_min} tool={tool['n_min']}")
        return 1
    if abs(hand_any - C.n_any(p_obs, beta)) != 0:
        print("FAILED:CNF-0138-probe1 n_any local vs calculator")
        return 1

    # One stratum: independent n vs receipt row (to the unit).
    example_id = doc["worked_example"]["stratum_id"]
    row = next(r for r in doc["per_stratum"] if r["id"] == example_id)
    n_required = tool["n_stable"]
    recomputed = n_required if not row["census"] else row["population"]
    if not row["census"]:
        recomputed = min(n_required, row["population"])
    if recomputed != row["n"]:
        print(
            f"FAILED:CNF-0138-probe1 stratum {example_id} n={row['n']} "
            f"recomputed={recomputed}"
        )
        return 1

    table = doc["sensitivity_table"]
    n_vals = [r["n_any"] for r in table]
    if len(set(n_vals)) < 2:
        print("FAILED:CNF-0138-probe1 sensitivity table did not move", n_vals)
        return 1
    by = {(r["p"], r["beta"]): r["n_any"] for r in table}
    n20 = by[(0.20, 0.10)]
    n10 = by[(0.10, 0.10)]
    n05 = by[(0.05, 0.10)]
    if not (n05 > n10 > n20):
        print(f"FAILED:CNF-0138-probe1 halving p did not increase n_any {n20},{n10},{n05}")
        return 1
    # Independent check of the same three cells.
    phi_t = table[0]["phi"]
    for p_cell, want in ((0.20, n20), (0.10, n10), (0.05, n05)):
        got = local_n_any(p_cell * (1.0 - phi_t), 0.10)
        if got != want:
            print(f"FAILED:CNF-0138-probe1 table cell p={p_cell} got={got} want={want}")
            return 1

    # n_stable at p=0.20 must be < n_stable at p=0.10 (both > tau after attenuation)
    nstab = {
        (r["p"], r["beta"]): r.get("n_stable")
        for r in table
        if r.get("n_stable") is not None
    }
    if nstab.get((0.10, 0.10)) is None or nstab.get((0.20, 0.10)) is None:
        print("FAILED:CNF-0138-probe1 missing n_stable sensitivity cells")
        return 1
    if not (nstab[(0.10, 0.10)] > nstab[(0.20, 0.10)]):
        print("FAILED:CNF-0138-probe1 n_stable did not increase when p halved 0.20->0.10")
        return 1

    frame, _src = I.load_frame()
    print(
        json.dumps(
            {
                "stratum_id": example_id,
                "hand_n_any": hand_any,
                "hand_n_min": hand_min,
                "tool_n_any": tool["n_any"],
                "tool_n_min": tool["n_min"],
                "tool_n_stable": tool["n_stable"],
                "stratum_n": row["n"],
                "sensitivity_n_any": {"p0.20": n20, "p0.10": n10, "p0.05": n05},
                "frame_strata": len(I.extract_strata(frame)),
                "match": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0138-probe1 hand-check and sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
