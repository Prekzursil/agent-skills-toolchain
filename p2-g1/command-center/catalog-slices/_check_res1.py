"""Mechanical verification of RES-1.json read back OFF DISK.

Checks: field completeness, id format/uniqueness/sequence, controlled vocabularies,
dependency resolvability, per-field variance (no field may be a single constant),
and token-Jaccard near-duplicate detection with a planted-mutant detector control.
"""
import json
import os
import re
import itertools
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "RES-1.json")

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9", "10",
          "11", "12", "13", "14", "15", "16"}
SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}

with open(PATH, encoding="utf-8") as fh:
    units = json.load(fh)

fail = []
print("PARSED  :", type(units).__name__, "of", len(units))
assert isinstance(units, list), "top level must be a JSON array"

ids = [x["id"] for x in units]
print("IDS     : first=%s last=%s unique=%d" % (ids[0], ids[-1], len(set(ids))))
if len(set(ids)) != len(ids):
    fail.append("duplicate ids: %s" % [k for k, v in Counter(ids).items() if v > 1])
for i, x in enumerate(units, 1):
    if x["id"] != "RES-%04d" % i:
        fail.append("id out of sequence at index %d: %s" % (i, x["id"]))

for x in units:
    missing = [f for f in FIELDS if f not in x]
    extra = [k for k in x if k not in FIELDS]
    if missing:
        fail.append("%s missing %s" % (x["id"], missing))
    if extra:
        fail.append("%s has non-contract keys %s" % (x["id"], extra))
    for f in FIELDS:
        v = x.get(f)
        if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
            if f != "dependencies":
                fail.append("%s empty field %s" % (x["id"], f))
    if x["phase"] not in PHASES:
        fail.append("%s bad phase %s" % (x["id"], x["phase"]))
    if x["execution_substrate"] not in SUBSTRATES:
        fail.append("%s bad substrate %s" % (x["id"], x["execution_substrate"]))
    if not isinstance(x["owner_approval_required"], bool):
        fail.append("%s owner_approval_required not bool" % x["id"])
    if not isinstance(x["timeout_seconds"], int):
        fail.append("%s timeout not int" % x["id"])
    amr = x["assigned_model_vendor_role"]
    if set(amr) != {"model", "vendor", "role"}:
        fail.append("%s bad assigned_model_vendor_role keys %s" % (x["id"], sorted(amr)))
    if not x["question_or_target"].rstrip().endswith("?"):
        fail.append("%s question_or_target is not a question" % x["id"])
    if x["output_path"] != "command-center/research/%s.json" % x["id"]:
        fail.append("%s output_path mismatch" % x["id"])
    if x["id"] not in x["completion_sentinel"]:
        fail.append("%s sentinel does not name the unit" % x["id"])

# dependency resolvability: intra-slice ids must exist; bucket codes allowed
idset = set(ids)
BUCKETS = {"B01", "B02", "B03", "B04", "B05"}
dangling = set()
for x in units:
    for d in x["dependencies"]:
        if d.startswith("RES-"):
            if d not in idset:
                dangling.add((x["id"], d))
            if int(d.split("-")[1]) >= int(x["id"].split("-")[1]):
                fail.append("%s forward/self dependency %s" % (x["id"], d))
        elif d not in BUCKETS:
            fail.append("%s unknown dependency token %s" % (x["id"], d))
if dangling:
    fail.append("dangling deps: %s" % sorted(dangling))

# per-field variance: no mandated field may collapse to one global value
print("\nVARIANCE (distinct values per field):")
for f in FIELDS:
    vals = set(json.dumps(x[f], sort_keys=True) for x in units)
    flagpad = "  <-- SINGLE GLOBAL VALUE" if len(vals) == 1 and f != "phase" else ""
    print("  %-28s %3d%s" % (f, len(vals), flagpad))
    if len(vals) == 1 and f not in ("phase",):
        fail.append("field %s has a single global value across all units" % f)

print("\nDISTRIBUTIONS:")
print("  substrate :", dict(Counter(x["execution_substrate"] for x in units)))
print("  vendor    :", dict(Counter(x["assigned_model_vendor_role"]["vendor"] for x in units)))
print("  roles     :", len(set(x["assigned_model_vendor_role"]["role"] for x in units)), "distinct")
print("  timeouts  :", dict(sorted(Counter(x["timeout_seconds"] for x in units).items())))
print("  schemas   :", len(set(x["output_schema"] for x in units)), "distinct")
print("  owner_gate:", dict(Counter(x["owner_approval_required"] for x in units)))
print("  toolsets  :", len(set(json.dumps(x["tool_permissions"]) for x in units)), "distinct")

for name, key in [("substrate", lambda x: x["execution_substrate"]),
                  ("owner_approval", lambda x: x["owner_approval_required"])]:
    seen = set(key(x) for x in units)
    if name == "substrate" and seen != SUBSTRATES:
        fail.append("substrates unused: %s" % sorted(SUBSTRATES - seen))
    if name == "owner_approval" and seen != {True, False}:
        fail.append("owner_approval_required does not use both booleans")

# ---------------------------------------------------------- near-duplicate detection
STOP = set("the a an of to in for and or is are what which how does do that this it its by "
           "on at as with from be been was were will would can could must may not no "
           "than then when where who whom whose why into over under between each every "
           "any all both some such only own same so s t just".split())


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2)


def jac(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


sig = {x["id"]: toks(x["title"] + " " + x["question_or_target"]) for x in units}
pairs = sorted(((jac(sig[a], sig[b]), a, b) for a, b in itertools.combinations(ids, 2)),
               reverse=True)
print("\nNEAR-DUPLICATE SCAN (token Jaccard over title+question):")
for s, a, b in pairs[:8]:
    print("  %.3f  %s / %s" % (s, a, b))
maxs = pairs[0][0]
over = [(s, a, b) for s, a, b in pairs if s >= 0.50]
print("  max=%.3f   pairs>=0.50: %d   pairs>=0.40: %d"
      % (maxs, len(over), len([1 for s, _, _ in pairs if s >= 0.40])))
if over:
    fail.append("near-duplicate pairs at Jaccard>=0.50: %s" % over)

# DETECTOR CONTROL: plant a near-duplicate and prove the scan fires on it
victim = units[60]
mutant = toks(victim["title"] + " " + victim["question_or_target"] + " additionally")
ctrl = jac(sig[victim["id"]], mutant)
print("  detector control: planted paraphrase of %s scores %.3f (must be >=0.50) -> %s"
      % (victim["id"], ctrl, "FIRES" if ctrl >= 0.50 else "SILENT-DETECTOR-BROKEN"))
if ctrl < 0.50:
    fail.append("duplicate detector failed its known-positive control")
# negative control: two known-different units must score low
neg = jac(sig["RES-0119"], sig["RES-0050"])
print("  negative control: RES-0119 vs RES-0050 scores %.3f (must be < 0.30) -> %s"
      % (neg, "OK" if neg < 0.30 else "DETECTOR-TOO-LOOSE"))
if neg >= 0.30:
    fail.append("duplicate detector failed its known-negative control")

print("\n" + ("FAILED:RES-1-check\n" + "\n".join("  - " + f for f in fail)
             if fail else "SUCCESS:RES-1-check  units=%d  all %d fields present on all units"
             % (len(units), len(FIELDS))))
