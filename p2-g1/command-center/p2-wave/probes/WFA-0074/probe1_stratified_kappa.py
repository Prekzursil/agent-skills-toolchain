#!/usr/bin/env python3
"""Probe 1: stratified 60-sample, label-blind adjudicator, confusion matrix + kappa.

The adjudicator must not see existing labels. Family coverage (9/9) and used
disposition coverage (9/9) are proven from the drawn sample, not asserted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0074-disposition-cross-adjudication.json"


def main() -> int:
    records, meta = L.load_corpus()
    if len(records) < L.SAMPLE_N:
        print(f"FAILED:WFA-0074-probe1 corpus n={len(records)}")
        return 1
    sample = L.stratified_sample(records)
    cov = L.coverage(sample)
    if not cov["all_9_families"]:
        print(f"FAILED:WFA-0074-probe1 families {cov['families']}")
        return 1
    if not cov["all_9_used_dispositions"]:
        print(f"FAILED:WFA-0074-probe1 dispositions {cov['dispositions']}")
        return 1

    leaked = [r["id"] for r in sample if "classification" in L.withhold_labels(r)]
    if leaked:
        print(f"FAILED:WFA-0074-probe1 label leak {leaked[:8]}")
        return 1

    # Mutant: a withheld view with a bogus label still in the raw record must
    # not change the criteria verdict (label-primed re-adjudication is banned).
    mutant = dict(sample[0])
    mutant["classification"] = "REJECT"
    a_true = L.adjudicate(L.withhold_labels(sample[0]))["disposition"]
    a_mut = L.adjudicate(L.withhold_labels(mutant))["disposition"]
    if a_true != a_mut:
        print("FAILED:WFA-0074-probe1 label-primed verdict changed")
        return 1

    missing_rec = {
        "id": "probe1-missing",
        "family": "A-saved-workflow",
        "does": "",
        "provenance": "x",
    }
    refusal = L.adjudicate(L.withhold_labels(missing_rec))
    if refusal["disposition"] != "UNKNOWN-NEEDS-PROBE" or not refusal["missing"]:
        print("FAILED:WFA-0074-probe1 refusal path silent")
        return 1

    scored = L.run_adjudication(sample)
    conf = scored["confusion"]
    if conf["n"] != L.SAMPLE_N:
        print(f"FAILED:WFA-0074-probe1 n={conf['n']}")
        return 1
    if conf["kappa"] is None:
        print("FAILED:WFA-0074-probe1 kappa missing")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0074-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0074":
        print("FAILED:WFA-0074-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:WFA-0074" not in text:
        print("FAILED:WFA-0074-probe1 sentinel absent")
        return 1
    art_k = doc.get("kappa") or {}
    if abs(float(art_k.get("kappa")) - float(conf["kappa"])) > 1e-9:
        print("FAILED:WFA-0074-probe1 kappa mismatch vs artifact")
        return 1
    if int(art_k.get("n")) != L.SAMPLE_N:
        print("FAILED:WFA-0074-probe1 artifact n mismatch")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0074-probe1 self-declared", doc.get("state"))
        return 1

    payload = {
        "probe": "probe1-stratified-kappa",
        "source_mode": meta["mode"],
        "n_corpus": meta["n"],
        "n_sample": cov["n"],
        "families": cov["families"],
        "dispositions": cov["dispositions"],
        "agreements": conf["agreements"],
        "accuracy": conf["accuracy"],
        "kappa": conf["kappa"],
        "per_disposition_agreement": conf["per_disposition_agreement"],
        "label_blind": True,
        "refusal_on_missing": True,
        "sampling_rule": L.SAMPLING_RULE,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"kappa={conf['kappa']:.4f} agree={conf['agreements']}/{conf['n']} "
        f"families=9 dispositions=9 source={meta['mode']}"
    )
    print("SUCCESS:WFA-0074-probe1 stratified sample label-blind kappa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
