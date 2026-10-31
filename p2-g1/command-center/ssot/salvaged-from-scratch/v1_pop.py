"""V1: independent re-derivation of the BLOCKED/FAILED population and the review-gate split.

Reads ONLY committed blobs (git show HEAD:<path>). Shares no code with the lane's scripts.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def blob_text(rel, rev=None):
    r = subprocess.run(
        ["git", "show", f"{rev or REV}:{rel}"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout if r.returncode == 0 else None


def blob_json(rel, rev=None):
    t = blob_text(rel, rev)
    if t is None:
        return None
    try:
        return json.loads(t)
    except Exception as e:  # noqa: BLE001
        return {"__parse_error__": str(e)}


cat = blob_json("command-center/WORK-UNIT-CATALOG.json")
units = cat["work_units"]
print(f"catalog units at {REV}: {len(units)}")

# --- population: every catalog unit whose receipt (output_path) says BLOCKED or FAILED
pop = []
missing_receipt = []
states = {}
for u in units:
    op = u.get("output_path")
    if not op:
        continue
    rec = blob_json(op)
    if rec is None:
        missing_receipt.append(u["id"])
        continue
    st = str(rec.get("state", "")).upper()
    states[st] = states.get(st, 0) + 1
    if st in ("BLOCKED", "FAILED"):
        pop.append((u, rec))

print(f"state histogram: {states}")
print(f"catalog units whose output_path has NO committed receipt: {len(missing_receipt)}")
print(f"POPULATION (BLOCKED|FAILED via catalog output_path): {len(pop)}")
ids = sorted(u['id'] for u, _ in pop)
print("ids:", ids)

# --- split: cross-vendor required vs any-independent
CROSS = re.compile(r"cross[- ]vendor|cross_vendor|crossvendor", re.I)
VENDORS = re.compile(r"\b(openai|codex|gpt-?5|gemini|google)\b", re.I)


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(o, str):
        yield path, o


rows = []
for u, rec in pop:
    req = str(u.get("reviewer_requirement") or "")
    bo = str(((rec.get("failure") or {}).get("blocked_on")) or "")
    cross_in_req = bool(CROSS.search(req))
    cross_in_bo = bool(CROSS.search(bo))
    # greedy: any cross-vendor token anywhere in the receipt tree
    anywhere = [(p, s) for p, s in walk(rec) if CROSS.search(s)]
    vend_anywhere = [(p, s) for p, s in walk(rec) if VENDORS.search(s)]
    rows.append(
        dict(
            id=u["id"],
            state=rec.get("state"),
            cross_req=cross_in_req,
            cross_bo=cross_in_bo,
            cross_either=cross_in_req or cross_in_bo,
            n_cross_anywhere=len(anywhere),
            n_vendor_anywhere=len(vend_anywhere),
            req=req,
            bo=bo,
            output_path=u.get("output_path"),
        )
    )

cross = [r for r in rows if r["cross_either"]]
anyi = [r for r in rows if not r["cross_either"]]
print(f"\nCROSS-VENDOR-REQUIRED (req or blocked_on carries a cross-vendor clause): {len(cross)}")
print(f"ANY-INDEPENDENT (neither field): {len(anyi)}")
print("any-independent ids:", sorted(r["id"] for r in anyi))
# greedy check on the satisfiable set
print("\n-- greedy scan of the ANY-INDEP set for ANY cross-vendor token anywhere in the receipt --")
for r in anyi:
    print(f"  {r['id']:12s} cross_anywhere={r['n_cross_anywhere']}  vendor_tokens_anywhere={r['n_vendor_anywhere']}")

json.dump(rows, open(Path(__file__).parent / f"v1_rows_{REV.replace('^','C').replace('/','_')}.json", "w", encoding="utf-8"), indent=1)
print("\nwrote rows")
