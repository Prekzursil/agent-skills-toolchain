#!/usr/bin/env python3
"""RES-0103 delivery predicate: explicit cost ratio, Chow threshold, inverse.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0103"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    th = doc.get("threshold_recommendation") or {}
    mw = float(th.get("assumed_cost_wrong") or 0)
    mm = float(th.get("assumed_cost_miss") or 0)
    tau = float(th.get("tau") or -1)
    c.append(("cost ratio stated explicitly with nonzero both sides", mw > 0 and mm > 0,
              f"C_wrong={mw} C_miss={mm}"))
    c.append(("tau equals the Chow reject threshold 1 - C_miss/C_wrong",
              abs(tau - (1 - mm / mw)) < 1e-9,
              f"tau={tau} recomputed={1 - mm / mw}"))
    iw = float(th.get("inverted_cost_wrong") or 0)
    im = float(th.get("inverted_cost_miss") or 0)
    itau = float(th["inverted_tau"]) if th.get("inverted_tau") is not None else -1.0
    c.append(("inverted ratio recorded and its tau collapses to zero",
              iw > 0 and im > 0 and abs(itau - max(0.0, 1 - im / iw)) < 1e-9,
              f"inverted C_wrong={iw} C_miss={im} inverted_tau={itau}"))
    c.append(("note names the ratio and the inversion consequence",
              "4:1" in str(th.get("note") or "") and "always" in str(th.get("note") or ""),
              str(th.get("note"))[:90]))
    eb = th.get("empirical_best_tau_on_fixture")
    fa = float(th.get("fixture_cost_always_answer") or 0)
    ft = float(th.get("fixture_cost_at_chow_tau") or 0)
    c.append(("fixture costs recorded with chow-tau cost below always-answer",
              eb is not None and ft < fa, f"best_tau={eb} cost_tau={ft} cost_always={fa}"))
    cr = doc.get("control_regime") or {}
    c.append(("regime where abstention is strictly worse is identified",
              "strictly more expensive" in str(cr.get("when_abstention_strictly_worse") or "").lower()
              and "C_miss >= C_wrong" in str(cr.get("when_abstention_strictly_worse") or ""),
              str(cr.get("when_abstention_strictly_worse") or cr.get("when_abstention_strictly_worse_text"))[:80]))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
