#!/usr/bin/env python3
"""CNF-0133 probe1 - both-states, blind form, leakage control (fail-closed).

Asserts from the published receipt: per-set and combined 2x2 confusion
matrices with RAW counts, both-states pass (>=1 planted-true CONFIRMED and
>=1 planted-false REFUTED per set), blind form (all confirmer-facing records
share ONE key set and the CLM-0133-<12hex> id template), and the leakage
control (zero plant tokens in any confirmer-facing record). Rebuilt
2026-10-26 (wave-3 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/CNF-0133.json"
UNIT = "CNF-0133"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
LEAK_TOKENS = ("planted", "oracle_label", "operator", "mutation",
               "falsified", "naive_verdict", "set_id")
ID_TPL = re.compile(r"^CLM-0133-[0-9a-f]{12}$")


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))

    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    check(doc.get("unit_id") == UNIT, "unit_id matches catalog unit")
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "artifact not self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact non-empty")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel present in artifact text")
    # ---- both-states + raw-count matrices from the receipt ----
    pi = doc.get("planted_items") or []
    check(len(pi) == 16, "16 planted items across both sets", str(len(pi)))
    for sid in ("set_a", "set_b"):
        rows = [p for p in pi if p.get("set_id") == sid]
        tp = sum(1 for p in rows if p["oracle_label"] == "true"
                 and p["confirmer_verdict"] == "CONFIRMED")
        fp = sum(1 for p in rows if p["oracle_label"] == "false"
                 and p["confirmer_verdict"] == "CONFIRMED")
        tn = sum(1 for p in rows if p["oracle_label"] == "false"
                 and p["confirmer_verdict"] == "REFUTED")
        fn = sum(1 for p in rows if p["oracle_label"] == "true"
                 and p["confirmer_verdict"] == "REFUTED")
        want = doc["per_set"][sid]["confusion_matrix"]
        got = {"true_positive": tp, "false_positive": fp,
               "true_negative": tn, "false_negative": fn}
        check(got == want, sid + " 2x2 matrix recompute equals published (raw counts)",
              json.dumps(got) + " vs " + json.dumps(want))
        check(tp >= 1 and tn >= 1,
              sid + " both-states: >=1 planted-true CONFIRMED and >=1 planted-false REFUTED")
    cm = doc.get("confusion_matrix") or {}
    check(cm == {"true_positive": 8, "false_positive": 4,
                 "true_negative": 4, "false_negative": 0},
          "combined 2x2 matrix is the published raw-count matrix",
          json.dumps(cm))
    arith = doc.get("arithmetic_recompute", {})
    check(arith.get("matches_published_matrix") is True,
          "receipt carries its own arithmetic recompute (matches published)")
    # ---- blind form: one key set, one id template, per-record schema ----
    recs = (doc.get("confirmation_records_set_a") or []) + \
           (doc.get("confirmation_records_set_b") or [])
    check(len(recs) == 20, "20 confirmer-facing records embedded", str(len(recs)))
    keysets = {tuple(sorted(r.keys())) for r in recs}
    check(len(keysets) == 1,
          "blind form: every record shares ONE key set regardless of label",
          str(len(keysets)))
    check(all(ID_TPL.match(r.get("claim_id", "")) for r in recs),
          "blind form: all claim ids share the CLM-0133-<12hex> template")

    # ---- leakage control: zero plant tokens in confirmer-facing records ----
    hits = []
    for r in recs:
        blob = json.dumps(r).lower()
        for t in LEAK_TOKENS:
            if t in blob:
                hits.append((r.get("claim_id"), t))
    check(not hits, "leakage control: zero plant tokens in any confirmer-facing record",
          "hits=" + str(hits[:4]))
    leak_block = doc.get("leakage") or {}
    check(leak_block.get("clean") is True,
          "published leakage block records clean=True")

    report = {
        "probe": "probe1-both-states-blind",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "checks": checks,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 both-states, blind form and leakage control hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
