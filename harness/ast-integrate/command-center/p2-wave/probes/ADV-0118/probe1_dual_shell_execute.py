#!/usr/bin/env python3
"""Probe 1: execute each construction × payload in GNU bash and live pwsh 7."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

WORK = HERE / "_work" / "probe1"


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    matrix = E.run_matrix(WORK)
    summary = E.summarize(matrix)
    compact = E.compact_cells(matrix["cells"])
    out = {
        "probe": "probe1-dual-shell-execute",
        "unit_id": E.UNIT,
        "n_cells": matrix["n_cells"],
        "shells": matrix["shells"],
        "windows_clip_control": matrix["windows_clip_control"],
        "counts": summary["counts"],
        "overall_verdict": summary["overall_verdict"],
        "control_ascii_ok": summary["control_ascii_ok"],
        "tests": summary["tests"],
        "targets": summary["targets"],
        "cells": compact,
        "pass": all(t["result"] == "PASS" for t in summary["tests"]),
    }
    (WORK / "probe1.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if not out["pass"]:
        print("FAILED:ADV-0118-probe1 control or long-payload detector did not pass")
        return 1
    print("SUCCESS:ADV-0118-probe1 dual-shell execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
