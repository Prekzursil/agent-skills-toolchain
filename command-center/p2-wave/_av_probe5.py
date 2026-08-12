"""ADVERSARIAL VERIFIER probe 5 -- re-run the two probes whose instruments I had broken.

My probe-4 used `u.get("substrate")` (wrong field: it is `execution_substrate`) and looked for
command-center/P2-BLOCKED-UNITS.json (wrong dir: it is command-center/p2-wave/). Both produced
a false negative. Disclosed, fixed, re-measured here.
"""

from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path

R = Path("C:/Users/Prekzursil/source/ast-integrate")
units = json.loads((R / "command-center/WORK-UNIT-CATALOG.json").read_text("utf-8"))["work_units"]
by = {x["id"]: x for x in units}
ready = json.loads((R / "command-center/READY-UNITS.json").read_text("utf-8"))["ready_units"]

h = collections.Counter(by[i]["execution_substrate"] for i in ready)
print(f"READY={len(ready)}  execution_substrate histogram = {dict(h)}")

rel = "command-center/p2-wave/P2-BLOCKED-UNITS.json"
bp = R / rel
print(f"{rel}: exists={bp.is_file()} worktree_bytes={bp.stat().st_size}")
sha = subprocess.run(
    ["git", "ls-files", "-s", "--", rel], cwd=str(R), capture_output=True, text=True
).stdout.split()[1]
blob = subprocess.run(["git", "cat-file", "-p", sha], cwd=str(R), capture_output=True).stdout
crlf = blob.count(b"\r\n")
print(f"  blob_bytes={len(blob)} CRLF={crlf}")
d = json.loads(blob.decode("utf-8"))
print(f"  keys={sorted(d)}")
for k in ("ready_count", "reviewer_gated_count", "substrate_histogram"):
    print(f"    {k} = {d.get(k)}")

print(f"\nRES-0001 in READY set: {'RES-0001' in ready}")
print(f"IMP-0433 in READY set: {'IMP-0433' in ready}")
meta_ready = [
    i for i in ready
    if by[i]["output_schema"] in (
        "https://json-schema.org/draft/2020-12/schema",
        "command-center/schema/meta/json-schema-draft.json",
        "command-center/schema/_meta/json-schema-2020-12.json",
    )
]
print(f"meta-contract units currently READY: {len(meta_ready)} -> {sorted(meta_ready)}")
print("\nDONE:av-probe5")
