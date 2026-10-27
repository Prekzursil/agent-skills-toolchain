#!/usr/bin/env python3
"""TST-0085 probe1: budget-curve re-derivation (live, fail-closed).

Re-derives the repaired variance_band from raw_runs (Bessel), recounts
every embedded payload with the estate token counter, asserts the budget
ceiling holds against the raw max, the growth curve is sublinear, and
the delivery predicate. The receipt's band was repaired during resume
(the prior band was not re-derivable; repair note is on the receipt)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "TST-0085"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
TOKEN_RE = re.compile("\\" + "w+|[^" + chr(92) + "s" + chr(92) + "w]")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def band_of(vals: list[int]) -> dict:
    n = len(vals)
    mu = sum(vals) / n
    var = sum((x - mu) ** 2 for x in vals) / (n - 1) if n > 1 else 0.0
    sd = var ** 0.5
    se = sd / n ** 0.5
    z = 1.959963984540054
    return {"n": n, "mean": mu, "sample_variance": var, "sample_std": sd, "se": se,
            "ci95_low": mu - z * se, "ci95_high": mu + z * se}


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 4096, "under-min-bytes", str(OUT.stat().st_size))
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0085" in text, "sentinel-absent")
    chk("REPAIR" in str(doc.get("notes") or ""), "repair-note-present")

    runs = doc.get("raw_runs") or []
    chk(len(runs) == 24, "raw-run-count", str(len(runs)))
    toks = [int(r["injected_tokens"]) for r in runs]
    vb = doc.get("variance_band") or {}
    chk(vb.get("derived_from") == "raw_runs", "band-derived-from")
    got = band_of(toks)
    for k in ("n", "mean", "sample_variance", "sample_std", "se", "ci95_low", "ci95_high"):
        chk(close(float(got[k]), float(vb[k])), "band-rederive:" + k, "computed=" + str(got[k]) + " recorded=" + str(vb.get(k)))
    chk(int(vb.get("sum", -1)) == sum(toks) and int(vb.get("max", -1)) == max(toks), "band-sum-max")
    for ic in ("10", "100", "500"):
        sub = [int(r["injected_tokens"]) for r in runs if str(r["installed_count"]) == ic]
        g = band_of(sub)
        rec = (vb.get("per_installed_count") or {}).get(ic) or {}
        for k in ("n", "mean", "sample_variance", "sample_std"):
            chk(close(float(g[k]), float(rec.get(k, float("nan")))), "band-per-installed:" + ic + ":" + k)
    # payload recount with the estate counter
    recountable = recounted = 0
    for r in runs:
        pl = r.get("payload")
        if not pl:
            continue
        recountable += 1
        if len(TOKEN_RE.findall(pl)) == int(r["injected_tokens"]):
            recounted += 1
    chk(recountable >= 20 and recounted == recountable, "payload-recount", str(recounted) + "/" + str(recountable))
    # budget ceiling vs raw max; sublinear growth
    budget = doc.get("budget") or {}
    ceiling = int(budget.get("ceiling", 0))
    chk(ceiling == 500, "ceiling-value")
    chk(max(toks) <= ceiling, "budget-held", "max=" + str(max(toks)))
    curve = doc.get("growth_curve") or []
    tpi = [float(g["tokens_per_installed"]) for g in curve]
    chk(len(tpi) == 3 and tpi[0] > tpi[1] > tpi[2], "growth-sublinear", str(tpi))
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails[:10]))
        return 1
    print(json.dumps({"band": {k: round(float(v), 6) if isinstance(v, float) else v for k, v in vb.items() if k != "per_installed_count"},
                      "payload_recount": str(recounted) + "/" + str(recountable),
                      "budget": {"ceiling": ceiling, "raw_max": max(toks), "held": True},
                      "growth_tokens_per_installed": tpi}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 repaired band re-derives exactly from raw_runs (n=24 mean=115.375); payload recount " + str(recounted) + "/" + str(recountable) + "; budget 500 held at raw max " + str(max(toks)) + "; growth sublinear " + str(tpi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
