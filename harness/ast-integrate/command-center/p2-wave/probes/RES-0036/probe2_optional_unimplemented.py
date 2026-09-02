#!/usr/bin/env python3
"""Probe 2: optional-and-unimplemented control + claimed vs observed split.

Catalog control: at least one capability must be marked optional-and-unimplemented.
Evidence requirement: claimed client support is separated from observed support.

Also checks that emptying the unimplemented list would fail (in-memory mutant),
so the control is not silent-in-both-states.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
ARTIFACT = REPO / "command-center" / "research" / "RES-0036.json"
TS = PROBE / "fixtures" / "clients" / "typescript-sdk.constants.ts"
PY_EX = PROBE / "fixtures" / "clients" / "python-sdk._types.excerpt.txt"
PY_VER = PROBE / "fixtures" / "clients" / "python-sdk.mcp_types.version.py"


def unimplemented_rows(doc: dict) -> list[dict]:
    rows = []
    for item in doc.get("optional_and_unimplemented") or []:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def control_ok(rows: list[dict], cells: list[dict]) -> tuple[bool, str]:
    if not rows:
        return False, "no optional_and_unimplemented rows"
    cell_idx = {
        (c.get("capability"), c.get("spec_revision_id")): c.get("presence")
        for c in cells
        if isinstance(c, dict)
    }
    for row in rows:
        cap = row.get("capability")
        rid = row.get("spec_revision_id")
        presence = cell_idx.get((cap, rid))
        if presence not in {"optional", "deprecated-optional"}:
            return False, f"{cap}@{rid} is {presence}, not optional"
        claimed = row.get("claimed")
        observed = row.get("observed")
        if claimed is None or observed is None or claimed == observed:
            return False, f"{cap}@{rid} claimed/observed not separated"
        if observed not in {"unimplemented", "types-only", "not-negotiated-by-default"}:
            return False, f"{cap}@{rid} observed={observed}"
    return True, "ok"


def main() -> int:
    if not ARTIFACT.is_file():
        print("FAILED:RES-0036-probe2 artifact missing")
        return 1
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cells = (((doc.get("matrix") or {}).get("cells")) or [])
    rows = unimplemented_rows(doc)
    ok, why = control_ok(rows, cells)
    if not ok:
        print(f"FAILED:RES-0036-probe2 control: {why}")
        return 1

    mutant = dict(doc)
    mutant["optional_and_unimplemented"] = []
    mok, _ = control_ok(unimplemented_rows(mutant), cells)
    if mok:
        print("FAILED:RES-0036-probe2 mutant with empty unimplemented list still passed")
        return 1

    ts = TS.read_text(encoding="utf-8")
    py_ex = PY_EX.read_text(encoding="utf-8")
    py_ver = PY_VER.read_text(encoding="utf-8")
    if "no SDK runtime" not in ts:
        print("FAILED:RES-0036-probe2 typescript fixture lost 'no SDK runtime'")
        return 1
    if 'LATEST_PROTOCOL_VERSION = "2025-11-25"' not in ts.replace("'", '"') and "LATEST_PROTOCOL_VERSION = '2025-11-25'" not in ts:
        print("FAILED:RES-0036-probe2 typescript fixture lost LATEST_PROTOCOL_VERSION")
        return 1
    if "DEFAULT_NEGOTIATED_PROTOCOL_VERSION = '2025-03-26'" not in ts:
        print("FAILED:RES-0036-probe2 typescript fixture lost DEFAULT_NEGOTIATED_PROTOCOL_VERSION")
        return 1
    if "2024-10-07" not in ts:
        print("FAILED:RES-0036-probe2 typescript fixture lost claimed 2024-10-07")
        return 1
    if 'DEFAULT_NEGOTIATED_VERSION: Final[str] = "2025-03-26"' not in py_ex:
        print("FAILED:RES-0036-probe2 python excerpt lost DEFAULT_NEGOTIATED_VERSION")
        return 1
    if "deliberately excluded (types-only)" not in py_ex:
        print("FAILED:RES-0036-probe2 python excerpt lost types-only exclusion")
        return 1
    if '"2026-07-28"' not in py_ver or "LATEST_PROTOCOL_VERSION" not in py_ver:
        print("FAILED:RES-0036-probe2 python version registry lost 2026-07-28 latest")
        return 1

    clients = doc.get("clients") or []
    separated = 0
    for client in clients:
        if not isinstance(client, dict):
            continue
        claimed = client.get("claimed") or {}
        observed = client.get("observed") or {}
        if claimed.get("protocol_versions") != observed.get("protocol_versions"):
            separated += 1
        if claimed.get("latest") != observed.get("default_negotiated"):
            separated += 1
    if separated < 1:
        print("FAILED:RES-0036-probe2 claimed vs observed not separated")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-optional-unimplemented",
                "unit_id": "RES-0036",
                "unimplemented_rows": len(rows),
                "mutant_empty_list_fails": True,
                "claimed_vs_observed_separated": True,
                "control": why,
            },
            indent=2,
        )
    )
    print("SUCCESS:RES-0036-probe2 optional-and-unimplemented control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
