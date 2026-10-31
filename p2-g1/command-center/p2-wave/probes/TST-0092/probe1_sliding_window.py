#!/usr/bin/env python3
"""TST-0092 probe1: sliding-window cap property (live, fail-closed).

Rebuild 2026-10-26 (shard19-w3 resume): the prior builder died mid-flight
before this probe dir landed; the receipt's recorded probe shas refer to
files that no longer exist. This probe re-derives the property LIVE on the
current tools/arrival_scheduler scheduler (superseded in place by a later
wave; the property, not the byte-identity, is the claim):

  * 1000 generated schedules from the recorded seed 920092: no half-open
    sliding window count ever exceeds the declared rate cap;
  * 1000-unit dispatches at caps 5,10,20,40,50: max window printed per cap;
  * the receipt's recorded campaign map saturates at cap (never exceeds);
  * burst twin control FIRES: identical timestamps exceed the cap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "TST-0092"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
RECORDED_SEED = 920092
CAPS = [5, 10, 20, 40, 50]
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        sys.path.insert(0, str(REPO))
        from tools.arrival_scheduler.scheduler import (
            WINDOW_TICKS,
            max_sliding_window_count,
            naive_burst,
            schedule_arrivals,
        )
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 scheduler-import:" + type(exc).__name__)
        return 1
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 128, "under-min-bytes", str(OUT.stat().st_size))
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:" + UNIT in text, "sentinel-absent")

    # Live property campaign: 1000 generated schedules from the recorded seed.
    n_schedules = 1000
    n_units_cycle = [80, 160, 320, 640, 1000]
    worst_by_cap: dict[int, int] = {}
    violations = 0
    for i in range(n_schedules):
        cap = CAPS[i % len(CAPS)]
        n = n_units_cycle[i % len(n_units_cycle)]
        jf = 0.4 if i % 2 else 0.0
        sched = schedule_arrivals(n, cap, seed=RECORDED_SEED + i, jitter_frac=jf)
        mx = max_sliding_window_count(sched.times_ticks, WINDOW_TICKS)
        worst_by_cap[cap] = max(worst_by_cap.get(cap, 0), mx)
        if mx > cap:
            violations += 1
    chk(violations == 0, "campaign-window-violations", str(violations))
    print("campaign: 1000 schedules from seed %d, violations=%d, worst per cap=%s"
          % (RECORDED_SEED, violations, json.dumps({str(k): v for k, v in sorted(worst_by_cap.items())})))

    # Live 1000-unit dispatches at the receipt's caps; print max window per cap.
    live_max: dict[int, int] = {}
    for cap in CAPS:
        sched = schedule_arrivals(1000, cap, seed=RECORDED_SEED + cap, jitter_frac=0.4)
        live_max[cap] = max_sliding_window_count(sched.times_ticks, WINDOW_TICKS)
    chk(all(v <= c for c, v in live_max.items()), "large-dispatch-over-cap",
          json.dumps({str(k): v for k, v in live_max.items()}))
    print("large dispatch (n=1000, jittered) max window per cap: %s"
          % json.dumps({str(k): v for k, v in sorted(live_max.items())}))

    # Recorded maps: campaign saturates at cap; recorded max never exceeds cap.
    camp = doc.get("campaign_per_cap_max_window") or {}
    chk(len(camp) >= 13, "campaign-map-shape", str(len(camp)))
    for cap_s, mx in camp.items():
        cap = int(cap_s)
        chk(int(mx) <= cap, "recorded-campaign-over-cap", "%s>%s" % (mx, cap))
    rec = doc.get("max_observed_window_rate_per_cap") or {}
    chk(set(rec.keys()) == {str(c) for c in CAPS}, "recorded-per-cap-keys", json.dumps(rec))
    for cap_s, mx in rec.items():
        chk(int(mx) <= int(cap_s), "recorded-per-cap-over-cap", "%s>%s" % (mx, cap_s))
    print("recorded campaign map caps=%d all within cap; recorded per-cap max %s within caps"
          % (len(camp), json.dumps(rec)))

    # Burst twin negative control must FIRE (identical timestamps exceed cap).
    burst = naive_burst(80, 10)
    burst_mx = max_sliding_window_count(burst.times_ticks, WINDOW_TICKS)
    chk(burst_mx > 10, "burst-control-silent", str(burst_mx))
    chk(len(set(burst.times_ticks)) == 1, "burst-timestamps-unique")
    jittered = schedule_arrivals(80, 10, seed=RECORDED_SEED + 7, jitter_frac=0.4)
    chk(len(set(jittered.times_ticks)) == len(jittered.times_ticks), "jittered-timestamps-not-unique")
    print("burst twin: max_window=%d>cap=10 (control fires); jittered twin timestamps unique" % burst_mx)

    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 live scheduler property: 1000 schedules from recorded seed 920092 never exceed cap in any half-open sliding window; n=1000 dispatches at caps 5,10,20,40,50 within cap; recorded maps within cap; burst twin fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
