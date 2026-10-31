#!/usr/bin/env python3
"""TST-0109 probe1: per-benchmark MDE re-derivation (fail-closed).

Re-derives every benchmark's n/mean/stdev/CI95/MDE/n_min from the
receipt's attached raw per-run vectors using the estate variance_band
library (band_from_raw) plus the formula block, asserting equality with
the recorded summary; refuses empty input (EmptyInputError); asserts
the delivery predicate. Formula: two-sample MDE=(z_a+z_b)s*sqrt(2/n);
CI95 = mean +/- z*s/sqrt(n); n_min=ceil(2((z_a+z_b)s/delta)^2),
delta=0.05|mean|; Bessel stdev."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "variance_band"))
from stats import EmptyInputError, band_from_raw  # noqa: E402

UNIT = "TST-0109"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
Z = 1.959963984540054
ZPOWER = 0.8416212335729143
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 4096, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0109" in text, "sentinel-absent")
    try:
        band_from_raw("x", [])
        chk(False, "empty-input-must-refuse")
    except EmptyInputError:
        chk(True, "empty-input-refused")
    except Exception as exc:
        chk(False, "empty-input-wrong-exception", type(exc).__name__)
    checks = 0
    for b in doc.get("benchmarks") or []:
        bid = str(b.get("id"))
        raw = b.get("raw") or []
        n = len(raw)
        chk(n == int(b.get("n", -1)), "n-rows:" + bid, str(n))
        lib = band_from_raw(bid, raw)
        mu = sum(raw) / n
        sd = lib["stdev"]
        mde = (Z + ZPOWER) * sd * math.sqrt(2.0 / n)
        hw = Z * sd / math.sqrt(n)
        delta = 0.05 * abs(mu)
        nmin = math.ceil(2.0 * ((Z + ZPOWER) * sd / delta) ** 2)
        chk(close(lib["mean"], float(b["mean"])) and close(sd, float(b["stdev"])), "mean-std:" + bid)
        chk(close(mde, float(b["mde"])), "mde:" + bid, str(mde) + " vs " + str(b["mde"]))
        vb = b.get("variance_band") or {}
        chk(close(hw, float(vb.get("halfwidth", -1))) and close(mu - hw, float(vb.get("low", 0))) and close(mu + hw, float(vb.get("high", 0))), "ci:" + bid)
        chk(nmin == int(b.get("n_min_for_claimed_5pct", -1)), "nmin:" + bid, str(nmin))
        checks += 1
    chk(checks >= 4, "benchmark-count", str(checks))
    c = (doc.get("controls") or {}).get("gaussian-seeded") or {}
    craw = c.get("raw") or []
    if craw:
        cb = band_from_raw("gaussian-seeded", craw)
        chk(close(cb["mean"], float(c["mean"])) and close(cb["stdev"], float(c["stdev"])) and close((Z + ZPOWER) * cb["stdev"] * math.sqrt(2.0 / len(craw)), float(c["mde"])), "gaussian-control")
        chk(int(c.get("n_min_for_claimed_5pct", -1)) == math.ceil(2.0 * ((Z + ZPOWER) * cb["stdev"] / (0.05 * abs(cb["mean"]))) ** 2), "gaussian-nmin")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails[:8]))
        return 1
    print(json.dumps({"benchmarks_rederived": checks, "empty_input": "refused",
                      "gaussian_control": "PASS" if craw else "absent"}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 all " + str(checks) + " benchmarks re-derive n/mean/stdev/CI95/MDE/n_min exactly from attached raw vectors via the estate band library + formula block; empty input refused; gaussian-seeded control reproduces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
