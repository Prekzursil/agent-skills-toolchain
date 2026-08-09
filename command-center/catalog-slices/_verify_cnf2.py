#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify CNF-2.json off disk: schema shape, id sequence, dependency closure,
acyclicity, field variation, and near-duplicate detection WITH a planted-mutant
control (a detector that has not been shown to fire on a known duplicate is not
evidence of zero duplicates)."""
import json
import re
import sys
from collections import Counter

PATH = r"C:/Users/Prekzursil/source/ast-integrate/command-center/catalog-slices/CNF-2.json"

KEYS = {
    "id", "title", "phase", "question_or_target", "inputs", "dependencies",
    "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
    "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
    "tests_required", "reviewer_requirement", "completion_sentinel",
    "retry_policy", "failure_classification", "owner_approval_required",
}
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A",
          "8", "9", "10", "11", "12", "13", "14", "15", "16"}
SUBS = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
BUCKETS = {"B%02d" % i for i in range(1, 14)}

fail = []


def chk(cond, msg):
    if not cond:
        fail.append(msg)


with open(PATH, encoding="utf-8") as fh:
    raw = fh.read()
units = json.loads(raw)

print("PARSE: ok, bytes=%d" % len(raw.encode("utf-8")))
print("COUNT (read off disk): %d" % len(units))
chk(isinstance(units, list), "top level is not a list")
chk(len(units) == 64, "expected 64 units, got %d" % len(units))

ids = [u["id"] for u in units]
chk(len(set(ids)) == len(ids), "duplicate ids")
expected = ["CNF-%04d" % n for n in range(129, 193)]
chk(ids == expected, "id sequence mismatch: first=%s last=%s" % (ids[0], ids[-1]))
print("IDS: %s .. %s  sequential=%s" % (ids[0], ids[-1], ids == expected))

for u in units:
    k = set(u.keys())
    chk(k == KEYS, "%s key mismatch: missing=%s extra=%s" % (u["id"], KEYS - k, k - KEYS))
    chk(u["phase"] in PHASES, "%s bad phase %r" % (u["id"], u["phase"]))
    chk(u["execution_substrate"] in SUBS, "%s bad substrate" % u["id"])
    chk(isinstance(u["timeout_seconds"], int) and u["timeout_seconds"] > 0, "%s bad timeout" % u["id"])
    chk(u["completion_sentinel"] == "SUCCESS:" + u["id"], "%s bad sentinel" % u["id"])
    chk(u["output_path"] == "command-center/receipts/%s.json" % u["id"], "%s bad output_path" % u["id"])
    chk(isinstance(u["owner_approval_required"], bool), "%s owner_approval not bool" % u["id"])
    for f in ("inputs", "dependencies", "tool_permissions", "tests_required", "failure_classification"):
        chk(isinstance(u[f], list), "%s %s not a list" % (u["id"], f))
    chk(len(u["inputs"]) >= 2, "%s too few inputs" % u["id"])
    chk(len(u["tests_required"]) >= 3, "%s fewer than 3 tests_required" % u["id"])
    chk(len(u["failure_classification"]) >= 2, "%s too few failure classes" % u["id"])
    chk(len(u["question_or_target"]) >= 200, "%s question too thin (%d chars)" % (u["id"], len(u["question_or_target"])))
    chk(len(u["evidence_requirement"]) >= 120, "%s evidence too thin" % u["id"])
    mvr = u["assigned_model_vendor_role"]
    chk(set(mvr.keys()) == {"model", "vendor", "role"}, "%s bad mvr" % u["id"])

# dependency closure + acyclicity
idset = set(ids)
edges = {}
for u in units:
    outs = []
    for d in u["dependencies"]:
        if d.startswith("CNF-"):
            chk(d in idset, "%s depends on unknown in-slice id %s" % (u["id"], d))
            chk(d != u["id"], "%s self-dependency" % u["id"])
            outs.append(d)
        else:
            chk(d in BUCKETS, "%s unknown bucket dep %r" % (u["id"], d))
    edges[u["id"]] = outs

WHITE, GREY, BLACK = 0, 1, 2
color = {i: WHITE for i in ids}
cyc = []


def dfs(n, stack):
    color[n] = GREY
    for m in edges[n]:
        if color[m] == GREY:
            cyc.append(stack + [n, m])
        elif color[m] == WHITE:
            dfs(m, stack + [n])
    color[n] = BLACK


for i in ids:
    if color[i] == WHITE:
        dfs(i, [])
chk(not cyc, "dependency cycle: %s" % cyc[:3])
print("DEPS: in-slice edges=%d  bucket edges=%d  cycles=%d"
      % (sum(len(v) for v in edges.values()),
         sum(1 for u in units for d in u["dependencies"] if not d.startswith("CNF-")),
         len(cyc)))

# ---- field variation (the measured B09 catalog defect was 9 of 19 fields being
# one global default overridden by 0 of 103 items). Materialised per unit here.
def dist(f, key=lambda u, f: u[f]):
    return Counter(json.dumps(key(u, f), sort_keys=True) for u in units)


print("VARIATION:")
print("  substrates      :", dict(Counter(u["execution_substrate"] for u in units)))
print("  timeouts        :", dict(Counter(u["timeout_seconds"] for u in units)))
print("  vendors         :", dict(Counter(u["assigned_model_vendor_role"]["vendor"] for u in units)))
print("  roles           :", len(set(u["assigned_model_vendor_role"]["role"] for u in units)),
      sorted(set(u["assigned_model_vendor_role"]["role"] for u in units)))
print("  output_schemas  :", dict(Counter(u["output_schema"].rsplit("/", 1)[-1] for u in units)))
print("  retry variants  :", len(dist("retry_policy")))
print("  toolperm sets   :", len(dist("tool_permissions")))
print("  distinct titles :", len(set(u["title"] for u in units)))
print("  distinct qs     :", len(set(u["question_or_target"] for u in units)))
print("  owner_approval  :", dict(Counter(u["owner_approval_required"] for u in units)))
print("  failure classes :", len(set(c for u in units for c in u["failure_classification"])))
chk(len(set(u["title"] for u in units)) == 64, "titles not all distinct")
chk(len(dist("retry_policy")) >= 5, "retry_policy has too few distinct values")
chk(len(set(u["execution_substrate"] for u in units)) >= 3, "too few substrates")

# ---- near-duplicate detection with a PLANTED-MUTANT CONTROL
STOP = set("the a an of to and or is are for that this with not by be it its on in as must "
           "at from any every each which what does do can no non its own than then when".split())


def toks(u):
    t = (u["title"] + " " + u["question_or_target"]).lower()
    return set(w for w in re.findall(r"[a-z0-9_.-]{3,}", t) if w not in STOP)


def jac(a, b):
    return len(a & b) / float(len(a | b)) if (a | b) else 0.0


T = [toks(u) for u in units]
pairs = []
for i in range(len(units)):
    for j in range(i + 1, len(units)):
        s = jac(T[i], T[j])
        if s >= 0.30:
            pairs.append((round(s, 3), units[i]["id"], units[j]["id"]))
pairs.sort(reverse=True)
print("NEAR-DUP (Jaccard >= 0.30): %d pairs" % len(pairs))
for p in pairs[:10]:
    print("   ", p)
top = max((jac(T[i], T[j]) for i in range(len(T)) for j in range(i + 1, len(T))), default=0.0)
print("NEAR-DUP max pairwise similarity: %.3f" % top)

# control 1 (known-present duplicate): clone unit 0 with light rewording
mut = dict(units[0])
mut["id"] = "CNF-9999"
mut["title"] = units[0]["title"].replace("Author", "Write").replace("and", "plus")
mut["question_or_target"] = units[0]["question_or_target"].replace("must", "shall")
ctrl = jac(toks(mut), T[0])
print("CONTROL known-present duplicate similarity: %.3f (detector fires: %s)" % (ctrl, ctrl >= 0.30))
chk(ctrl >= 0.30, "near-dup detector FAILED its known-present control - zero-duplicate verdict is void")

# control 2 (known-absent): a sentinel token that exists nowhere
sentinel = "zzqqxxsentinel"
hits = sum(1 for u in units if sentinel in json.dumps(u).lower())
print("CONTROL known-absent sentinel hits: %d (expect 0)" % hits)
chk(hits == 0, "known-absent control polluted")

print()
if fail:
    print("FAILED:CNF-2 %d violations" % len(fail))
    for f in fail:
        print("  -", f)
    sys.exit(1)
print("SUCCESS:CNF-2 64 units, all checks pass")
sys.exit(0)
