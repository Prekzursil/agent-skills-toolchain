#!/usr/bin/env python3
"""CC-0006 Probe 1: live scan of command-center verification prose roots."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
sys.path.insert(0, str(PROBE))

import wrong_recipe_gate as gate  # noqa: E402

OUT_JSON = PROBE / "probe1-live-scan.json"
OUT_RAW = PROBE / "probe1-live-scan.raw.txt"

# Catalog inputs + the corrected recipe table the gate must stay silent on.
ROOTS = [
    "command-center/RELEASE-CHECKLIST.md",
    "command-center/RUNBOOK.md",
    "command-center/ROLLBACK-MANIFEST.md",
    "command-center/PROGRAM-CHARTER.md",
    "rules/common/windows-shell.md",
]


def main() -> int:
    report = gate.scan(ROOTS, repo=REPO, excludes=gate.DEFAULT_EXCLUDES)
    payload = {
        "unit": "CC-0006",
        "probe": "probe1-live-scan",
        "roots": ROOTS,
        "ok": report.ok_clean,
        "report": report.to_dict(),
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    OUT_JSON.write_text(text, encoding="utf-8")
    raw = (
        f"probe1-live-scan ok={report.ok_clean} files={report.files_scanned} "
        f"prescriptive={len(report.prescriptive)} documentary={len(report.documentary)} "
        f"hit_count={report.hit_count}\n"
    )
    for f in report.prescriptive:
        raw += f"PRESCRIPTIVE {f.file_line} {f.excerpt}\n"
    for f in report.documentary:
        raw += f"DOCUMENTARY {f.file_line} {f.excerpt}\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if report.ok_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
