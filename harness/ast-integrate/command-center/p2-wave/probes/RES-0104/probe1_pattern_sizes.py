#!/usr/bin/env python3
"""Probe 1: live re-parse of captures vs annotated pattern sizes.

Both-states: the real artifact must match capture-derived sizes; a mutant
that lies about catalog_size_observed must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import observed as O  # noqa: E402

ART = REPO / "command-center/research/RES-0104.json"


def sizes_from_doc(doc: dict) -> dict[str, int]:
    return {p["id"]: int(p["catalog_size_observed"]) for p in doc["patterns"]}


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0104-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.check(doc, repo=REPO)
    print(f"contract_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0104-probe1 contract")
        return 1
    obs = O.load()
    got = sizes_from_doc(doc)
    expect = {
        "P-INDEX-HYDRATE": obs["vscode_marketplace_extensions"],
        "P-SEARCH-PAGINATE": obs["npm_search_total"],
        "P-AGGREGATED-DISCOVERY": obs["k8s_openapi_v3_documents"],
    }
    print(f"observed={obs}")
    print(f"annotated={got}")
    for pid, n in expect.items():
        if got.get(pid) != n:
            print(f"FAILED:RES-0104-probe1 size-mismatch {pid} want={n} got={got.get(pid)}")
            return 1
    bp = int(doc["breaking_point"]["breaks_above"])
    if bp != obs["k8s_unaggregated_break_requests"]:
        print(f"FAILED:RES-0104-probe1 breaks_above want=80 got={bp}")
        return 1
    if not any(int(p["catalog_size_observed"]) >= 500 for p in doc["patterns"]):
        print("FAILED:RES-0104-probe1 no pattern observed at >=500")
        return 1
    if doc["answer_for_500"]["pattern_id"] != "P-INDEX-HYDRATE":
        print("FAILED:RES-0104-probe1 answer pattern")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["patterns"][0]["catalog_size_observed"] = 50
    mok, mwhy = C.check(mutant, repo=REPO)
    print(f"size_lie_ok={mok} {mwhy}")
    # Contract still accepts 50 as a positive int; probe1 must catch the lie
    # against captures even if schema-level checks pass.
    if sizes_from_doc(mutant)["P-INDEX-HYDRATE"] == expect["P-INDEX-HYDRATE"]:
        print("FAILED:RES-0104-probe1 mutant did not change size")
        return 1
    if mok and sizes_from_doc(mutant)["P-INDEX-HYDRATE"] != expect["P-INDEX-HYDRATE"]:
        # Discriminating extra check lives here, not only in contract.
        print("probe1-extra: size lie would be accepted by contract; probe rejects it")
    dropped = copy.deepcopy(doc)
    del dropped["patterns"][0]["catalog_size_observed"]
    dok, dwhy = C.check(dropped, repo=REPO)
    print(f"drop_size_ok={dok} {dwhy}")
    if dok:
        print("FAILED:RES-0104-probe1 drop size was accepted")
        return 1

    print(
        "SUCCESS:RES-0104-probe1 pattern sizes match captures and "
        "catalog_size_observed is required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
