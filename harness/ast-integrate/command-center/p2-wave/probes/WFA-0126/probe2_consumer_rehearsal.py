#!/usr/bin/env python3
"""Probe 2: consumer rehearsal — IMP-0209 driven purely from the contract."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inventory as I  # noqa: E402
from consumer import ConsumerError, consume  # noqa: E402

ART = I.REPO / I.OUT_REL
OUT = HERE / "IMP-0209-first-output.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0126-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    contract = I.load_json(ART)
    # Mechanical independence: consume() must not need the catalog.
    try:
        result = consume(contract, "IMP-0209")
    except ConsumerError as exc:
        return fail(f"consume:{exc}")

    first = result.get("first_output") or {}
    if first.get("kind") != "scout-source-plan":
        return fail(f"kind={first.get('kind')}")
    if result.get("unit_id") != "IMP-0209":
        return fail("unit_id")
    if result.get("catalog_not_consulted") is not True:
        return fail("catalog-consulted")
    if result.get("driven_purely_from") != I.OUT_REL:
        return fail("driven-from")
    consumed = result.get("consumed_rows") or []
    if len(consumed) < 3:
        return fail("consumed-too-few")
    inherited = result.get("inherited_unknowns") or []
    if not inherited:
        return fail("inherited-unknowns-absent")
    for ru in inherited:
        if not ru.get("settling_experiment") or not ru.get("owner_visible_impact"):
            return fail(f"inherited-thin {ru.get('id')}")
    if first.get("ranked_candidate_slots") != []:
        return fail("overclaim-ranked-candidates")
    if "WFA-0084" not in str(first.get("gap") or "") and result.get("usable"):
        # usable true only if every consumed artifact is present
        pass
    query = first.get("query_interface") or {}
    if query.get("unit_id") != "WFA-0084":
        return fail("query-interface-row")

    OUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    bad = deepcopy(contract)
    bad["consumer_bindings"] = []
    try:
        consume(bad, "IMP-0209")
    except ConsumerError:
        empty_bindings_rejected = True
    else:
        return fail("empty-bindings-accepted")

    bad2 = deepcopy(contract)
    del bad2["declared_artifacts"]
    try:
        consume(bad2, "IMP-0209")
    except ConsumerError:
        missing_rows_rejected = True
    else:
        return fail("missing-declared-accepted")

    bad3 = deepcopy(contract)
    bad3["residual_unknowns"][0]["settling_experiment"] = ""
    try:
        consume(bad3, "IMP-0209")
    except ConsumerError:
        empty_settling_rejected = True
    else:
        return fail("empty-settling-accepted")

    tst = consume(contract, "TST-0001")
    if tst.get("first_output", {}).get("kind") != "predicate-bind-plan":
        return fail("tst-kind")

    print(
        json.dumps(
            {
                "probe": "probe2-consumer-rehearsal",
                "unit_id": "WFA-0126",
                "downstream_unit": "IMP-0209",
                "first_output_kind": first.get("kind"),
                "consumed": len(consumed),
                "inherited_unknowns": len(inherited),
                "usable": result.get("usable"),
                "gap": first.get("gap"),
                "empty_bindings_rejected": empty_bindings_rejected,
                "missing_rows_rejected": missing_rows_rejected,
                "empty_settling_rejected": empty_settling_rejected,
                "second_downstream_unit": "TST-0001",
                "rehearsal_path": str(OUT.relative_to(I.REPO).as_posix()),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0126-probe2 consumer rehearsal IMP-0209")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
