#!/usr/bin/env python3
"""Probe 2: error DIRECTION before accuracy; dangerous-class re-run, not patch.

Prints the conservative/dangerous/other split FIRST, then accuracy. A planted
conservative disagreement and a planted dangerous disagreement must both fire.
If dangerous-direction errors exceed the stated threshold, every contributing
disposition class is re-run under the same criteria; rows are not patched.
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
    sample = L.stratified_sample(records)
    scored = L.run_adjudication(sample)
    direction = scored["direction"]
    conf = scored["confusion"]

    # DIRECTION FIRST — a comfortable aggregate must not lead the reading.
    print(
        "DIRECTION "
        f"conservative={direction['conservative_toward_unknown_or_repair']} "
        f"dangerous={direction['dangerous_toward_adopt_as_is']} "
        f"other={direction['other']} "
        f"disagreements={direction['disagreements']}"
    )
    print(
        f"ACCURACY {conf['accuracy']:.4f} kappa={conf['kappa']:.4f} "
        f"agree={conf['agreements']}/{conf['n']}"
    )

    plants = L.planted_direction_controls()
    if not plants["conservative_plant"]["pass"]:
        print("FAILED:WFA-0074-probe2 conservative plant silent", plants["conservative_plant"])
        return 1
    if not plants["dangerous_plant"]["pass"]:
        print("FAILED:WFA-0074-probe2 dangerous plant silent", plants["dangerous_plant"])
        return 1
    refusal = plants["missing_input_refusal"]
    if refusal["disposition"] != "UNKNOWN-NEEDS-PROBE":
        print("FAILED:WFA-0074-probe2 missing-input plant", refusal)
        return 1

    exceeded = scored["threshold_exceeded"]
    rerun = scored["class_rerun"]
    if exceeded:
        if not rerun or rerun.get("patched") is True:
            print("FAILED:WFA-0074-probe2 threshold exceeded but class was patched")
            return 1
        if not rerun.get("classes"):
            print("FAILED:WFA-0074-probe2 threshold exceeded with no class re-run")
            return 1
        if rerun.get("stable") is not True:
            print("FAILED:WFA-0074-probe2 class re-run not stable", rerun)
            return 1
        print(
            "CLASS-RERUN "
            f"classes={rerun['classes']} records={rerun['records_rerun']} "
            "stable=True patched=False"
        )
    else:
        print("CLASS-RERUN not-required threshold-not-exceeded")

    if not ART.is_file():
        print("FAILED:WFA-0074-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0074" not in json.dumps(doc):
        print("FAILED:WFA-0074-probe2 sentinel absent")
        return 1
    headline = str(doc.get("headline") or "")
    dir_at = headline.find("DIRECTION")
    acc_at = headline.find("accuracy=")
    if dir_at < 0 or acc_at < 0 or dir_at > acc_at:
        print("FAILED:WFA-0074-probe2 artifact headline does not lead with DIRECTION")
        return 1
    art_dir = doc.get("direction_split") or {}
    if int(art_dir.get("dangerous_toward_adopt_as_is")) != int(
        direction["dangerous_toward_adopt_as_is"]
    ):
        print("FAILED:WFA-0074-probe2 direction mismatch vs artifact")
        return 1
    if doc.get("tests_required_order") != ["direction_split", "accuracy"]:
        print("FAILED:WFA-0074-probe2 tests_required_order")
        return 1

    payload = {
        "probe": "probe2-direction",
        "source_mode": meta["mode"],
        "direction_first": True,
        "conservative": direction["conservative_toward_unknown_or_repair"],
        "dangerous": direction["dangerous_toward_adopt_as_is"],
        "other": direction["other"],
        "accuracy": conf["accuracy"],
        "kappa": conf["kappa"],
        "threshold": {
            "of_sample": L.DANGEROUS_OF_SAMPLE_THRESHOLD,
            "of_disagreements": L.DANGEROUS_OF_DISAGREEMENTS_THRESHOLD,
            "exceeded": exceeded,
        },
        "class_rerun": rerun,
        "plants": plants,
        "estate_precedent": (
            "86 percent accuracy with 100 percent of errors pointing at data loss"
        ),
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print("SUCCESS:WFA-0074-probe2 direction-before-accuracy class-rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
