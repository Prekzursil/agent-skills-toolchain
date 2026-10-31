"""Independent DoD re-score for the INTEGRATE stage.

Does NOT read any round's prose verdict. Reads the artifact and counts, so a claim like
"unique-content measured per clone" is scored against how many rows actually carry a
measurement rather than against a sentence saying they do.
"""

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
pc = json.loads(
    (ROOT / "command-center/ssot/population-classified.json").read_text(
        encoding="utf-8"
    )
)
rows = pc["rows"]
assert len(rows) == pc["population"], "wrong collection"
print(f"CONTROL rows={len(rows)} == population={pc['population']}")

print("\n-- classification --")
print("  kind:", dict(Counter(r["kind"] for r in rows)))
print("  signals_agree:", dict(Counter(str(r["signals_agree"]) for r in rows)))

print("\n-- unique content: how many rows carry an actual measurement --")
for f in ("dirty_files", "staged_files", "unpushed_commits"):
    measured = [r for r in rows if isinstance(r.get(f), int)]
    print(
        f"  {f:18s} measured={len(measured):3d}  unmeasured(None)={len(rows) - len(measured)}"
    )

print("\n-- the rows git CANNOT measure, named --")
for r in rows:
    if not isinstance(r.get("dirty_files"), int):
        print(f"  dirty unmeasurable: kind={r['kind']:18s} {r['path']}")
for r in rows:
    if not isinstance(r.get("unpushed_commits"), int):
        print(f"  unpushed unmeasurable: has_remote={r['has_remote']} {r['path']}")

print("\n-- inbound references --")
ie = [r for r in rows if r.get("inbound_exec")]
print(f"  rows with inbound_exec truthy: {len(ie)}")
for r in ie:
    print(f"    {r['path']}  intra_repo={r.get('inbound_exec_intra_repo')}")
print(f"  referenced_by_exec_config list: {len(pc['referenced_by_exec_config'])}")
print(f"  retire_candidates: {len(pc['retire_candidates'])}")
print(f"  no_remote: {len(pc['no_remote'])}")

print("\n-- nothing deleted: do the named source checkouts still exist --")
probe = [
    "C:/Users/Prekzursil/source/agent-skills-toolchain",
    "C:/Users/Prekzursil/source/ast-integrate",
    "C:/Users/Prekzursil/work/agent-skills-toolchain-re",
    "C:/Users/Prekzursil/source/_advver_M14/scratch",
    "D:/wt-salvage-probe",
    "C:/Users/Prekzursil/nonexistent-control-path",  # fabricated: must read False
]
for p in probe:
    print(f"  exists={pathlib.Path(p).exists()!s:5s} {p}")
