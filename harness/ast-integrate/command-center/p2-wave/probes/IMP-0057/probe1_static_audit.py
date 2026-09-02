#!/usr/bin/env python3
"""IMP-0057 probe 1: static audit of outbound calls + negative control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
LIB = REPO / "tools" / "lib"
for p in (PLUGIN, LIB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import static_audit as sa  # noqa: E402

MUTANT = "import urllib.request\nurllib.request.urlopen('http://203.0.113.1/x')\n"


def main() -> int:
    findings = sa.audit_tree([PLUGIN, LIB])
    files = sa.iter_production_files([PLUGIN, LIB])
    mutant_hits = sa.audit_snippet(MUTANT, rel="neg-control.py")
    ok = (not findings) and bool(files) and bool(mutant_hits)
    doc = {
        "probe": "probe1-static-audit",
        "unit_id": "IMP-0057",
        "production_files": len(files),
        "findings": findings,
        "negative_control_hits": mutant_hits,
        "pass": ok,
    }
    print(json.dumps(doc, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0057-probe1 static audit")
        return 1
    print("SUCCESS:IMP-0057-probe1 static audit zero outbound calls; mutant detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
