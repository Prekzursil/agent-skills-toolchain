#!/usr/bin/env python3
"""Named probe 1: merge result equals hand-authored expected file for each fixture triple.

Signal 1 of IMP-0031. Independent of the random-triple property (probe 2).
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

from plugin.three_way_oracle import run_all  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0031.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0031-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0031-probe1 receipt unparseable: {exc}")
        return 1
    if "SUCCESS:IMP-0031" not in text:
        print("FAILED:IMP-0031-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0031-probe1 self-declared {st}")
        return 1

    report = run_all()
    print(json.dumps({k: report[k] for k in ("fixtures", "passed", "failed", "ok")}, sort_keys=True))
    if not report["ok"]:
        print(json.dumps(report["rows"], indent=2)[:4000])
        print("FAILED:IMP-0031-probe1 fixture oracle")
        return 1
    print(
        f"fixtures={report['fixtures']} passed={report['passed']} "
        "byte_or_conflict_oracle=True"
    )
    print("SUCCESS:IMP-0031-probe1 fixture oracle equals hand-authored expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
