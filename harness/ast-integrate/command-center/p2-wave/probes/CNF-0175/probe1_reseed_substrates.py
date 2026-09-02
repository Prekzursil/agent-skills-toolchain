#!/usr/bin/env python3
"""Named probe 1: re-run three seeds on two substrates. Do not read cert scores."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fusion_core as fc  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0175.json"
CERT = HERE / "adjudicator" / "certification.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0175-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:CNF-0175" not in blob:
        print("FAILED:CNF-0175-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0175-probe1 process state not SUCCESS")
        return 1
    if not doc.get("source_probe") or not doc.get("verifier_probe"):
        print("FAILED:CNF-0175-probe1 missing probes")
        return 1
    if doc["source_probe"].get("fingerprint") == doc["verifier_probe"].get("fingerprint"):
        print("FAILED:CNF-0175-probe1 same-probe-rerun fingerprints")
        return 1

    # Confirmer must not consume original certification scores.
    # We only check the path exists; we do not read the file body.
    if not CERT.is_file():
        print("FAILED:CNF-0175-probe1 cert envelope missing (path check only)")
        return 1

    empty = fc.empty_input_control()
    refuse = fc.refuse_empty_run([])
    if not empty.get("ok") or refuse.get("ok") is not False:
        print("FAILED:CNF-0175-probe1 empty-input control")
        return 1

    wids = [fc.FUSION, fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C]
    rows = fc.run_matrix(
        fc.CONFIRM_SEEDS,
        [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
        wids,
    )
    live = []
    for seed in fc.CONFIRM_SEEDS:
        for sub in (fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS):
            live.append(fc.summarize_condition(rows, seed, sub))
    agreement = fc.substrate_agreement(rows, fc.CONFIRM_SEEDS)
    if not agreement["agree"]:
        print("FAILED:CNF-0175-probe1 substrates disagree")
        print(json.dumps(agreement, indent=2)[:2000])
        return 1

    recorded = doc["corrected_repro"]["summaries"]
    if len(recorded) != len(live):
        print(f"FAILED:CNF-0175-probe1 summary count {len(recorded)} != {len(live)}")
        return 1
    for got, rec in zip(live, recorded):
        if got["mean_f1"] != rec["mean_f1"]:
            print("FAILED:CNF-0175-probe1 mean_f1 drift", got["seed"], got["substrate"])
            return 1
        if got["ci_excludes_zero_or_negative"] != rec["ci_excludes_zero_or_negative"]:
            print("FAILED:CNF-0175-probe1 CI flag drift")
            return 1
        if not got["fusion_beats_each_source_mean"]:
            print("FAILED:CNF-0175-probe1 fusion does not beat each source")
            return 1
        if not got["weak_source_loses"]:
            print("FAILED:CNF-0175-probe1 weak source did not lose")
            return 1

    out = {
        "probe": "probe1-reseed-substrates",
        "unit_id": "CNF-0175",
        "n_summaries": len(live),
        "seeds": list(fc.CONFIRM_SEEDS),
        "substrates": [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
        "agreement": agreement["agree"],
        "empty_ok": True,
        "cert_body_unread": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0175-probe1 re-seed and substrate confirmation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
