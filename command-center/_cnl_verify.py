#!/usr/bin/env python3
"""Independent read-back + DETECTOR CONTROL for CNL-1.json.

Mechanically independent of _cnl_build.py: it re-reads the file from disk and
re-derives every count. Also proves the near-duplicate scanner is not vacuous
by planting known-present duplicates and confirming it FIRES on them.
"""
import json
import re
from collections import Counter

P = "C:/Users/Prekzursil/source/ast-integrate/command-center/catalog-slices/CNL-1.json"

with open(P, encoding="utf-8") as f:
    raw = f.read()
U = json.loads(raw)

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]

print("bytes on disk:", len(raw))
print("parses:", isinstance(U, list))
print("COUNT READ OFF DISK:", len(U))
print("first id:", U[0]["id"], "| last id:", U[-1]["id"])

# sequential + zero-padded + unique
exp = ["CNL-%04d" % i for i in range(1, len(U) + 1)]
got = [x["id"] for x in U]
print("ids sequential+padded from 1:", got == exp)
print("ids unique:", len(set(got)) == len(got))

# every unit carries every mandated field, nothing extra
missing = [x["id"] for x in U if set(x) != set(FIELDS)]
print("units with wrong field set:", len(missing), missing[:5])
print("field count per unit:", sorted(set(len(x) for x in U)))

# sentinel matches id
bad_sent = [x["id"] for x in U if x["completion_sentinel"] != "SUCCESS:" + x["id"]]
print("sentinel mismatches:", len(bad_sent))

# output_path carries the id and is unique
bad_path = [x["id"] for x in U if x["id"] not in x["output_path"]]
print("output_path missing id:", len(bad_path))
print("output_path unique:", len(set(x["output_path"] for x in U)) == len(U))

# dependency targets resolve
known = set(got) | {"B01", "B02", "B03"}
dang = [(x["id"], d) for x in U for d in x["dependencies"] if d not in known]
print("dangling deps:", len(dang), dang[:5])
selfdep = [x["id"] for x in U if x["id"] in x["dependencies"]]
print("self-deps:", len(selfdep))

# acyclicity over intra-slice edges
adj = {x["id"]: [d for d in x["dependencies"] if d.startswith("CNL-")] for x in U}
state = {}


def cyc(n):
    state[n] = 1
    for m in adj.get(n, []):
        if state.get(m) == 1:
            return [n, m]
        if state.get(m) is None:
            r = cyc(m)
            if r:
                return [n] + r
    state[n] = 2
    return None


found = None
for n in adj:
    if state.get(n) is None:
        found = cyc(n)
        if found:
            break
print("dependency cycle:", found)

# question is a question and is specific
print("all question_or_target end with ?:",
      all(x["question_or_target"].rstrip().endswith("?") for x in U))
print("min/median question length:",
      min(len(x["question_or_target"]) for x in U),
      sorted(len(x["question_or_target"]) for x in U)[len(U) // 2])

print("phases:", dict(Counter(x["phase"] for x in U)))
print("substrates:", dict(Counter(x["execution_substrate"] for x in U)))
print("owner_approval_required true:", sum(1 for x in U if x["owner_approval_required"]))
print("timeout range:", min(x["timeout_seconds"] for x in U),
      max(x["timeout_seconds"] for x in U))
print("distinct reviewer_requirement:", len(set(x["reviewer_requirement"] for x in U)))
print("distinct retry_policy:", len(set(x["retry_policy"] for x in U)))
print("distinct evidence_requirement:", len(set(x["evidence_requirement"] for x in U)))
print("distinct tests_required blocks:",
      len(set(json.dumps(x["tests_required"]) for x in U)))
print("distinct failure_classification sets:",
      len(set(json.dumps(x["failure_classification"]) for x in U)))

# ---------------- NEAR-DUPLICATE SCANNER + DETECTOR CONTROL ----------------
STOP = set("what which the a an of and or to for is are how does do that this it in on by with "
           "not no its their than then when where who whom whose must may can be been being as at "
           "from into over under after before between one two both each every any all rather "
           "there here so such but if while during against per via given only also more most "
           "less least same different other another such about upon within without across".split())


def toks(x):
    return set(w for w in re.findall(
        r"[a-z0-9]+", (x["title"] + " " + x["question_or_target"]).lower())
        if w not in STOP and len(w) > 2)


def scan(units, thr):
    out = []
    T = [toks(x) for x in units]
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            un = len(T[i] | T[j])
            if not un:
                continue
            jac = len(T[i] & T[j]) / un
            if jac >= thr:
                out.append((round(jac, 3), units[i]["id"], units[j]["id"]))
    out.sort(reverse=True)
    return out


print("\n--- near-duplicate scan on the REAL slice ---")
for thr in (0.50, 0.42, 0.35, 0.30, 0.25):
    print("  threshold %.2f -> %d pairs" % (thr, len(scan(U, thr))))
top = scan(U, 0.0)[:8]
print("  highest actual similarity pairs:")
for jac, a, b in top:
    ta = next(x["title"] for x in U if x["id"] == a)
    tb = next(x["title"] for x in U if x["id"] == b)
    print("    %.3f %s | %s" % (jac, a + " " + ta[:44], b + " " + tb[:44]))

print("\n--- DETECTOR CONTROL: plant KNOWN-PRESENT duplicates ---")
ctrl = [dict(x) for x in U]
# C1: exact copy with a renamed id (the cheapest padding attack)
c1 = dict(U[0])
c1["id"] = "CNL-9001"
ctrl.append(c1)
# C2: reworded copy - same mechanism, synonyms swapped (the real padding shape)
c2 = dict(U[30])
c2["id"] = "CNL-9002"
c2["title"] = U[30]["title"].replace("protocols", "protocol records").replace(
    "Executable runtime semantics", "Runnable execution semantics")
c2["question_or_target"] = U[30]["question_or_target"].replace(
    "For each of", "Considering each one of").replace("what is the", "what exactly is the")
ctrl.append(c2)
# C3: a genuinely DISTINCT unit - must NOT be flagged (false-positive control)
c3 = dict(U[0])
c3["id"] = "CNL-9003"
c3["title"] = "Marketplace signature verification and SBOM provenance for published packages"
c3["question_or_target"] = ("Which signature scheme and SBOM format does the marketplace registry "
                            "accept, and what happens on install when a package signature verifies "
                            "but its SBOM lists a dependency the lockfile never pinned?")
ctrl.append(c3)

hits = scan(ctrl, 0.42)
planted = {"CNL-9001", "CNL-9002", "CNL-9003"}
fired = set()
for jac, a, b in hits:
    if a in planted or b in planted:
        fired.add(a if a in planted else b)
        print("  FIRED %.3f  %s <-> %s" % (jac, a, b))
print("  C1 exact-copy caught:", "CNL-9001" in fired)
print("  C2 reworded-copy caught:", "CNL-9002" in fired)
print("  C3 distinct-unit NOT flagged (false-positive control):", "CNL-9003" not in fired)
print("  control verdict:",
      "PASS - detector fires on known-present duplicates and is silent on a distinct unit"
      if {"CNL-9001", "CNL-9002"} <= fired and "CNL-9003" not in fired
      else "FAIL - detector is not trustworthy, the 0-pair reading means nothing")
