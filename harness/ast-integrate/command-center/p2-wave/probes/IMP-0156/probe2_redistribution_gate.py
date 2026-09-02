#!/usr/bin/env python3
"""Named probe 2: UNKNOWN blocks redistribution; a permissive twin passes.

Mechanically different from probe 1 (which scores SPDX equality). This probe
calls the live redistribution_gate API on two candidate trees that differ only
by a MIT LICENSE file.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import evaluate_redistribution_gate  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0156.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0156-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0156":
        print("FAILED:IMP-0156-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0156" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0156-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0156-p2-") as tmp:
        result = evaluate_redistribution_gate(Path(tmp))

    payload = {
        "probe": "probe2-redistribution-gate",
        "unit_id": "IMP-0156",
        "unknown_spdx": result["unknown"]["record"]["spdx_id"],
        "unknown_allowed": result["unknown"]["gate"]["allowed"],
        "unknown_reason": result["unknown"]["gate"]["reason"],
        "twin_spdx": result["permissive_twin"]["record"]["spdx_id"],
        "twin_allowed": result["permissive_twin"]["gate"]["allowed"],
        "twin_reason": result["permissive_twin"]["gate"]["reason"],
        "pass": bool(result["pass"]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0156-probe2 redistribution gate both-states")
        return 1
    print(
        f"unknown_allowed={payload['unknown_allowed']} "
        f"twin_allowed={payload['twin_allowed']} "
        f"reason={payload['unknown_reason']}"
    )
    print("SUCCESS:IMP-0156-probe2 UNKNOWN blocks redistribution; MIT twin passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
