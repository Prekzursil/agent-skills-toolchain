#!/usr/bin/env python3
"""Probe 1: CouncilSpec schema + named-preset set-difference coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from validate import validate_all  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0293.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0293-probe1 {msg}")
    return 1


def main() -> int:
    report = validate_all()
    print(json.dumps({k: report[k] for k in report if k != "rows"}, sort_keys=True))
    if report["n_presets"] != 64:
        return fail(f"preset count {report['n_presets']}")
    if report["n_schema_ok"] != 64:
        sample = report["invalid_ids"][:5]
        detail = []
        for row in report["rows"]:
            if not row["schema_ok"]:
                detail.append(f"{row['id']}:{row['errors'][:2]}")
            if len(detail) >= 3:
                break
        return fail(f"schema invalid {sample} {detail}")
    if report["named_missing"]:
        return fail(f"named set-difference missing {report['named_missing']}")
    if not report["negative_control"]["fired"]:
        return fail("schema negative control did not fire")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != "TST-0293":
            return fail("receipt unit_id")
        if "SUCCESS:TST-0293" not in json.dumps(doc):
            return fail("sentinel-absent")
        cov = (doc.get("named_coverage") or {}).get("missing") or []
        if cov:
            return fail(f"receipt named missing {cov}")
    print("SUCCESS:TST-0293-probe1 schema and named-preset set difference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
