#!/usr/bin/env python3
"""Probe 2: re-draw the sampling frame; recompute Brier from the published table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import bands as B  # noqa: E402
import harvest as H  # noqa: E402
import schemautil as SU  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0069-band-calibration.json"
TOL = 1e-12


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0069-probe2 {msg}")
    return 1


def brier_independent(rows: list[dict]) -> tuple[float | None, int]:
    """Third copy of the arithmetic — does not import scorer."""
    acc = 0.0
    n = 0
    for it in rows:
        outcome = str(it.get("outcome") or "").upper()
        if outcome not in {"CONFIRMED", "REFUTED"}:
            continue
        if str(it.get("settlement_kind") or "") == "contemporaneous-measurement":
            continue
        y = 1.0 if outcome == "CONFIRMED" else 0.0
        p = float(it["p"]) if "p" in it else float(B.MAPPING[it["band"]]["p"])
        acc += (p - y) ** 2
        n += 1
    if n == 0:
        return None, 0
    return acc / n, n


def hit_rate_independent(rows: list[dict], band: str) -> tuple[int, int]:
    hits = 0
    n = 0
    for it in rows:
        if it.get("band") != band:
            continue
        if str(it.get("settlement_kind") or "") == "contemporaneous-measurement":
            continue
        outcome = str(it.get("outcome") or "").upper()
        if outcome not in {"CONFIRMED", "REFUTED"}:
            continue
        n += 1
        if outcome == "CONFIRMED":
            hits += 1
    return hits, n


def main() -> int:
    if not OUT.is_file():
        return fail("artifact absent")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    body = SU.payload(doc)
    live = H.harvest()
    rec_seed = (body.get("sampling") or {}).get("seed")
    if rec_seed != live["seed"]:
        return fail(f"seed mismatch recorded={rec_seed} live={live['seed']}")
    rec_frame = list((body.get("sampling") or {}).get("frame") or [])
    if rec_frame != live["sampling_frame"]:
        return fail(
            f"sampling-frame redraw mismatch rec={len(rec_frame)} live={len(live['sampling_frame'])}"
        )
    rec_ids = list((body.get("sampling") or {}).get("sampled_ids") or [])
    if rec_ids != live["sampled_ids"]:
        return fail("sampled_ids redraw mismatch")
    print(
        f"redraw seed={live['seed']} frame={len(rec_frame)} identical=True"
    )

    published = list(body.get("claims") or [])
    recomputed, n = brier_independent(published)
    recorded = (body.get("brier") or {}).get("score")
    rec_n = (body.get("brier") or {}).get("n")
    if rec_n != n:
        return fail(f"brier n mismatch recorded={rec_n} recomputed={n}")
    if n == 0:
        if recorded is not None:
            return fail("recorded Brier on empty settled set")
        print("brier n=0 both-null (no later-settled claims to score)")
    else:
        if recorded is None or abs(float(recorded) - float(recomputed)) > TOL:
            return fail(f"brier mismatch recorded={recorded} recomputed={recomputed}")
        print(f"brier recorded={recorded} recomputed={recomputed} n={n} match=True")

    for band_row in body.get("bands") or []:
        band = band_row["band"]
        hits, n_b = hit_rate_independent(published, band)
        if n_b != band_row.get("n_settled"):
            return fail(
                f"{band} n_settled mismatch table={band_row.get('n_settled')} recomputed={n_b}"
            )
        if hits != band_row.get("hits"):
            return fail(f"{band} hits mismatch table={band_row.get('hits')} recomputed={hits}")
        if n_b < 5:
            if band_row.get("status") not in {"insufficient-data", "no-settled"}:
                return fail(f"{band} n={n_b} should not be scored: {band_row.get('status')}")
        print(
            f"band {band} n={n_b} hits={hits} status={band_row.get('status')} "
            f"p={band_row.get('p')}"
        )

    ctrl = body.get("control") or {}
    # Recompute control expected from the mapping and the published hits rule.
    n_per = int(ctrl.get("n_per_band") or 20)
    acc = 0.0
    n_c = 0
    for band, spec in B.MAPPING.items():
        p = float(spec["p"])
        hits = int(round(n_per * p))
        acc += hits * (p - 1.0) ** 2 + (n_per - hits) * (p - 0.0) ** 2
        n_c += n_per
    expect = acc / n_c
    if abs(float(ctrl["expected_brier"]) - expect) > TOL:
        return fail(
            f"control expected arithmetic mismatch {ctrl['expected_brier']} vs {expect}"
        )
    print(f"control expected recomputed={expect} match=True")
    print("SUCCESS:CNF-0069-probe2 sample-redraw interval-arithmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
