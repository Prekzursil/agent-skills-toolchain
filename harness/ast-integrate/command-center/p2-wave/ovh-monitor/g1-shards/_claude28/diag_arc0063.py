#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PROBE_DIR = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\ARC-0063")
sys.path.insert(0, str(PROBE_DIR))
from estate import S1_EVALUATOR_REL  # noqa: E402
from rollback import RESTORE_COMMAND  # noqa: E402

ART = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\phase3\A9\MIGRATION.json")
doc = json.loads(ART.read_text(encoding="utf-8"))
tests = doc.get("tests")
print("tests type:", type(tests).__name__)
if isinstance(tests, dict):
    rec = tests.get("rollback_rehearsal") or {}
else:
    rec = (doc.get("report") or {}).get("rollback_rehearsal") or doc.get("rollback_rehearsal") or {}
print("recorded:", json.dumps(rec, indent=1)[:1200])
print("expected S1_EVALUATOR_REL:", S1_EVALUATOR_REL)
print("expected RESTORE_COMMAND:", RESTORE_COMMAND)
both = (doc.get("tests") or {}).get("content_preservation_both_directions") if isinstance(tests, dict) else None
print("both:", json.dumps(both, indent=1)[:600] if both else both)
