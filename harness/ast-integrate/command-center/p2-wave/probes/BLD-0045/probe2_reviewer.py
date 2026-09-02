#!/usr/bin/env python3
"""Named probe 2: independent reviewer + mutation pivot.

Reviewer: delete the assertion on one covered region (asserted_value) and
confirm the audit reclassifies it as COVERED-UNASSERTED.

Pivot: mutate the except-arm rolled_back effect; the suite stays green, proving
the except region is unasserted empirically, not only by static inference.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import auditor as A  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0045.json"


def main() -> int:
    reviewer = A.reviewer_delete_assert()
    print(
        "reviewer_ok={ok} reclassified={reclassified_asserted_value} "
        "after={unasserted_functions}".format(**{k: reviewer.get(k) for k in (
            "ok", "reclassified_asserted_value", "unasserted_functions"
        )})
    )
    if not reviewer.get("ok") or not reviewer.get("reclassified_asserted_value"):
        print("FAILED:BLD-0045-probe2 reviewer did not reclassify asserted_value")
        return 1
    if reviewer.get("rewritten_has_assert"):
        print("FAILED:BLD-0045-probe2 assertion was not actually deleted")
        return 1

    mutation = A.mutate_except_and_retest()
    print(
        f"mutation_still_green={mutation['tests_still_green']} "
        f"failed={mutation['failed_tests']}"
    )
    if not mutation["tests_still_green"]:
        print("FAILED:BLD-0045-probe2 except mutation turned tests red")
        return 1

    if not ART.is_file():
        print("FAILED:BLD-0045-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:BLD-0045-probe2 reviewer independence flags")
        return 1
    if rev.get("reclassified_asserted_value") is not True:
        print("FAILED:BLD-0045-probe2 receipt reviewer did not record reclassification")
        return 1
    if str(rev.get("verdict") or "").upper() != "PASS":
        print("FAILED:BLD-0045-probe2 reviewer verdict")
        return 1
    pivot = doc.get("mutation_pivot") or {}
    if pivot.get("tests_still_green") is not True:
        print("FAILED:BLD-0045-probe2 receipt mutation pivot not green")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["reviewer"]["reclassified_asserted_value"] = False
    if mutant["reviewer"]["reclassified_asserted_value"] is True:
        print("FAILED:BLD-0045-probe2 could not strip reclassification flag")
        return 1
    # The live reviewer already proved the audit reclassifies. A receipt that
    # omitted that flag would fail this probe — green-not-live guard.
    if doc["reviewer"]["reclassified_asserted_value"] is not True:
        print("FAILED:BLD-0045-probe2 live receipt lost the reclassification flag")
        return 1

    b08 = doc.get("b08_suite_coverage") or {}
    if b08.get("status") == "PRESENT" and not (b08.get("found") or []):
        print("FAILED:BLD-0045-probe2 overclaim: B08 PRESENT with no files")
        return 1
    shipped = doc.get("shipped_tree_scan") or {}
    if shipped.get("coverage") == "line" or shipped.get("coverage") is True:
        print("FAILED:BLD-0045-probe2 overclaim: shipped tree claimed covered")
        return 1

    print("SUCCESS:BLD-0045-probe2 reviewer reclassify plus except mutation pivot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
