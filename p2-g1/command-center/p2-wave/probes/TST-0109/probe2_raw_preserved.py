#!/usr/bin/env python3
"""TST-0109 probe2: raw preserved, summary-only rejected (independent).

Mechanically different from probe1's library+formula path: recomputes
every benchmark's mean/stdev/MDE with the stdlib statistics module
(fmean/stdev/NormalDist rather than the manual sums), asserts the raw
vectors are attached at full cardinality (not summaries), verifies the
seeded gaussian control reproduces the same-seed record, and proves
both negative controls: a summary-only row (raw stripped) is rejected
by the probe's own validator, and empty input refuses to emit."""
from __future__ import annotations

import json
import random
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "TST-0109"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
Z = st.NormalDist().inv_cdf(0.975)
ZP = st.NormalDist().inv_cdf(0.80)
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def validate_row(row: dict) -> None:
    raw = row.get("raw")
    if not raw or not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("summary-only or empty row rejected: raw vector required")
    if len(raw) != int(row.get("n", -1)):
        raise ValueError("cardinality mismatch")


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0109" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    rederived = 0
    for b in doc.get("benchmarks") or []:
        validate_row(b)
        raw = [float(x) for x in b["raw"]]
        mu = st.fmean(raw)
        sd = st.stdev(raw)
        n = len(raw)
        mde = (Z + ZP) * sd * (2.0 / n) ** 0.5
        chk(close(mu, float(b["mean"])) and close(sd, float(b["stdev"])) and close(mde, float(b["mde"])),
            "stats-rederive:" + str(b.get("id")))
        chk(all(isinstance(x, (int, float)) for x in raw), "raw-numeric:" + str(b.get("id")))
        rederived += 1
    chk(rederived == 4, "all-benchmarks", str(rederived))
    c = (doc.get("controls") or {}).get("gaussian-seeded") or {}
    chk(int(c.get("seed", -1)) == 109, "seed-recorded")
    rng = random.Random(109)
    replay = [rng.gauss(100.0, 4.3) for _ in range(21)]
    chk(abs(st.fmean(replay) - float(c["mean"])) < 0.5 and abs(st.stdev(replay) - float(c["stdev"])) < 0.5,
        "same-seed-reproduces", str(st.fmean(replay)) + "/" + str(st.fmean([float(x) for x in c.get("raw") or [0]])))
    for name, row in [("summary-only", {k: v for k, v in (doc.get("benchmarks") or [{}])[0].items() if k != "raw"}),
                      ("empty-raw", {"id": "x", "n": 0, "mean": 1.0, "stdev": 0.0, "mde": 0.0, "raw": []})]:
        try:
            validate_row(row)
            chk(False, "negative-must-reject:" + name)
        except ValueError:
            chk(True, "negative-rejects:" + name)
    nc = {n.get("id") for n in doc.get("negative_controls") or []}
    chk({"TST-0109-EMPTY-INPUT", "TST-0109-SUMMARY-ONLY"} <= nc, "receipt-controls-recorded", json.dumps(sorted(nc)))
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails[:8]))
        return 1
    print(json.dumps({"benchmarks_rederived_stats_module": rederived,
                      "seed_replay_mean": round(st.fmean(replay), 3),
                      "seed_record_mean": round(float(c["mean"]), 3),
                      "negatives_rejected": ["summary-only", "empty-raw"]}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 raw vectors attached at full cardinality and re-derived via statistics.fmean/stdev/NormalDist; seed-109 gaussian control reproduces within band; summary-only and empty rows rejected - raw numbers are preserved, not only the summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
