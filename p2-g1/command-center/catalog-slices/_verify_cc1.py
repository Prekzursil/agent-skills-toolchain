"""Mechanical verification of CC-1.json. Read-only; prints a terminal-state marker."""
import json
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

P = Path(__file__).parent / "CC-1.json"
FIELDS = [
    "id", "title", "phase", "question_or_target", "inputs", "dependencies",
    "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
    "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
    "tests_required", "reviewer_requirement", "completion_sentinel",
    "retry_policy", "failure_classification", "owner_approval_required",
]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A",
          "8", "9", "10", "11", "12", "13", "14", "15", "16"}
SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}

raw = P.read_text(encoding="utf-8")
units = json.loads(raw)
fail = []
print("PARSE ok  bytes=%d  units=%d" % (len(raw.encode("utf-8")), len(units)))

ids = [u["id"] for u in units]
print("ids_first=%s ids_last=%s unique=%s" % (ids[0], ids[-1], len(set(ids)) == len(ids)))

# --- field completeness + enum validity ---------------------------------
for i, u in enumerate(units, 1):
    exp = "CC-%04d" % i
    if u.get("id") != exp:
        fail.append("id sequence: got %s want %s" % (u.get("id"), exp))
    missing = [f for f in FIELDS if f not in u]
    extra = [k for k in u if k not in FIELDS]
    if missing:
        fail.append("%s missing %s" % (u.get("id"), missing))
    if extra:
        fail.append("%s extra %s" % (u.get("id"), extra))
    for f in FIELDS:
        v = u.get(f)
        if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
            if f != "dependencies":  # empty deps are legitimate (roots)
                fail.append("%s empty field %s" % (u["id"], f))
    if u.get("phase") not in PHASES:
        fail.append("%s bad phase %r" % (u["id"], u.get("phase")))
    if u.get("execution_substrate") not in SUBSTRATES:
        fail.append("%s bad substrate %r" % (u["id"], u.get("execution_substrate")))
    if u.get("completion_sentinel") != "SUCCESS:" + u["id"]:
        fail.append("%s sentinel mismatch" % u["id"])
    if not isinstance(u.get("owner_approval_required"), bool):
        fail.append("%s owner_approval_required not bool" % u["id"])
    if not isinstance(u.get("timeout_seconds"), int):
        fail.append("%s timeout not int" % u["id"])
    if not isinstance(u.get("tests_required"), list) or len(u["tests_required"]) < 3:
        fail.append("%s fewer than 3 tests" % u["id"])
    qt = u.get("question_or_target", "")
    if not (qt.startswith("Question") or qt.startswith("Implementation target")):
        fail.append("%s question_or_target is a topic, not a question/target" % u["id"])

# --- DAG check -----------------------------------------------------------
idset = set(ids)
edges = {u["id"]: [d for d in u["dependencies"] if d in idset] for u in units}
for u in units:
    for d in u["dependencies"]:
        if d not in idset and not re.fullmatch(r"B\d{2}", d):
            fail.append("%s dangling dependency %s" % (u["id"], d))
seen, stack = set(), set()


def visit(n):
    if n in stack:
        fail.append("CYCLE at %s" % n)
        return
    if n in seen:
        return
    stack.add(n)
    for m in edges.get(n, []):
        visit(m)
    stack.discard(n)
    seen.add(n)


for n in ids:
    visit(n)

# --- per-unit variation of the 9 previously-global fields ----------------
GLOBAL9 = ["assigned_model_vendor_role", "tool_permissions", "execution_substrate",
           "timeout_seconds", "output_schema", "tests_required",
           "reviewer_requirement", "retry_policy", "failure_classification"]
print("\nDISTINCT VALUES ACROSS THE 9 FORMERLY-GLOBAL FIELDS:")
for f in GLOBAL9:
    vals = {json.dumps(u[f], sort_keys=True) for u in units}
    print("  %-28s distinct=%2d / 24" % (f, len(vals)))
    if len(vals) == 1:
        fail.append("field %s has a single global value across all 24 units" % f)

# --- near-duplicate self-check (mechanical, not eyeballed) ---------------
STOP = set(("the a an and or of to in for that this with must be is are on by not "
            "it its as at from into then than which what when where must-be a-the "
            "unit units work spec target question implementation must").split())


def toks(u):
    text = (u["title"] + " " + u["question_or_target"]).lower()
    return {w for w in re.findall(r"[a-z0-9_.-]{3,}", text) if w not in STOP}


pairs = []
for a, b in combinations(units, 2):
    ta, tb = toks(a), toks(b)
    j = len(ta & tb) / max(1, len(ta | tb))
    pairs.append((j, a["id"], b["id"]))
pairs.sort(reverse=True)
print("\nTOP 6 LEXICAL JACCARD PAIRS (near-duplicate self-check):")
for j, x, y in pairs[:6]:
    print("  %.3f  %s <-> %s" % (j, x, y))
if pairs[0][0] >= 0.55:
    fail.append("near-duplicate pair above 0.55: %s" % (pairs[0],))

# --- distribution ---------------------------------------------------------
print("\nphase      :", dict(Counter(u["phase"] for u in units)))
print("substrate  :", dict(Counter(u["execution_substrate"] for u in units)))
print("timeouts   :", sorted(Counter(u["timeout_seconds"] for u in units).items()))
print("owner_gate :", sum(1 for u in units if u["owner_approval_required"]), "of 24")
print("vendors    :", dict(Counter(u["assigned_model_vendor_role"]["vendor"] for u in units)))
print("out_schemas:", len({u["output_schema"] for u in units}), "distinct")

print("\n" + ("FAILED:CC-1of1 " + " | ".join(fail) if fail else "SUCCESS:CC-1of1 all checks pass"))
sys.exit(1 if fail else 0)
