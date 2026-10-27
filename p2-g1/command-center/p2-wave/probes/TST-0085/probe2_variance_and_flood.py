#!/usr/bin/env python3
"""TST-0085 probe2: live injection flood-control + independent variance.

Mechanically different from probe1 (receipt recount): this drives the
estate router inject module LIVE on this box at 10/100/500 installed
capabilities, asserts the top-k payload stays under the 500-token
ceiling, grows sublinearly per installed capability, is dominated by the
unbounded-flood control, and re-derives the receipt's variance band with
the stdlib statistics module (Bessel stdev + NormalDist CI) rather than
the probe1 formula."""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "router"))
import importlib

inject = importlib.import_module("inject")
UNIT = "TST-0085"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0085" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    runs = doc.get("raw_runs") or []
    toks = [int(r["injected_tokens"]) for r in runs]
    vb = doc.get("variance_band") or {}
    # independent recompute: statistics module path
    mu = st.fmean(toks)
    sd = st.stdev(toks)
    z = st.NormalDist().inv_cdf(0.975)
    se = sd / len(toks) ** 0.5
    chk(len(toks) == int(vb["n"]) and abs(mu - vb["mean"]) < 1e-9, "mean-match", str(mu))
    chk(abs(sd - vb["sample_std"]) < 1e-9, "std-match", str(sd))
    chk(abs(mu - z * se - vb["ci95_low"]) < 1e-6 and abs(mu + z * se - vb["ci95_high"]) < 1e-6, "ci-match")
    # live injection: 10/100/500 installed
    wl = ("git commit hook router suite fan lease guard parse receipt probe context token budget").split()
    live = {}
    for n in (10, 100, 500):
        caps = []
        for i in range(n):
            w = wl[i % len(wl)]
            caps.append({"id": "cap." + str(i), "name": "capability " + w,
                         "description": "capability procedure for " + w + " work " + str(i),
                         "triggers": [w, "cap" + str(i)]})
        r = inject.inject_topk("write a git commit message for the staged files", caps, k=4)
        live[n] = int(r.get("tokens") or 0)
        chk(live[n] <= 500, "live-under-ceiling:" + str(n), str(live[n]))
    per_cap = [live[10] / 10.0, live[100] / 100.0, live[500] / 500.0]
    chk(per_cap[0] >= per_cap[1] >= per_cap[2], "live-growth-sublinear", str(per_cap))
    flood_caps = []
    for i in range(500):
        flood_caps.append({"id": "cap.git." + str(i), "name": "git " + str(i),
                           "description": "git commit staged files procedure " + str(i),
                           "triggers": ["git", "commit"]})
    flood = inject.inject_unbounded_flood("write a git commit message", flood_caps)
    topk = inject.inject_topk("write a git commit message", flood_caps, k=4)
    ft, tt = int(flood.get("tokens") or 0), int(topk.get("tokens") or 0)
    chk(ft > tt, "flood-dominates-topk", str(ft) + " vs " + str(tt))
    chk(tt <= 500, "topk-clamped", str(tt))
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"live_topk_tokens": live, "live_tokens_per_installed": per_cap,
                      "flood_tokens": ft, "topk_same_corpus_tokens": tt,
                      "band_recompute": {"mean": mu, "std": sd, "ci95": [mu - z * se, mu + z * se]}}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 live router on this box: top-k stays under the 500 ceiling at 10/100/500 installed (" + json.dumps(live) + "), per-capability injection sublinear, unbounded flood (" + str(ft) + ") dominates clamped top-k (" + str(tt) + "); variance band independently re-derived via statistics.stdev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
