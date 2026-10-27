"""CC-0002 gap probe: run the EXISTING validator against the 4 mutants the row names.

Prior art first. `platform/lib/receipt_schema_gate.py` is a runnable two-layer validator
(schema + the 12-condition predicate) with a CLI. Building a second one would duplicate it, so
measure which of CC-0002's four mutants it already rejects and build ONLY the gap.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "platform/lib/receipt_schema_gate.py"
TMP = REPO / "command-center/p2-wave/_r2_tmp"
TMP.mkdir(parents=True, exist_ok=True)

GOLDEN = REPO / "command-center/receipts/TST-0334.json"
golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
print(
    f"golden = {GOLDEN.relative_to(REPO).as_posix()} ({GOLDEN.stat().st_size} B) "
    f"unit_id={golden.get('unit_id')!r} state={golden.get('state')!r}"
)


def run_gate(path: Path, schema_only: bool) -> tuple[int, str]:
    cmd = [sys.executable, str(GATE), str(path), "--repo-root", str(REPO)]
    if schema_only:
        cmd.append("--schema-only")
    r = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


mutants: dict[str, object] = {}
m = json.loads(json.dumps(golden))
m.pop("sentinel", None)
mutants["m1-missing-sentinel"] = m
m = json.loads(json.dumps(golden))
m["evidence"] = []
mutants["m2-empty-evidence"] = m
m = json.loads(json.dumps(golden))
m["unit_id"] = "ZZZ-9999"
if isinstance(m.get("sentinel"), str):
    m["sentinel"] = m["sentinel"].replace(str(golden.get("unit_id")), "ZZZ-9999")
mutants["m3-unit-id-not-in-catalog"] = m

paths = {"golden": GOLDEN}
for name, doc in mutants.items():
    p = TMP / f"cc0002-{name}.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    paths[name] = p
p4 = TMP / "cc0002-m4-unparseable.json"
p4.write_text(
    '{"unit_id": "TST-0334", "state": ', encoding="utf-8"
)  # truncated on purpose
paths["m4-unparseable"] = p4

print()
print(f"{'fixture':<28} {'schema-only':>12} {'full-gate':>10}  first line")
print("-" * 110)
for name, p in paths.items():
    rc_s, out_s = run_gate(p, True)
    rc_f, out_f = run_gate(p, False)
    print(
        f"{name:<28} {('rc=' + str(rc_s)):>12} {('rc=' + str(rc_f)):>10}  {out_s.splitlines()[0][:60]}"
    )

print()
print(
    "=== the catalog cross-reference: does ANY existing tool check unit_id membership? ==="
)
src = GATE.read_text(encoding="utf-8")
for token in ["WORK-UNIT-CATALOG", "work_units", "catalog"]:
    print(f"  {token!r} in receipt_schema_gate.py: {token in src}")
cat = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
ids = {u["id"] for u in cat["work_units"]}
print(f"  catalog ids: {len(ids)}  'ZZZ-9999' in catalog: {'ZZZ-9999' in ids}")
print("DONE:cc0002-gap")
