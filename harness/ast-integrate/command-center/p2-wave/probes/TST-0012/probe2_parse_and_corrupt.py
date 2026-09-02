#!/usr/bin/env python3
"""Probe 2: live parse+field-read succeeds; one-byte corrupt fails loudly."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

REPORT = REPO / M.OUT_REL


def main() -> int:
    catalog = M.load_catalog()
    live = M.build_matrix(catalog)
    cells = live["cells"]
    read_ok = [c for c in cells if c["status"] == "READ_OK"]
    if not read_ok:
        print("FAILED:TST-0012-probe2 no READ_OK cell (parse+field-read never ran)")
        return 1

    catalog_cells = [
        c
        for c in read_ok
        if c["kind_id"] == "contracted:WORK-UNIT-CATALOG.json"
        and c["consumer_id"] == "monitor-renderer"
    ]
    if not catalog_cells:
        print("FAILED:TST-0012-probe2 catalog was not parsed by monitor-renderer")
        return 1
    cat_cell = catalog_cells[0]
    if not cat_cell.get("parse") or not cat_cell.get("field"):
        print(f"FAILED:TST-0012-probe2 catalog cell missing field {cat_cell}")
        return 1
    if cat_cell.get("field_value") in (None, ""):
        print("FAILED:TST-0012-probe2 catalog field read empty")
        return 1

    indexer_ok = [
        c
        for c in read_ok
        if c["consumer_id"] == "manifest-indexer" and c.get("field") == "unit_id"
    ]
    # Indexer READ_OK is expected on this tree (live receipts exist) but is not
    # required if the receipts dir is empty; the catalog cell is the floor.
    if indexer_ok and not indexer_ok[0].get("field_value"):
        print("FAILED:TST-0012-probe2 indexer field read empty")
        return 1

    # Schema-only is not enough: every READ_OK cell must carry a field name.
    for cell in read_ok:
        if not cell.get("field"):
            print(f"FAILED:TST-0012-probe2 READ_OK without field {cell['kind_id']}")
            return 1

    corrupt = M.corrupt_one_byte_fails()
    if not corrupt.get("all_fired"):
        print(f"FAILED:TST-0012-probe2 one-byte mutant silent {corrupt}")
        return 1
    if not corrupt.get("good_state_silent"):
        print("FAILED:TST-0012-probe2 good catalog load failed (control inverted)")
        return 1
    if not corrupt.get("both_states"):
        print("FAILED:TST-0012-probe2 both-states control failed")
        return 1

    if REPORT.is_file():
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        reported = (doc.get("consumer_artifact_matrix") or {}).get("counts") or {}
        if int(reported.get("kinds") or -1) != live["counts"]["kinds"]:
            print(
                "FAILED:TST-0012-probe2 report kinds "
                f"{reported.get('kinds')} != live {live['counts']['kinds']}"
            )
            return 1
        if int(reported.get("read_ok") or 0) < 1:
            print("FAILED:TST-0012-probe2 report has no READ_OK cell")
            return 1
        enc = doc.get("encoding_control") or {}
        if enc.get("crlf_not_misread_as_data") is not True:
            print("FAILED:TST-0012-probe2 encoding_control.crlf_not_misread_as_data false")
            return 1
        if len(enc.get("surfaces") or []) < 2:
            print("FAILED:TST-0012-probe2 encoding surfaces < 2")
            return 1
        if "SUCCESS:TST-0012" not in json.dumps(doc.get("sentinel")):
            print("FAILED:TST-0012-probe2 sentinel missing")
            return 1

    print(
        "read_ok={n} catalog_field={f}={v} indexer_ok={i} "
        "corrupt_fired={cf} good_silent={gs}".format(
            n=len(read_ok),
            f=cat_cell.get("field"),
            v=cat_cell.get("field_value"),
            i=len(indexer_ok),
            cf=corrupt["all_fired"],
            gs=corrupt["good_state_silent"],
        )
    )
    print(
        "SUCCESS:TST-0012-probe2 parse+field-read succeeded; "
        "one-byte corrupt failed loudly"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
