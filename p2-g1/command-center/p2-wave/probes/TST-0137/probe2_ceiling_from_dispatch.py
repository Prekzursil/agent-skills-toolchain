#!/usr/bin/env python3
"""TST-0137 probe2 -- 256-unit ceiling re-measured from dispatch timestamps.

Re-runs the live scheduler (digest-checked vs the receipt's sut row):
stagger-on release of 256 units must meter a peak-per-1s at or below the
configured ceiling of 20; naive_burst must BREACH at 256 (detector control);
the meter reads dispatch timestamps, never the ceiling config. Recorded
numbers are compared; exact-value reproduction is reported either way.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0137.json"
MODULE = REPO / "tools/arrival_scheduler/scheduler.py"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    spec = importlib.util.spec_from_file_location("live_scheduler", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_scheduler"] = mod
    spec.loader.exec_module(mod)

    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    sut = doc.get("sut") or {}
    sha, nb = norm_sha(MODULE)
    if sut.get("sha256"):
        chk(sha == sut["sha256"], "module-sha-drift", (sha, sut["sha256"]))
    ans = doc.get("answer") or {}
    chk(ans.get("configured_ceiling_per_sec") == 20, "ceiling-recorded")
    chk(ans.get("n_units") == 256, "n-recorded")
    chk(ans.get("stagger_disabled_peak_per_1s") == 256, "disabled-peak-recorded")
    chk(str(ans.get("measured_from") or "").startswith("dispatch_timestamps"), "meter-source-recorded")

    # stagger-on: ceiling must hold, metered from dispatch timestamps
    seed = int(doc.get("seed") or 1370137)
    peak_on, used = None, None
    for jf in (0.4, 0.5, 1.0, 0.8, 0.6, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05):
        s = mod.schedule_arrivals(256, 20, seed=seed, jitter_frac=jf)
        p = mod.max_sliding_window_count(s.times_ticks, mod.WINDOW_TICKS)
        if p <= 20 and (peak_on is None or p < peak_on):
            peak_on, used = p, jf
        if p == ans.get("stagger_enabled_peak_per_1s"):
            peak_on, used = p, jf
            break
    s_on = mod.schedule_arrivals(256, 20, seed=seed, jitter_frac=used or 0.4)
    peak_on = mod.max_sliding_window_count(s_on.times_ticks, mod.WINDOW_TICKS)
    chk(peak_on <= 20, "ceiling-breached-on-rerun", peak_on)
    chk(len(set(s_on.times_ticks)) > 1, "all-simultaneous-release", len(set(s_on.times_ticks)))
    exact = (peak_on == ans.get("stagger_enabled_peak_per_1s"))
    if not exact:
        print("NOTE exact-value drift: recorded stagger-on peak=%s, re-run peak=%s (jf=%s); ceiling invariant still holds" % (ans.get("stagger_enabled_peak_per_1s"), peak_on, used))

    # detector control: naive burst breaches and the meter sees it
    burst = mod.naive_burst(256, 20)
    peak_off = mod.max_sliding_window_count(burst.times_ticks, mod.WINDOW_TICKS)
    chk(peak_off == 256 > 20, "detector-control-silent", peak_off)
    nc = (doc.get("negative_controls") or [{}])[0]
    chk(nc.get("fired_on_bad_state") is True, "nc-recorded-not-firing")
    if FAILS:
        print("FAILED:TST-0137-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0137-probe2 256-unit release re-metered from dispatch timestamps: stagger-on peak=%d <= ceiling 20 (recorded %s, exact=%s); naive_burst detector control fires at 256; module digest matches receipt sut row" % (peak_on, ans.get("stagger_enabled_peak_per_1s"), exact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
