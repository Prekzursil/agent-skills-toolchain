"""EXTEND: find a Family-H executed workflow whose SCRIPT is still on disk and READ it.

The prior archaeology states Family H entries carry a MECHANICAL classification 'derived
from the run record plus a regex mechanism scan - not a read of the script', marked
UNVERIFIED on every entry, and names the 259 unread scripts as 'the single largest
untapped reservoir'. Family H occupies spine positions 182-253, which is OUTSIDE the
1-160 program window, so harvesting from it cannot collide with any sibling unit's range.
"""

import json
import pathlib
import re

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
reg = json.loads((CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text("utf-8"))
cands = reg["candidates"]
H = [(i + 1, c) for i, c in enumerate(cands) if c["family"] == "H-executed-corpus"]
print(f"Family H entries: {len(H)}  spine positions {H[0][0]}-{H[-1][0]}")

resolvable = []
for pos, c in H:
    prov = c["provenance"]
    # provenance may hold a path; try to extract a real filesystem path
    for m in re.finditer(r"[A-Za-z]:\\[^\s;,'\"]+|[A-Za-z]:/[^\s;,'\"]+", prov):
        p = pathlib.Path(m.group(0).replace("\\", "/"))
        if p.is_file():
            resolvable.append((pos, c, p))
            break

print(f"H entries whose provenance path resolves to a real file on disk: {len(resolvable)}")
for pos, c, p in resolvable[:12]:
    print(f"  {pos:3d} {c['id'][:56]:56s} {p.stat().st_size:7d}B  {p.name}")

if not resolvable:
    print("\nprovenance strings for the first 3 H entries (to see the shape):")
    for pos, c in H[:3]:
        print(f"  {pos}: {c['provenance'][:220]}")
        print(f"      does: {c['does'][:150]}")
        print(f"      mech: {c['mechanisms']}")
        print(f"      evid: {c['evidence'][:200]}")

out = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_h_scan.json"
)
out.write_text(
    json.dumps(
        [
            {"pos": pos, "id": c["id"], "path": str(p), "bytes": p.stat().st_size}
            for pos, c, p in resolvable
        ],
        indent=1,
    ),
    encoding="utf-8",
)
print(f"\nwrote {out}")
