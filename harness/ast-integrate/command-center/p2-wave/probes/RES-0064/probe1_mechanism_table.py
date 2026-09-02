#!/usr/bin/env python3
"""Probe 1: mechanism table, entanglement verdicts, inseparable example, local schema gap."""
from __future__ import annotations

import copy
import json
import sys

import lib as L

LANGS = {"CWL", "WDL", "Nextflow", "Snakemake", "RO-Crate"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0064-probe1 {msg}")
    return 1


def table_errors(table: list) -> list[str]:
    errs: list[str] = []
    if not isinstance(table, list) or len(table) < 8:
        return [f"table too small: {0 if not isinstance(table, list) else len(table)}"]
    langs = set()
    inseparable = []
    for i, row in enumerate(table):
        if not isinstance(row, dict):
            errs.append(f"row[{i}] not object")
            continue
        rid = row.get("id")
        verdict = row.get("runtime_entanglement_verdict")
        if verdict not in L.ENTANGLEMENT:
            errs.append(f"{rid}: bad verdict {verdict!r}")
        lang = row.get("source_language")
        langs.add(lang)
        if not row.get("mechanism") or not row.get("what_it_does"):
            errs.append(f"{rid}: empty mechanism/what")
        if not row.get("how_to_avoid_importing_a_runtime"):
            errs.append(f"{rid}: missing how_to_avoid")
        if not isinstance(row.get("adopting_would_import_a_runtime"), bool):
            errs.append(f"{rid}: adopting_would_import_a_runtime not bool")
        if verdict == "INSEPARABLE" and row.get("adopting_would_import_a_runtime") is not True:
            errs.append(f"{rid}: INSEPARABLE must import a runtime")
        if verdict == "SEPARABLE" and row.get("adopting_would_import_a_runtime") is not False:
            errs.append(f"{rid}: SEPARABLE must not import a runtime")
        if row.get("is_inseparable_example"):
            inseparable.append(row)
    missing_lang = LANGS - langs
    if missing_lang:
        errs.append(f"missing languages {sorted(missing_lang)}")
    if not inseparable:
        errs.append("no is_inseparable_example row")
    for row in inseparable:
        if row.get("runtime_entanglement_verdict") != "INSEPARABLE":
            errs.append(f"{row.get('id')}: inseparable example not INSEPARABLE")
    return errs


def schema_errors(art: dict, live: dict) -> list[str]:
    errs: list[str] = []
    if not live["inputs_are_string_array"] or not live["outputs_are_string_array"]:
        errs.append("live schema I/O is not string arrays")
    if live["mentions_file_type"] or live["mentions_checksum"] or live["mentions_ro_crate"]:
        errs.append("live schema unexpectedly has File/checksum/RO-Crate")
    recorded = art.get("local_schema_gap") or {}
    if recorded.get("sha256") != live["sha256"]:
        errs.append("recorded schema sha256 != live")
    if not recorded.get("inputs_are_string_array"):
        errs.append("artifact does not record string-array inputs")
    return errs


def main() -> int:
    art = L.load_artifact()
    text = json.dumps(art)
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {art.get('state')}")
    if L.SENTINEL not in text:
        return fail("sentinel absent")
    table = art.get("mechanism_table") or []
    good = table_errors(table)
    if good:
        return fail("good table: " + "; ".join(good[:8]))

    mutant = copy.deepcopy(table)
    mutant[0]["runtime_entanglement_verdict"] = ""
    bad = table_errors(mutant)
    if not bad:
        return fail("blanked verdict still accepted (silent both states)")

    mutant2 = copy.deepcopy(table)
    for row in mutant2:
        row["is_inseparable_example"] = False
    bad2 = table_errors(mutant2)
    if not bad2:
        return fail("cleared inseparable example still accepted")

    live = L.local_schema_gap()
    serr = schema_errors(art, live)
    if serr:
        return fail("; ".join(serr))

    example = art.get("inseparable_example") or {}
    if example.get("mechanism_id") != "M-NEXTFLOW-CHANNELS":
        return fail(f"inseparable_example id {example.get('mechanism_id')}")

    print(
        json.dumps(
            {
                "probe": "probe1-mechanism-table",
                "rows": len(table),
                "verdicts": sorted(
                    {r["runtime_entanglement_verdict"] for r in table}
                ),
                "inseparable": [
                    r["id"] for r in table if r.get("is_inseparable_example")
                ],
                "mutation_blank_verdict_errs": bad[:3],
                "mutation_no_inseparable_errs": bad2[:3],
                "schema_inputs_line": live["inputs_line"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0064-probe1 mechanism table and local schema gap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
