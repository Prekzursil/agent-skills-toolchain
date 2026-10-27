"""IMP-0269 probe 1: tag-matching precision/recall on a labelled fixture.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0269/probe1_tag_precision.py
Exit 0 iff the live tools/council/participants/select_expertise.tag_match_metrics
scores the 12-row labelled fixture at precision=1.0 recall=1.0 (tp=6 tn=6
fp=0 fn=0); the taxidermy near-miss does NOT match tax-law; the taxation
alias DOES match tax-law.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from select_expertise import tag_match_metrics  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "labelled-tags.json"
rows = json.loads(FIX.read_text(encoding="utf-8"))["rows"]
m = tag_match_metrics(rows)

by_id = {r["row_id"]: r for r in m["rows"]}
checks = {
    "n_is_12": m["n"] == 12,
    "precision_1": m["precision"] == 1.0,
    "recall_1": m["recall"] == 1.0,
    "f1_1": m["f1"] == 1.0,
    "tp6_tn6": m["tp"] == 6 and m["tn"] == 6,
    "fp0_fn0": m["fp"] == 0 and m["fn"] == 0,
    "alias_taxation_matches": by_id["r02"]["predicted"] is True,
    "alias_crypto_matches": by_id["r03"]["predicted"] is True,
    "underscore_normalises": by_id["r04"]["predicted"] is True,
    "near_miss_taxidermy_rejected": by_id["r07"]["predicted"] is False,
    "near_miss_tariff_law_rejected": by_id["r09"]["predicted"] is False,
}
ok = all(checks.values())
out = {"probe": "probe1-tag-precision-recall", "unit_id": "IMP-0269",
       "n": m["n"], "tp": m["tp"], "tn": m["tn"], "fp": m["fp"], "fn": m["fn"],
       "precision": m["precision"], "recall": m["recall"], "f1": m["f1"],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-tag-precision.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0269-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0269-probe1 precision=1.000 recall=1.000 tp=6 tn=6 fp=0 fn=0; near-miss and alias both correct")
