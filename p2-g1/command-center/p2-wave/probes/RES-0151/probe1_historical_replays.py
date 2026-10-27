#!/usr/bin/env python3
"""RES-0151 probe1_historical_replays.

Re-derives the evidence-saturation fire decision for the five replayed
historical research runs from the artifact's own embedded data, using an
inline implementation of the catalog metric (rolling mean of new distinct
mechanism keys). Live-verifies the five replayed files' sha256 where the
files are still on disk. Defaults to FAIL.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def score_run(yields, window, floor, min_sources):
    """Fire rule from artifact metric.fire_rule: smallest t >= min_sources with
    mean(y[t-window+1..t]) <= floor. None when silent. 1-based index."""
    n = len(yields)
    for t in range(min_sources, n + 1):
        seg = yields[t - window : t]
        if seg and (sum(seg) / len(seg)) <= floor:
            return t
    return None


def main() -> int:
    art = REPO / "command-center/research/evidence-quality/RES-0151-evidence-saturation-stopping-metric.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:300]})
        return bool(ok)

    metric = doc.get("metric") or {}
    window = int(metric.get("window") or 3)
    floor = float(metric.get("floor") if metric.get("floor") is not None else 0.34)
    min_sources = int(metric.get("min_sources") or 5)
    ck("metric-fire-rule-declared", bool(metric.get("fire_rule")), metric.get("fire_rule", "")[:120])

    replays = doc.get("historical_replays") or []
    ck("five-real-replays", len(replays) == 5, f"n={len(replays)}")
    ck("replays-real-class", all(r.get("corpus_class") == "real-prior-document" for r in replays),
       str({r.get("corpus_class") for r in replays}))

    live_hash_ok, live_hashed = 0, 0
    recompute_ok, recompute_n = 0, 0
    for r in replays:
        rid = r.get("run_id")
        p = REPO / str(r.get("path", "")).replace("\\", "/")
        if p.is_file():
            live_hashed += 1
            live = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if live == r.get("file_sha256"):
                live_hash_ok += 1
        y = r.get("yields")
        if isinstance(y, list) and y:
            recompute_n += 1
            exp_fire = score_run([int(v) for v in y], window, floor, min_sources)
            rec_fired = r.get("fired")
            rec_idx = r.get("fire_index")
            ok = ((exp_fire is None and rec_fired is False and rec_idx is None)
                  or (exp_fire is not None and rec_fired is True and rec_idx == exp_fire))
            if ok:
                recompute_ok += 1

    ck("replayed-files-live-hashes-match", live_hash_ok == 5 and live_hashed == 5,
       f"hashed={live_hashed} matched={live_hash_ok}")
    ck("fire-index-recompute-matches-recorded", recompute_n == 5 and recompute_ok == 5,
       f"recomputed={recompute_ok}/{recompute_n}")

    obs = {o.get("name"): o.get("measured") for o in (doc.get("report") or {}).get("observations") or []}
    ck("historical-observation-none-for-all-five",
       obs.get("historical-fire-indexes") == "P2-GROUNDING=None,P2-BUILD-ROUND1=None,P2-BUILD-ROUND2=None,P2-BUILD-ROUND3=None,P2-INTEGRATE=None",
       str(obs.get("historical-fire-indexes"))[:80])
    ck("state-success-and-sentinel",
       str(doc.get("state")) == "SUCCESS" and "SUCCESS:RES-0151" in str(doc.get("completion_sentinel")),
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-historical-replays", "unit_id": "RES-0151", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0151-probe1 five real replays re-scored live" if not red
          else f"FAILED:RES-0151-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
