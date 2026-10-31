#!/usr/bin/env python3
"""IMP-0160 probe1: workflows/rtv-pdr.js imports through the Claude saved
workflow adapter and validate_workflow is clean; the adapter fan-out width
equals an independently re-derived width from the source text."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for p in ("tools/agentspec", "tools/import-adapters"):
    sys.path.insert(0, str(REPO / p))

from claude_saved_workflow import import_path  # noqa: E402
from agentspec.validate import validate_workflow, violation_ids  # noqa: E402

SRC = REPO / "workflows" / "rtv-pdr.js"


def main() -> int:
    if not SRC.is_file():
        print("FAILED:IMP-0160-probe1 workflows/rtv-pdr.js missing")
        return 1
    src = SRC.read_text(encoding="utf-8")

    # adapter width vs independent re-derivation from the JS text
    res = import_path(SRC)
    adapter_width = (res.fanout_widths or [0])[0]
    m = re.search(r"default\s+(\d+)", src)
    indep_width = int(m.group(1)) if m else 0
    widths_agree = adapter_width > 0 and adapter_width == indep_width

    wf = res.workflow
    viols = violation_ids(validate_workflow(wf))
    imported_ok = wf is not None and bool(getattr(wf, "units", ()))
    validate_ok = not viols

    # the imported workflow carries the unit set the adapter materialized
    unit_ids = [u.id for u in getattr(wf, "units", ())]

    result = {
        "unit_id": "IMP-0160",
        "probe": "probe1-roundtrip",
        "source": "workflows/rtv-pdr.js",
        "imported": imported_ok,
        "adapter_fanout_width": adapter_width,
        "independent_fanout_width": indep_width,
        "widths_agree": widths_agree,
        "validated": validate_ok,
        "violations": viols,
        "unit_ids": unit_ids,
        "pass": imported_ok and widths_agree and validate_ok,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0160-probe1 rtv-pdr.js import+validate clean; fan-out width preserved"
            if result["pass"] else
            "FAILED:IMP-0160-probe1 import/validate contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
