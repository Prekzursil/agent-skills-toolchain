#!/usr/bin/env python3
"""Named probe 1: recovered sources must EXECUTE and match original outputs.

Signal is sha256 of canonical recovered output vs frozen/live original output.
Listing a source in fusion metadata does not satisfy this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from workflow import (  # noqa: E402
    ORIGINAL_OUT_DIR,
    canonical_dumps,
    load_json,
    run_analysis,
    sha256_text,
)

ART = REPO / "command-center/confirmation/CNF-0076-fusion-decomposition.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0076-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0076":
        print("FAILED:CNF-0076-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0076" not in json.dumps(doc):
        print("FAILED:CNF-0076-probe1 sentinel absent")
        return 1

    analysis = run_analysis()
    exec_ = analysis["lossy_exec"]
    if not exec_["every_recovered_source_executed"]:
        print("FAILED:CNF-0076-probe1 recovered sources did not execute")
        return 1
    if not exec_["every_recovered_output_matches"]:
        print("FAILED:CNF-0076-probe1 output mismatch")
        print(json.dumps(exec_["recovered"], indent=2, default=str)[:3000])
        return 1
    if len(exec_["recovered"]) < 2:
        print("FAILED:CNF-0076-probe1 recovered count", len(exec_["recovered"]))
        return 1
    lost = exec_["lost_capabilities"]
    if not any(item.get("source_id") == "wf.license-stamp" for item in lost):
        print("FAILED:CNF-0076-probe1 lost capability not filed")
        print(json.dumps(lost, indent=2)[:2000])
        return 1

    for src in analysis["sources"]:
        frozen = ORIGINAL_OUT_DIR / f"{src['id']}.json"
        if not frozen.is_file():
            print("FAILED:CNF-0076-probe1 frozen original missing", frozen.name)
            return 1
        frozen_doc = load_json(frozen)
        live = analysis["original_runs"][src["id"]]["doc"]
        if sha256_text(canonical_dumps(frozen_doc)) != sha256_text(canonical_dumps(live)):
            print("FAILED:CNF-0076-probe1 frozen original drifted", src["id"])
            return 1

    payload = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    recovered_rows = payload.get("recovered") or doc.get("recovered") or []
    recorded = {row["source_id"]: row for row in recovered_rows}
    for row in exec_["recovered"]:
        rec = recorded.get(row["source_id"])
        if not rec:
            print("FAILED:CNF-0076-probe1 artifact missing recovered", row["source_id"])
            return 1
        if rec.get("executed") is not True:
            print("FAILED:CNF-0076-probe1 artifact did not record execute", row["source_id"])
            return 1
        art_sha = (rec.get("diff_against_original") or {}).get("recovered_sha256")
        if art_sha != row["diff_against_original"]["recovered_sha256"]:
            print("FAILED:CNF-0076-probe1 artifact sha drift", row["source_id"])
            return 1

    out = {
        "probe": "probe1-execute-recovered",
        "unit_id": "CNF-0076",
        "recovered_count": len(exec_["recovered"]),
        "every_recovered_source_executed": True,
        "every_recovered_output_matches": True,
        "lost_capability_filed": "wf.license-stamp",
        "recovered_sha256": {
            row["source_id"]: row["diff_against_original"]["recovered_sha256"]
            for row in exec_["recovered"]
        },
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "executed="
        f"{len(exec_['recovered'])}/{len(exec_['recovered'])} "
        "match=True lost=wf.license-stamp"
    )
    print("SUCCESS:CNF-0076-probe1 recovered sources executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
