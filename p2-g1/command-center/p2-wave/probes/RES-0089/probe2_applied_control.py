#!/usr/bin/env python3
"""RES-0089 independent re-derivation: live canary scan, both states + NC.
The canary token is read from the artifact itself (no hardcoded literal)."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0089"

def canary_scan(file_text: str, canary: str, catalog_sample: str) -> dict:
    exact = canary.split(" ")[0] in file_text
    return {"exact_hit": exact,
            "ngram_overlap": L.char3gram_overlap(file_text, catalog_sample)}

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    ar = doc.get("applied_result") or {}
    both = ar.get("both_states") or {}
    canary = str(both.get("canary") or "")
    c.append(("applied control names a canary and a benchmark to guard",
              bool(canary) and "WORK-UNIT-CATALOG.json" in str(ar.get("benchmark_path") or ""),
              f"canary={canary[:40]}... benchmark={ar.get('benchmark_id')}"))
    cat = L.REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    catalog_sample = cat.read_text(encoding="utf-8", errors="ignore")[:400_000]
    clean = (HERE / "fixtures" / "clean-boilerplate.txt").read_text(encoding="utf-8")
    planted = (HERE / "fixtures" / "planted-benchmark-case.txt").read_text(encoding="utf-8")
    r_clean = canary_scan(clean, canary, catalog_sample)
    r_planted = canary_scan(planted, canary, catalog_sample)
    c.append(("clean control: no canary hit (FPR 0)", not r_clean["exact_hit"],
              f"exact_hit={r_clean['exact_hit']} overlap={r_clean['ngram_overlap']}"))
    c.append(("planted control: canary hit (TPR 1)", r_planted["exact_hit"],
              f"exact_hit={r_planted['exact_hit']} overlap={r_planted['ngram_overlap']}"))
    c.append(("measured rates match the artifact record",
              float(both.get("measured_fpr_on_clean_control", -1)) == 0.0
              and float(both.get("measured_tpr_on_planted_control", -1)) == 1.0,
              f"fpr={both.get('measured_fpr_on_clean_control')} "
              f"tpr={both.get('measured_tpr_on_planted_control')}"))
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    Path(tmp).write_text(clean.replace("generic filler lines",
                                       "generic filler lines, " + canary), encoding="utf-8")
    try:
        txt = Path(tmp).read_text(encoding="utf-8")
        fired = canary_scan(txt, canary, catalog_sample)["exact_hit"]
        c.append(("NC: canary smuggled into a clean fixture fires the detector", fired,
                  f"fired={fired}"))
    finally:
        Path(tmp).unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
