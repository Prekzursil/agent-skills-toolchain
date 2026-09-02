#!/usr/bin/env python3
"""Named probe 2: merger reject-on-overlap, id-capacity, extra mutant shapes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import model as M  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0060.json"
EPS = 1e-9


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0060-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0060" not in json.dumps(doc):
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"state {doc.get('state')}")

    live = M.live_work_units()
    scheme = M.measure_id_scheme(live)
    rec_cap = doc.get("id_capacity") or {}
    if scheme["observed_zero_padding_width"] != 4:
        return fail(f"width {scheme['observed_zero_padding_width']}")
    if not scheme["accommodates_20480_without_format_change"]:
        return fail("capacity does not accommodate 20480 under multi-prefix")
    if scheme["single_prefix_accommodates_20480"]:
        return fail("single 4-digit prefix must NOT hold 20480")
    if scheme["allocated_capacity"] != rec_cap.get("allocated_capacity"):
        return fail("allocated_capacity mismatch")
    if not scheme["tenx_each_prefix_fits_without_format_change"]:
        return fail("a prefix would overflow 4 digits at 10x")

    merger = M.run_merger_controls(live)
    if not merger["overlap_rejected"]:
        return fail("overlapping slices were not REJECTED")
    if not merger["disjoint_accepted"]:
        return fail("disjoint slices were not accepted")
    if not merger["order_independent"]:
        return fail("merge is order-dependent")
    if not merger["silent_dedup_is_not_the_merger"]:
        return fail("merger matches silent-dedup anti-pattern")
    if not merger["live_merge_matches_catalog"]:
        return fail("live slice merge does not recover catalog ids")
    silent = M.merge_silently_dedup(
        [
            ("slice-a.json", live[:3]),
            ("slice-b-overlap.json", [live[0], live[4]]),
        ]
    )
    if len(silent) != 4:
        return fail("silent-dedup control did not hide the overlap")

    extra = M.extra_mutant_shapes(live, M.THRESHOLD)
    rec_extra = (doc.get("reviewer") or {}).get("additional_mutant_shapes") or []
    if len(extra) < 2 or len(rec_extra) < 2:
        return fail("reviewer additional mutant shapes missing")
    for row, rec in zip(extra, rec_extra):
        if row["shape"] != rec["shape"]:
            return fail(f"shape {row['shape']}!={rec['shape']}")
        if abs(row["firing_rate"] - rec["firing_rate"]) > EPS:
            return fail(f"{row['shape']} firing mismatch")
        if row["firing_rate"] != 1.0:
            return fail(f"{row['shape']} firing_rate {row['firing_rate']}")

    by_n = {int(s["n"]): s for s in doc.get("scale_points") or []}
    s100 = M.measure_scale(live, 100, M.THRESHOLD)
    if abs(s100["clean_max_jaccard"] - by_n[100]["clean_max_jaccard"]) > EPS:
        return fail("n=100 clean max mismatch")
    if not s100["clean_max_below_threshold"]:
        return fail("n=100 clean max not below threshold")

    pair = by_n[20480].get("clean_max_pair") or []
    if len(pair) != 3:
        return fail("n=20480 max pair not reported")
    # Re-score the reported pair from the synthetic generator (not from memory).
    left_id, right_id, reported = pair[0], pair[1], float(pair[2])
    if not str(left_id).startswith("q") or not str(right_id).startswith("q"):
        return fail(f"expected synth max pair, got {pair}")
    i = int(str(left_id)[1:])
    j = int(str(right_id)[1:])
    got = M.jaccard(M.unit_tokens(M.make_synth(i)), M.unit_tokens(M.make_synth(j)))
    if abs(got - reported) > EPS:
        return fail(f"reported pair {got}!={reported}")
    if got >= M.THRESHOLD:
        return fail(f"reported max {got} not below threshold")

    print(
        f"width=4 prefixes={scheme['n_prefixes']} allocated={scheme['allocated_capacity']} "
        f"accommodates_20480={scheme['accommodates_20480_without_format_change']} "
        f"single_prefix_fits={scheme['single_prefix_accommodates_20480']}"
    )
    print(
        f"overlap_rejected={merger['overlap_rejected']} "
        f"collision={merger['collision']} "
        f"silent_dedup_would_accept={merger['silent_dedup_would_accept']}"
    )
    print(
        "extra_mutants "
        + " ".join(f"{r['shape']}={r['firing_rate']}" for r in extra)
    )
    print(
        f"n100_clean_max={s100['clean_max_jaccard']:.6f} "
        f"n20480_reported_pair={got:.6f}"
    )
    print("SUCCESS:BLD-0060-probe2 merge-capacity and reviewer mutant shapes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
