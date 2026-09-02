#!/usr/bin/env python3
"""Probe 2: manifest diff + process-table observation (evidence B).

Adversarial bypasses the import scan: a runtime vendored rather than declared,
and a runtime spawned rather than imported, must still be named.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = HERE / "probe2-manifest-and-process.raw.json"


def main() -> int:
    b = S.evidence_b()
    doc = {
        "probe": "probe2-manifest-and-process",
        "unit_id": "WFA-0056",
        "evidence_b": b,
        "bypass_vendored_caught": bool(b.get("vendored", {}).get("pass")),
        "bypass_spawned_caught": bool(b.get("process_table", {}).get("pass")),
        "pass": bool(b.get("pass")),
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not doc["pass"]:
        print("FAILED:WFA-0056-probe2 manifest/process/vendored")
        print(json.dumps(doc, indent=2, sort_keys=True)[:4000])
        return 1
    print(
        "manifest_seven="
        + str(all(r["pass"] for r in b["manifest_diff"]))
        + " vendored="
        + str(b["vendored"]["pass"])
        + " spawn_source="
        + str(b["subprocess_source"]["pass"])
        + " process_table="
        + str(b["process_table"]["pass"])
        + " named_on_process="
        + ",".join(b["process_table"]["named_planes"])
    )
    print("SUCCESS:WFA-0056-probe2 manifest-diff process-table vendored-bypass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
