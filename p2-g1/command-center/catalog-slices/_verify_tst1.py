#!/usr/bin/env python3
"""Independent read-back verification of TST-1.json.

Deliberately does NOT import the generator: it re-reads the bytes off disk and
re-derives every count, so a generator bug cannot certify itself.
Includes a planted-mutant control on the near-duplicate detector (rule 6:
prove the detector fires on a known-broken state before trusting a zero).
"""
import collections
import json
import pathlib
import re
import sys

p = pathlib.Path(__file__).with_name("TST-1.json")
raw = p.read_bytes()
units = json.loads(raw.decode("utf-8"))

print("file        :", p)
print("bytes       :", len(raw))
print("units on disk:", len(units))
print("first id    :", units[0]["id"])
print("last id     :", units[-1]["id"])

REQUIRED = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
            "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
            "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
            "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
            "failure_classification", "owner_approval_required"]

problems = []
for u in units:
    missing = [f for f in REQUIRED if f not in u]
    extra = [f for f in u if f not in REQUIRED]
    if missing:
        problems.append("%s missing %s" % (u.get("id"), missing))
    if extra:
        problems.append("%s extra %s" % (u.get("id"), extra))
print("field count per unit:", sorted({len(u) for u in units}))
print("field problems      :", problems or "NONE")

ids = [u["id"] for u in units]
print("ids unique          :", len(set(ids)) == len(ids))
print("ids sequential      :", ids == ["TST-%04d" % i for i in range(1, len(units) + 1)])

# ---- per-unit variation of the fields that were a measured defect elsewhere --
def sig(u):
    a = u["assigned_model_vendor_role"]
    return (a["model"], a["vendor"], a["role"])


print()
print("DISTRIBUTIONS (a field with 1 distinct value = a global default in disguise)")
for label, fn in [
    ("phase", lambda u: u["phase"]),
    ("substrate", lambda u: u["execution_substrate"]),
    ("vendor", lambda u: u["assigned_model_vendor_role"]["vendor"]),
    ("role", lambda u: u["assigned_model_vendor_role"]["role"]),
    ("timeout_seconds", lambda u: u["timeout_seconds"]),
    ("output_schema", lambda u: u["output_schema"].split("/")[-1]),
    ("tool_permissions (set)", lambda u: ",".join(u["tool_permissions"])[:26]),
    ("retry_policy", lambda u: u["retry_policy"][:22]),
    ("owner_approval_required", lambda u: u["owner_approval_required"]),
    ("failure_classification", lambda u: tuple(u["failure_classification"])[0]),
]:
    c = collections.Counter(fn(u) for u in units)
    print("  %-24s distinct=%-3d %s" % (label, len(c), dict(c.most_common(8))))

print("  %-24s distinct=%-3d" % ("model/vendor/role triple", len({sig(u) for u in units})))
print("  %-24s distinct=%-3d" % ("output_path", len({u["output_path"] for u in units})))
print("  %-24s distinct=%-3d" % ("question_or_target", len({u["question_or_target"] for u in units})))

# ---- dependency integrity -----------------------------------------------
# The real invariant is ACYCLICITY, not id-ordering: a catalog may legitimately
# name a higher-numbered prerequisite. An id-order check would have reported 4
# false positives, so it is replaced by a Kahn topological sort.
idset = set(ids)
bad = []
bucket = set()
fwd = []
graph = {}
for u in units:
    graph[u["id"]] = []
    for d in u["dependencies"]:
        if d.startswith("TST-"):
            if d not in idset:
                bad.append((u["id"], d + " DANGLING"))
            elif d == u["id"]:
                bad.append((u["id"], "SELF-DEPENDENCY"))
            else:
                graph[u["id"]].append(d)
                if d > u["id"]:
                    fwd.append("%s->%s" % (u["id"], d))
        else:
            bucket.add(d)

indeg = {k: len(v) for k, v in graph.items()}
ready = [k for k, v in indeg.items() if v == 0]
seen = 0
rdep = collections.defaultdict(list)
for k, vs in graph.items():
    for v in vs:
        rdep[v].append(k)
while ready:
    n = ready.pop()
    seen += 1
    for m in rdep[n]:
        indeg[m] -= 1
        if indeg[m] == 0:
            ready.append(m)
cyclic = seen != len(graph)

print()
print("dangling/self deps   :", bad or "NONE")
print("acyclic (Kahn)       :", not cyclic, "(%d/%d nodes ordered)" % (seen, len(graph)))
print("forward-id deps      :", len(fwd), "->", fwd or "none", "(legal: id order != topo order)")
print("intra-slice dep edges:", sum(len(v) for v in graph.values()))
print("units with >=1 dep   :", sum(1 for u in units if u["dependencies"]))
print("bucket codes used    :", sorted(bucket))
if cyclic:
    bad.append(("GRAPH", "CYCLE DETECTED"))

# ---- MECHANICAL near-duplicate scan (token Jaccard over title+target) ----
STOP = set("the a an of to and or is are for that with this it its not be must on in by as at "
           "from any every each per than does do can no non one two".split())


def toks(u):
    t = (u["title"] + " " + u["question_or_target"]).lower()
    return {w for w in re.findall(r"[a-z_]{3,}", t) if w not in STOP}


def jac(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


T = {u["id"]: toks(u) for u in units}
pairs = []
for i in range(len(units)):
    for j in range(i + 1, len(units)):
        a, b = units[i]["id"], units[j]["id"]
        s = jac(T[a], T[b])
        if s >= 0.20:
            pairs.append((round(s, 3), a, b, units[i]["title"][:52], units[j]["title"][:52]))
pairs.sort(reverse=True)
print()
print("NEAR-DUPLICATE SCAN (token Jaccard >= 0.20) — %d pairs" % len(pairs))
for row in pairs[:15]:
    print("   %.3f  %s / %s\n          %s\n          %s" % row)

# ---- DETECTOR CONTROL: plant a near-duplicate and require the scan to see it
clone = dict(units[0])
clone["id"] = "TST-9999"
clone["title"] = units[0]["title"].replace("Executable", "Runnable")
ctrl = jac(toks(units[0]), toks(clone))
print()
print("DETECTOR CONTROL (planted reworded clone of TST-0001): jaccard=%.3f -> %s"
      % (ctrl, "FIRES (detector works)" if ctrl >= 0.20 else "SILENT (DETECTOR BROKEN)"))
lo = min(jac(T[a], T[b]) for a in list(T)[:1] for b in list(T)[1:])
print("DETECTOR CONTROL (known-distinct pair floor): min observed jaccard=%.3f" % lo)

ok = (not problems and not bad and len(units) == 128
      and ids == ["TST-%04d" % i for i in range(1, 129)] and ctrl >= 0.20)
print()
print("VERDICT:", "SUCCESS:verify-TST-1" if ok else "FAILED:verify-TST-1")
sys.exit(0 if ok else 1)
