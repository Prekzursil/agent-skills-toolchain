"""ADVERSARIAL VERIFIER probe 4 -- check the AUDIT's remaining PASSes and my own claims.

Q12. DoD4: does P2-BLOCKED-UNITS.json exist, and does my own substrate histogram +
     reviewer-gate census match the audit's numbers?
Q13. Is WFA-0001 -- the single `delivered`, and the self-test's CONTROL_GOOD -- really
     state-less, and is its content a real schema pack or a shell?
Q14. Did receipt.schema.json pre-exist the builder's first commit (audit claim)?
Q15. Fairness check on MY OWN blast-radius claim: for each meta-declaring unit, is the
     output_path a SCHEMA (meta-schema is type-appropriate) or a RECEIPT (category error)?
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CAT = REPO / "command-center/WORK-UNIT-CATALOG.json"
units = json.loads(CAT.read_text(encoding="utf-8"))["work_units"]
by_id = {u["id"]: u for u in units}
ready = json.loads((REPO / "command-center/READY-UNITS.json").read_text("utf-8"))["ready_units"]


def git(*a: str, check=True):
    return subprocess.run(["git", *a], cwd=str(REPO), capture_output=True, text=True, check=check)


print("=== Q12: DoD4 blocker census, my own count ===")
bp = REPO / "command-center/P2-BLOCKED-UNITS.json"
print(f"P2-BLOCKED-UNITS.json exists={bp.is_file()} size={bp.stat().st_size if bp.is_file() else 0}")
hist: dict[str, int] = {}
rev = 0
for uid in ready:
    u = by_id[uid]
    s = str(u.get("substrate"))
    hist[s] = hist.get(s, 0) + 1
    r = u.get("reviewer_requirement")
    if r not in (None, "", [], {}):
        rev += 1
print(f"READY={len(ready)}  substrate histogram={hist}")
print(f"READY units carrying a non-empty reviewer_requirement: {rev}/{len(ready)}")
if bp.is_file():
    d = json.loads(bp.read_text("utf-8"))
    print(f"artifact top-level keys: {sorted(d)[:12]}")
    for k in ("ready_count", "reviewer_gated_count", "substrate_histogram"):
        if k in d:
            print(f"  artifact.{k} = {d[k]}")

print("\n=== Q13: WFA-0001, the single `delivered` ===")
w = by_id["WFA-0001"]
p = REPO / w["output_path"]
raw = p.read_bytes()
doc = json.loads(raw.decode("utf-8"))
print(f"path={w['output_path']} bytes={len(raw)} top-level-keys={sorted(doc)[:12]}")
print(f"has a `state` field: {'state' in doc}   value={doc.get('state')!r}")
print(f"declared output_schema: {w['output_schema']}")

print("\n=== Q14: did receipt.schema.json pre-exist commit 03e565ea? ===")
r = git("cat-file", "-s", "03e565ea~1:command-center/schema/receipt.schema.json", check=False)
print(f"  size at 03e565ea~1: {r.stdout.strip() or r.stderr.strip()}")
r2 = git("log", "--diff-filter=A", "--format=%h %ad %s", "--date=short", "--",
         "command-center/schema/receipt.schema.json", check=False)
print(f"  add-commit: {r2.stdout.strip()[:160]}")

print("\n=== Q15: fairness -- is the meta-schema type-appropriate for each meta unit? ===")
import importlib.util, sys  # noqa: E402
sp = REPO / "platform/lib/schema_resolver.py"
spec = importlib.util.spec_from_file_location("schema_resolver", sp)
sr = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(sp.parent))
sys.modules["schema_resolver"] = sr
spec.loader.exec_module(sr)

appropriate, category_error = [], []
for u in units:
    d = u.get("output_schema")
    try:
        res = sr.resolve(d)
    except Exception:  # noqa: BLE001
        continue
    if res.kind not in ("meta-schema-url", "meta-schema-mirror"):
        continue
    op = str(u.get("output_path") or "")
    is_schema_output = op.endswith(".schema.json") or "/schema/" in op or "/contracts/" in op
    (appropriate if is_schema_output else category_error).append((u["id"], op))
print(f"meta-declaring units total          : {len(appropriate) + len(category_error)}")
print(f"  output IS a schema/contract (ok-ish): {len(appropriate)}")
print(f"  output is NOT a schema (category error): {len(category_error)} -> {category_error}")
print("\nDONE:av-probe4")
