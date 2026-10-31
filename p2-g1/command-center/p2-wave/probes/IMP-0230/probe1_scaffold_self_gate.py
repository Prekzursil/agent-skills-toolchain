"""IMP-0230 probe 1 (source): scaffold output passes its own gate (self-application control).

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0230/probe1_scaffold_self_gate.py
Exit 0 iff the scaffold registers unmodified (violations=0), survives a JSON
round-trip, stays disk-unmodified across validation, and its declared hermetic
smoke passes. A tool that commits the defect class it exists to prevent has
happened three times on this estate; this is the control against that class.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W))

from tools.blueprint_contract.contract import (  # noqa: E402
    register_blueprint,
    run_declared_smoke,
    validate_blueprint,
)
from tools.blueprint_contract.scaffold import (  # noqa: E402
    dump_blueprint,
    emit_scaffold,
    scaffold_blueprint,
)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        failures.append(f"{name}: {detail}" if detail else name)


# 1. In-memory scaffold registers with zero violations.
doc = scaffold_blueprint()
gate = register_blueprint(doc)
check("registers_unmodified", gate.ok and gate.violations == [],
      f"ok={gate.ok} violations={gate.violations}")

# 2. JSON round-trip of the scaffold still registers (sort_keys serialization
#    must not be load-bearing for the gate).
roundtrip = json.loads(dump_blueprint(doc))
gate2 = validate_blueprint(roundtrip)
check("json_round_trip", gate2.ok and gate2.violations == [],
      f"ok={gate2.ok} violations={gate2.violations}")

# 3. The declared hermetic smoke test passes.
smoke_ok, failed = run_declared_smoke(doc)
check("smoke_ok", smoke_ok, f"failed={failed}")

# 4. Emitting to disk and re-validating from disk: bytes unmodified by the
#    gate, file re-registers, and the sha256 over CRLF-normalized bytes is
#    recorded (matching the manifest digest rule).
with tempfile.TemporaryDirectory() as td:
    path = emit_scaffold(td)
    before = path.read_bytes()
    doc_disk = json.loads(path.read_text(encoding="utf-8"))
    gate3 = register_blueprint(doc_disk)
    after = path.read_bytes()
    check("disk_unmodified", before == after)
    check("disk_copy_registers", gate3.ok and gate3.violations == [],
          f"ok={gate3.ok} violations={gate3.violations}")
    normalized = before.replace(b"\r\n", b"\n")
    scaffold_sha = hashlib.sha256(normalized).hexdigest()

out = {
    "disk_unmodified": "disk_unmodified" not in failures and before == after,
    "json_round_trip": "json_round_trip" not in failures,
    "pass": not failures,
    "probe": "probe1-scaffold-self-gate",
    "registered_unmodified": "registers_unmodified" not in failures,
    "scaffold_sha256": scaffold_sha,
    "smoke_ok": smoke_ok,
    "unit_id": "IMP-0230",
    "violation_count": len(gate.violations) + len(gate2.violations) + len(gate3.violations),
}
print("RESULT:" + json.dumps(out, sort_keys=True))
if failures:
    for f in failures:
        print(f"  FAIL {f}")
    print(f"FAILED:IMP-0230-probe1 {len(failures)} self-gate assertion(s) failed")
    raise SystemExit(1)
print("SUCCESS:IMP-0230-probe1 scaffold output passes its own gate unmodified")
