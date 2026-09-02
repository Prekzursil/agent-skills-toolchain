#!/usr/bin/env python3
"""Probe 2: sensitivity sweep + independent recompute from raw transcripts.

Mechanically different from probe 1: serialise per-cast participant fields to
disk, reload, and recompute D without using probe 1's summary object. The
floor must sit in a gap on a five-point increasing-similarity curve, not on a
single pair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from divergence import floor_value, score_from_raw, score_transcript  # noqa: E402
from simulate import run_sweep  # noqa: E402

UNIT = "TST-0259"
RAW = HERE / "probe2-raw-casts.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    floor = floor_value()
    transcripts = run_sweep()
    if len(transcripts) < 5:
        return fail("sweep shorter than 5 casts", {"n": len(transcripts)})

    similarities = [float(t["similarity"]) for t in transcripts]
    if similarities != sorted(similarities):
        return fail("sweep is not increasing similarity", similarities)

    live_rows = []
    for t in transcripts:
        sc = score_transcript(t)
        live_rows.append(
            {
                "cast_id": t["cast_id"],
                "similarity": t["similarity"],
                "D": sc["D"],
                "panel": sc["panel"],
                "components": {
                    "claim": sc["claim_jaccard_distance"],
                    "evidence": sc["evidence_jaccard_distance"],
                    "vote": sc["vote_dispersion"],
                    "lexical": sc["lexical_jaccard_distance"],
                },
            }
        )

    raw_payload = {
        "floor": floor,
        "casts": [
            {
                "cast_id": t["cast_id"],
                "similarity": t["similarity"],
                "participants": t["participants"],
            }
            for t in transcripts
        ],
    }
    RAW.write_text(json.dumps(raw_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reloaded = json.loads(RAW.read_text(encoding="utf-8"))
    recomputed = []
    for row in reloaded["casts"]:
        sc = score_from_raw(row["participants"])
        recomputed.append(
            {
                "cast_id": row["cast_id"],
                "similarity": row["similarity"],
                "D": sc["D"],
                "panel": sc["panel"],
            }
        )

    for a, b in zip(live_rows, recomputed):
        if abs(a["D"] - b["D"]) > 1e-12:
            return fail("independent recompute D mismatch", {"live": a, "recomputed": b})
        if a["panel"] != b["panel"]:
            return fail("independent recompute panel mismatch", {"live": a, "recomputed": b})

    ds = [r["D"] for r in live_rows]
    for i in range(1, len(ds)):
        if ds[i] - ds[i - 1] > 1e-9:
            return fail(
                "D rose as similarity increased; sweep is not a floor-supporting curve",
                live_rows,
            )

    if live_rows[0]["panel"] != "PASS":
        return fail("least-similar sweep point did not PASS", live_rows[0])
    if live_rows[-1]["panel"] != "FAIL":
        return fail("most-similar sweep point did not FAIL", live_rows[-1])

    crossings = []
    for i in range(1, len(live_rows)):
        left, right = live_rows[i - 1], live_rows[i]
        if left["D"] >= floor > right["D"]:
            crossings.append(
                {
                    "between": [left["cast_id"], right["cast_id"]],
                    "D_left": left["D"],
                    "D_right": right["D"],
                }
            )
    if not crossings:
        return fail("floor does not sit in a sweep gap (single-point guess risk)", live_rows)

    effect = live_rows[0]["D"] - live_rows[-1]["D"]
    summary = {
        "floor": floor,
        "n_casts": len(live_rows),
        "similarities": similarities,
        "D_values": ds,
        "panels": [r["panel"] for r in live_rows],
        "floor_gap": crossings,
        "effect_size_D_low_sim_minus_high_sim": effect,
        "independent_recompute_matched": True,
        "raw_path": "command-center/p2-wave/probes/TST-0259/probe2-raw-casts.json",
        "rows": live_rows,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        "sweep_D="
        + ",".join(f"{x:.6f}" for x in ds)
        + f" floor={floor:.6f} effect={effect:.6f}"
    )
    print(f"SUCCESS:{UNIT}-probe2 sensitivity-sweep independent-recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
