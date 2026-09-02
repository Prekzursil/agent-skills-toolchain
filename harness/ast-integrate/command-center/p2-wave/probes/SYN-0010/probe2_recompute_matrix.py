#!/usr/bin/env python3
"""Named probe 2: coefficient is recomputable from the published matrix alone.

Reviewer role: re-derive Fleiss' kappa from the raw per-item table with the
recorded seed; confirm the null model is the Fleiss marginal-chance model
for a fixed panel over a closed universe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import agreement as A  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0010.json"
TOL = 1e-9


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0010-probe2 {msg}")
    return 1


def close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= TOL


def check_arm(name: str, arm: dict) -> str | None:
    matrix = arm.get("matrix")
    if not isinstance(matrix, dict) or not matrix.get("items"):
        return f"{name} matrix missing"
    recomputed = A.kappa_from_matrix(matrix)
    published = arm.get("coefficient")
    if published is None:
        return f"{name} coefficient missing"
    if not close(recomputed["value"], published):
        return (
            f"{name} recompute {recomputed['value']} != published {published}"
        )
    # Seeded bootstrap from matrix rows must match published interval.
    rows = [list(item["ratings"]) for item in matrix["items"]]
    seed = int(arm.get("seed") or A.SEED if name == "random" else A.SEED)
    if name == "random":
        seed = int(arm.get("seed") or A.SEED) + 1
    interval = A.bootstrap_interval(rows, seed)
    rec_iv = arm.get("interval") or {}
    if rec_iv.get("low") is not None and not close(interval["low"], rec_iv["low"]):
        return f"{name} interval.low {interval['low']} != {rec_iv.get('low')}"
    if rec_iv.get("high") is not None and not close(interval["high"], rec_iv["high"]):
        return f"{name} interval.high {interval['high']} != {rec_iv.get('high')}"
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "SYN-0010":
        return fail(f"unit_id {doc.get('unit_id')}")
    if A.CATALOG_SENTINEL not in json.dumps(doc):
        return fail("catalog completion_sentinel absent")

    sc = doc.get("synthetic_controls") or {}
    for name in ("identical", "random"):
        err = check_arm(name, sc.get(name) or {})
        if err:
            return fail(err)

    # Null model must name Fleiss chance agreement for the sampling frame.
    null = str(doc.get("null_model") or "")
    if "Fleiss" not in null or "marginal" not in null.lower():
        return fail("null model does not name Fleiss marginal chance")
    if "population" not in null.lower() and "named panel" not in null.lower():
        # Must distinguish the sampling frame.
        if "complete item universe" not in null.lower() and "closed-universe" not in null.lower():
            return fail("null model missing sampling-frame clause")

    # Refused prose must not be the answer.
    answer = str(doc.get("answer") or "").lower()
    if A.REFUSED_PHRASE.lower() in answer and "refused" not in answer:
        return fail("answer uses refused prose")
    refused = doc.get("refused_prose") or {}
    if refused.get("status") != "REFUSED":
        return fail("refused_prose.status")

    # Live matrix, if COMPUTED, must also recompute.
    live = doc.get("live_panel") or {}
    if live.get("status") == "COMPUTED":
        err = check_arm("live", live)
        if err:
            return fail(err)
        if live.get("universe_size") in (None, 0):
            return fail("live COMPUTED without universe size")
    else:
        # Headline must be NOT-CHECKED; do not smuggle a live number.
        coeff = doc.get("coefficient") or {}
        if coeff.get("status") != "NOT-CHECKED":
            return fail("live absent but headline not NOT-CHECKED")
        if coeff.get("value") is not None:
            return fail("live absent but headline value set")

    payload = {
        "probe": "probe2-recompute-matrix",
        "identical_recomputed": True,
        "random_recomputed": True,
        "null_model_checked": True,
        "seed": doc.get("seed"),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:SYN-0010-probe2 coefficient recomputable from published matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
