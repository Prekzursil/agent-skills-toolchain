#!/usr/bin/env python3
"""Probe 1: field-by-field metadata-vs-built-artifact comparison table.

Re-packs tools/agentspec via setuptools.build_meta.build_sdist (copy, not
in-tree) and compares name/version/entry_points/engines/files to PKG-INFO
and the sdist member list. Also checks the stored receipt table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.package_metadata_contract import (  # noqa: E402
    RULES,
    inspect_live_python,
    live_npm_package_json,
)

ART = REPO / "command-center/receipts/TST-0035.json"
SENTINEL = "SUCCESS:TST-0035"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0035-probe1 {msg}")
    return 1


def _by_field(table: list) -> dict:
    return {row["field"]: row for row in table if isinstance(row, dict)}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0035":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = inspect_live_python(REPO)
    if live is None:
        return fail("tools/agentspec pyproject missing")
    if live["kind"] != "python":
        return fail(f"kind={live['kind']}")
    table = live["comparison_table"]
    if {r["field"] for r in table} != set(RULES):
        return fail(f"fields={[r['field'] for r in table]}")

    stored = doc.get("comparison_table") or doc.get("live", {}).get("comparison_table") or []
    stored_by = _by_field(stored)
    live_by = _by_field(table)
    for field in RULES:
        if field not in stored_by:
            return fail(f"receipt missing field {field}")
        if bool(stored_by[field].get("consistent")) != bool(live_by[field].get("consistent")):
            return fail(
                f"{field} consistent stored={stored_by[field].get('consistent')} "
                f"live={live_by[field].get('consistent')}"
            )
        if stored_by[field].get("declared") != live_by[field].get("declared"):
            return fail(f"{field} declared drifted")
        if stored_by[field].get("built") != live_by[field].get("built"):
            return fail(f"{field} built drifted")

    npm = live_npm_package_json(REPO)
    print(
        json.dumps(
            {
                "probe": "probe1-field-table",
                "unit_id": "TST-0035",
                "artifact": live["artifact"],
                "gate_pass": live["gate_pass"],
                "mismatches": live["mismatches"],
                "npm_package_json_present": npm["present"],
                "rows": [
                    {
                        "field": r["field"],
                        "declared": r["declared"],
                        "built": r["built"],
                        "consistent": r["consistent"],
                    }
                    for r in table
                ],
            },
            sort_keys=True,
        )
    )
    for row in table:
        print(
            f"field {row['field']} consistent={row['consistent']} "
            f"declared={row['declared']!r} built={row['built']!r}"
        )
    print(
        f"SUCCESS:TST-0035-probe1 field-table artifact={live['artifact']} "
        f"gate_pass={live['gate_pass']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
