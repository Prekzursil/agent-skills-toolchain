"""V3: broadened cross-vendor detector + reviewer-block inspection, committed blobs only."""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def blob_json(rel, rev=None):
    r = subprocess.run(
        ["git", "show", f"{rev or REV}:{rel}"],
        cwd=REPO, capture_output=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


# BROAD: literal cross-vendor OR "different vendors" OR "non-anthropic" OR a named rival vendor
BROAD = re.compile(
    r"cross[-_ ]?vendor"
    r"|different\s+vendors?"
    r"|differently[- ]vendored"
    r"|second\s+vendor"
    r"|other\s+vendor"
    r"|non[- ]anthropic"
    r"|\bopenai\b|\bcodex\b|\bgpt-?5\b|\bgemini\b",
    re.I,
)
# CONTROL: a detector that must NOT fire on a pure same-vendor requirement
CTRL_TEXT = "one fresh-context Claude reviewer who has not seen this unit's transcript"

cat = blob_json("command-center/WORK-UNIT-CATALOG.json")
by_id = {u["id"]: u for u in cat["work_units"]}

rows = json.load(open(Path(__file__).parent / "v1_rows_HEAD.json", encoding="utf-8"))
n_req = n_bo = n_either = 0
either_ids, req_only, bo_only = [], [], []
for r in rows:
    a = bool(BROAD.search(r["req"]))
    b = bool(BROAD.search(r["bo"]))
    n_req += a
    n_bo += b
    if a or b:
        n_either += 1
        either_ids.append(r["id"])
        if a and not b:
            req_only.append(r["id"])
        if b and not a:
            bo_only.append(r["id"])
print(f"BROAD detector: req={n_req}  blocked_on={n_bo}  either={n_either}  (population {len(rows)})")
print(f"  only-in-blocked_on: {bo_only}")
print(f"  NOT matched (=> any-independent): {sorted(r['id'] for r in rows if r['id'] not in either_ids)}")
print(f"CONTROL: BROAD fires on the AUD same-vendor requirement text? {bool(BROAD.search(CTRL_TEXT))} (must be False)")
print(f"CONTROL: BROAD fires on 'two reviewers from DIFFERENT vendors'? {bool(BROAD.search('two reviewers from DIFFERENT vendors'))} (must be True)")

print("\n\n########## REVIEWER BLOCKS on the 10 satisfiable ##########")
SAT10 = sorted(r["id"] for r in rows if r["id"] not in either_ids)
for uid in SAT10:
    rec = blob_json(by_id[uid]["output_path"])
    rv = (rec or {}).get("reviewer") or {}
    notes = rv.get("notes") or ""
    print("\n" + "=" * 90)
    print(uid, "->", by_id[uid]["output_path"])
    print("  produced_by:", json.dumps(rec.get("produced_by"))[:200])
    print("  reviewer keys:", sorted(rv.keys()))
    for k in sorted(rv.keys()):
        if k == "notes":
            continue
        print(f"    {k} = {json.dumps(rv[k])[:300]}")
    print(f"  notes len={len(notes)}")
    print("  notes[:600]:", notes[:600].replace("\n", " | "))
