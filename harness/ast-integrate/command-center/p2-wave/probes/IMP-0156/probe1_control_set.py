#!/usr/bin/env python3
"""Named probe 1: 20-licence control set normalises exactly; no silent permissive default.

Signal is a computed equality (matched == 20), not a presence check. A second
signal on a different field: licence-less / 'permissive' / unrecognised-blob
fixtures stay UNKNOWN and are not coerced to MIT/Apache/BSD.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import evaluate_control_set, evaluate_silent_default  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0156.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0156-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0156":
        print("FAILED:IMP-0156-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0156" not in text:
        print("FAILED:IMP-0156-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0156-p1-") as tmp:
        root = Path(tmp)
        control = evaluate_control_set(root / "control")
        silent = evaluate_silent_default(root / "silent")

    payload = {
        "probe": "probe1-control-set",
        "unit_id": "IMP-0156",
        "matched": control["matched"],
        "total": control["total"],
        "control_pass": control["pass"],
        "silent_default_pass": silent["pass"],
        "misses": [r for r in control["rows"] if not r["match"]],
        "silent_failures": [r for r in silent["rows"] if not r["match"]],
        "pass": bool(control["pass"] and silent["pass"] and control["matched"] == 20),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0156-probe1 control-set or silent-default")
        return 1
    print(
        f"matched={control['matched']}/20 silent_default_pass={silent['pass']}"
    )
    print("SUCCESS:IMP-0156-probe1 20-licence control set and no silent permissive default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
