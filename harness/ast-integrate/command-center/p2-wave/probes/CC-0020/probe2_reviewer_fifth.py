#!/usr/bin/env python3
"""Probe 2: reviewer fifth mutant class + determinism.

Mechanically different from probe 1: does not retune thresholds; scores a
register-shift SOP the calibration set never contained. Also re-runs the
whole matrix three times and requires byte-identical verdicts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from eval import determinism_check, score_fifth  # noqa: E402
from gate import LEX_FIRE, EMB_FIRE  # noqa: E402

RECEIPT = HERE.parents[3] / "command-center" / "receipts" / "CC-0020.json"


def main() -> int:
    fifth = score_fifth()
    det = determinism_check(3)
    summary = {
        "fifth_class": fifth["mutant_class"],
        "fifth_verdict": fifth["verdict"],
        "fifth_caught": fifth["caught"],
        "fifth_jaccard": fifth["jaccard"],
        "fifth_cosine": fifth["cosine"],
        "fifth_lex_fires": fifth["lex_fires"],
        "fifth_emb_fires": fifth["emb_fires"],
        "thresholds_frozen": {"lex_fire": LEX_FIRE, "emb_fire": EMB_FIRE},
        "determinism_identical": det["identical"],
        "determinism_runs": det["runs"],
    }
    print(json.dumps(summary, sort_keys=True))
    if not fifth["caught"]:
        print("FAILED:CC-0020-probe2 fifth class not caught", fifth)
        return 1
    if fifth["error_direction"] == "under-merge":
        print("FAILED:CC-0020-probe2 fifth class under-merged")
        return 1
    if not det["identical"]:
        print("FAILED:CC-0020-probe2 non-deterministic verdicts", det)
        return 1
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if "SUCCESS:CC-0020" not in json.dumps(doc):
            print("FAILED:CC-0020-probe2 sentinel absent")
            return 1
        rev = doc.get("reviewer") or {}
        if rev.get("verdict") != "PASS" or not rev.get("independent"):
            print("FAILED:CC-0020-probe2 receipt reviewer not independent PASS")
            return 1
        if (doc.get("reviewer_fifth_class") or {}).get("verdict") != fifth["verdict"]:
            print("FAILED:CC-0020-probe2 receipt fifth verdict drift")
            return 1
        directions = doc.get("error_direction_report") or []
        if not directions:
            print("FAILED:CC-0020-probe2 receipt missing error_direction_report")
            return 1
    print("SUCCESS:CC-0020-probe2 fifth-class catch + determinism")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
