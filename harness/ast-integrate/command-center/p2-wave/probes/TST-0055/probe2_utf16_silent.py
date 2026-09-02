#!/usr/bin/env python3
"""Probe 2: UTF-16-LE must not silently parse as empty.

Derives classifications from live readers BEFORE opening the receipt.
Requires: planted decoder SILENT_EMPTY on UTF-16, catalog REJECT_LOUD on
UTF-16, inventory._load_json SILENT_EMPTY on UTF-16 (swallow control), and
every config/artifact reader not SILENT_EMPTY.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
import schema_check as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0055.json"
SENTINEL = "SUCCESS:TST-0055"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0055-probe2 {msg}")
    return 1


def pick(cells: list[dict], reader_id: str, encoding: str) -> dict:
    for cell in cells:
        if cell["reader_id"] == reader_id and cell["encoding"] == encoding:
            return cell
    raise KeyError(f"{reader_id}/{encoding}")


def main() -> int:
    # Derive first. Do not load the artifact until these numbers exist.
    live = M.run_matrix()
    cells = live["matrix"]
    plant_utf16 = pick(cells, "planted.silent_empty_decoder", "utf-16-le")
    plant_utf8 = pick(cells, "planted.silent_empty_decoder", "utf-8")
    catalog_utf16 = pick(cells, "catalog.load", "utf-16-le")
    inventory_utf16 = pick(cells, "inventory._load_json", "utf-16-le")
    inventory_utf8 = pick(cells, "inventory._load_json", "utf-8")

    if plant_utf16["classification"] != "SILENT_EMPTY":
        return fail("planted decoder did not SILENT_EMPTY on utf-16-le")
    if plant_utf8["classification"] != "HANDLE":
        return fail("planted decoder did not HANDLE utf-8")
    if catalog_utf16["classification"] != "REJECT_LOUD":
        return fail(
            f"catalog.load utf-16-le was {catalog_utf16['classification']} not REJECT_LOUD"
        )
    if catalog_utf16.get("silent_empty"):
        return fail("catalog.load utf-16-le silent_empty")
    exc = catalog_utf16.get("exception_text") or ""
    if not exc:
        return fail("catalog.load utf-16-le missing exception text")
    if inventory_utf16["classification"] != "SILENT_EMPTY":
        return fail("inventory utf-16-le did not swallow to SILENT_EMPTY")
    if inventory_utf8["classification"] != "HANDLE":
        return fail("inventory utf-8 did not HANDLE planted token")
    if not live["tests"]["test_utf16_input_does_not_silently_parse_as_empty"]:
        return fail("required utf-16 silent-empty test false")

    required_utf16 = [
        c
        for c in cells
        if c["in_required_tests"] and c["encoding"] == "utf-16-le"
    ]
    silent_req = [c["reader_id"] for c in required_utf16 if c["classification"] == "SILENT_EMPTY"]
    if silent_req:
        return fail(f"required readers silently empty on utf-16: {silent_req}")
    if catalog_utf16["nul_count"] <= 0:
        return fail("utf-16-le fixture was not NUL-dense")

    shells = {
        "bash": shutil.which("bash"),
        "pwsh": shutil.which("pwsh"),
        "powershell": shutil.which("powershell"),
    }

    # Now open the artifact and compare.
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    def fp(cell: dict) -> tuple:
        return (
            cell.get("classification"),
            cell.get("exception_type"),
            cell.get("exception_text"),
            cell.get("silent_empty"),
        )

    art_cells = S.matrix_from_artifact(doc)
    for reader_id, encoding in (
        ("catalog.load", "utf-16-le"),
        ("planted.silent_empty_decoder", "utf-16-le"),
        ("inventory._load_json", "utf-16-le"),
        ("catalog.load", "utf-8"),
    ):
        live_cell = pick(cells, reader_id, encoding)
        art_cell = pick(art_cells, reader_id, encoding)
        if fp(live_cell) != fp(art_cell):
            return fail(f"artifact drift {reader_id}/{encoding}")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_utf16_input_does_not_silently_parse_as_empty")
    if not row or row.get("result") != "PASS":
        return fail("artifact UTF-16 test not PASS")

    print(
        json.dumps(
            {
                "probe": "probe2-utf16-silent",
                "unit_id": "TST-0055",
                "pass": True,
                "plant_utf16": plant_utf16["classification"],
                "catalog_utf16": catalog_utf16["classification"],
                "catalog_exception": catalog_utf16.get("exception_text"),
                "inventory_utf16": inventory_utf16["classification"],
                "heartbeat_utf16": inventory_utf16["classification"],
                "required_utf16_not_silent": not silent_req,
                "shells": shells,
                "other_shell_present": bool(shells["pwsh"] or shells["powershell"]),
            },
            sort_keys=True,
        )
    )
    print(
        f"plant={plant_utf16['classification']} catalog={catalog_utf16['classification']} "
        f"inventory={inventory_utf16['classification']} pwsh={shells['pwsh']}"
    )
    print("SUCCESS:TST-0055-probe2 UTF-16 does not silently parse as empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
