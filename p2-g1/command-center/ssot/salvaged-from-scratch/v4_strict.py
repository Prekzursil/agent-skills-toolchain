"""V4: STRICT cross-vendor detector that excludes bare vendor names -> tests the auditor's
'ZERO are classified from a bare vendor name' claim. Plus the stale-43 census. Plus reviewer
timestamps on all 10."""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def show(rel, rev="HEAD"):
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=REPO,
                       capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


STRICT = re.compile(
    r"cross[-_ ]?vendor|different\s+vendors?|differently[- ]vendored"
    r"|second\s+vendor|other\s+vendor|non[- ]anthropic"
    r"|two-different-vendor|DIFFERENT vendors",
    re.I,
)
rows = json.load(open(Path(__file__).parent / "v1_rows_HEAD.json", encoding="utf-8"))
hit, miss = [], []
for r in rows:
    if STRICT.search(r["req"]) or STRICT.search(r["bo"]):
        hit.append(r["id"])
    else:
        miss.append(r["id"])
print(f"STRICT (no bare vendor names): {len(hit)} cross / {len(miss)} any-indep")
print("  any-indep:", sorted(miss))
print(f"  CONTROL strict fires on 'openai/gpt-5-codex reviewer'? {bool(STRICT.search('openai/gpt-5-codex reviewer'))} (must be False)")
print(f"  CONTROL strict fires on 'two reviewers from DIFFERENT vendors'? {bool(STRICT.search('two reviewers from DIFFERENT vendors'))} (must be True)")

print("\n########## reviewer timestamps / ids on the 10 satisfiable ##########")
cat = json.loads(show("command-center/WORK-UNIT-CATALOG.json"))
by_id = {u["id"]: u for u in cat["work_units"]}
for uid in sorted(miss):
    rec = json.loads(show(by_id[uid]["output_path"]))
    rv = rec.get("reviewer") or {}
    print(f"  {uid:10s} at={rv.get('reviewed_at')}  id={rv.get('reviewer_id')}  vendor={rv.get('vendor')} len(notes)={len(rv.get('notes') or '')}")

print("\n########## stale '43' census across the WHOLE committed tree ##########")
files = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=REPO,
                       capture_output=True, encoding="utf-8").stdout.split("\n")
pat = re.compile(r"\b43\b")
ctx = re.compile(r"43\s*(units|of\s+4[0-9]|blocked|cross|rail)|(cross[- ]vendor|rail[- ]blocked|independent)[^.\n]{0,80}\b43\b|\b43\b[^.\n]{0,80}(cross[- ]vendor|rail|independent review)", re.I)
hits = []
for f in files:
    if not f or not f.startswith("command-center/"):
        continue
    if not f.endswith((".md", ".json")):
        continue
    t = show(f)
    if not t:
        continue
    for i, line in enumerate(t.split("\n"), 1):
        if ctx.search(line):
            hits.append((f, i, line.strip()[:180]))
print(f"lines matching a 43+cross-vendor/rail context: {len(hits)}")
for f, i, ln in hits:
    print(f"  {f}:{i}  {ln}")
