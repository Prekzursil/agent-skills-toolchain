"""CC-0002 premise probe. The row asserts three absences; measure each before building."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def tracked(rel: str) -> bool:
    r = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=str(REPO),
                       capture_output=True)
    return r.returncode == 0


print("=== CC-0002 row asserts: schema ABSENT, receipts/ ABSENT, 0 receipts on disk ===")
sch = REPO / "command-center/schema/receipt.schema.json"
print(f"  receipt.schema.json exists={sch.is_file()} size={sch.stat().st_size if sch.is_file() else 0} tracked={tracked('command-center/schema/receipt.schema.json')}")
rd = REPO / "command-center/receipts"
print(f"  command-center/receipts/ exists={rd.is_dir()}")
if rd.is_dir():
    files = sorted(p.name for p in rd.iterdir())
    print(f"    entries={len(files)} -> {files[:12]}")
    gk = rd / ".gitkeep"
    print(f"    .gitkeep exists={gk.is_file()} tracked={tracked('command-center/receipts/.gitkeep')}")

print()
print("=== does an EMITTER exist? ===")
for cand in ["command-center/p13_emit_receipt.py"]:
    p = REPO / cand
    print(f"  {cand}: exists={p.is_file()} size={p.stat().st_size if p.is_file() else 0}")

print()
print("=== does a VALIDATOR exist? (the thing CC-0002 also demands) ===")
hits = subprocess.run(
    ["git", "grep", "-l", "-i", "-E", "validate.*receipt|receipt.*validat", "--",
     "command-center", "platform", "tools"],
    cwd=str(REPO), capture_output=True, text=True)
names = [h for h in hits.stdout.splitlines() if h.strip()]
print(f"  candidate files mentioning receipt validation: {len(names)}")
for n in names[:25]:
    print(f"    {n}")
print("  NOTE: a file MENTIONING validation is not a validator (use-vs-mention). Checked below.")
for n in names:
    p = REPO / n
    if p.suffix == ".py" and ("__main__" in p.read_text(encoding="utf-8", errors="replace")):
        print(f"    RUNNABLE: {n}")

print()
print("=== the 4 mutants CC-0002 demands, and whether the SCHEMA alone can judge them ===")
print("  m1 missing completion_sentinel        -> schema can judge (required field)")
print("  m2 empty evidence anchor array        -> schema can judge (minItems)")
print("  m3 unit id not present in the catalog -> schema CANNOT judge: cross-reference check")
print("  m4 syntactically unparseable JSON     -> schema CANNOT judge: parse-level check")
print("  => the deliverable is a VALIDATOR (parse + schema + catalog cross-ref), not a schema.")

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
print(f"  catalog unit ids available for the cross-reference: {len(cat['work_units'])}")
print("DONE:cc0002-premise")
