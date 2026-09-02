#!/usr/bin/env python3
"""Independent family recount / re-tabulation. A disagreement in n blocks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import analyze  # noqa: E402
import family  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0038-executable-runtime-semantics-for-the-6-deliberative-protoc.md"


def main() -> int:
    enum = family.enumeration()
    rows = analyze.verdicts()
    named = [m["id"] for m in enum["catalog_named"]]
    got = [r["record_id"] for r in rows]
    not_exec = [r for r in rows if r["verdict"] == "NOT-EXECUTABLE"]
    exec_rows = [r for r in rows if r["verdict"] == "EXECUTABLE"]
    print(
        f"catalog_expected_n={enum['catalog_expected_n']} "
        f"catalog_named_n={enum['catalog_named_n']} "
        f"slice_family_n={enum['slice_family_n']}"
    )
    print(f"named={named}")
    print(f"slice={enum['slice_family_ids']}")
    print(f"decoy_excluded={enum['decoy_excluded']}")
    print(f"library_present={enum['library_present']}")
    print(
        f"verdicts executable={len(exec_rows)} not_executable={len(not_exec)} "
        f"ids={[r['record_id']+':'+r['verdict'] for r in rows]}"
    )
    if not enum["counts_agree"]:
        print("FAILED:CNL-0038-probe1 family count disagreement")
        return 1
    if got != named or len(rows) != 6:
        print("FAILED:CNL-0038-probe1 verdict rows != catalog named list")
        return 1
    if len(not_exec) != 1 or not_exec[0]["record_id"] != "P01":
        print("FAILED:CNL-0038-probe1 expected sole NOT-EXECUTABLE P01")
        return 1
    if {r["record_id"] for r in exec_rows} != {"P02", "P03", "P04", "P05", "P06"}:
        print("FAILED:CNL-0038-probe1 executable set")
        return 1
    for row in exec_rows:
        ts = row.get("turn_schedule") or {}
        if not ts.get("stop_true_at_end") or not ts.get("stop_was_false_before_end"):
            print("FAILED:CNL-0038-probe1 tautology-or-no-halt", row["record_id"], ts)
            return 1
        if not ts.get("turns"):
            print("FAILED:CNL-0038-probe1 empty schedule", row["record_id"])
            return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0038-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0038" or "SUCCESS:CNL-0038" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0038-probe1 sentinel/unit")
        return 1
    art_ids = [v["record_id"] for v in doc.get("verdicts") or []]
    if art_ids != got:
        print("FAILED:CNL-0038-probe1 artifact/re-tabulation id disagreement", art_ids, got)
        return 1
    art_nx = doc.get("not_executable_ids")
    if art_nx != ["P01"]:
        print("FAILED:CNL-0038-probe1 artifact not_executable disagreement", art_nx)
        return 1
    if int(doc.get("family", {}).get("counted_n") or 0) != 6:
        print("FAILED:CNL-0038-probe1 artifact counted_n")
        return 1
    print("SUCCESS:CNL-0038-probe1 independent recount n=6 NOT-EXECUTABLE=P01")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
