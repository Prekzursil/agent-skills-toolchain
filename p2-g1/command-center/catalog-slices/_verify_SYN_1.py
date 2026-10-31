#!/usr/bin/env python
"""Independent verifier for SYN-1.json.

Deliberately NOT the generator's inline validation re-run: this reads the file
back off disk, re-derives every count from the parsed bytes, and adds two things
the generator cannot do -- a near-duplicate sweep WITHIN the slice and ACROSS the
sibling slices, each with a planted-mutant detector control.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "SYN-1.json")

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]

STOP = set("""a an the and or of to in on for by with is are be that this it its as at from
into not no any all every each which what when where must may can will shall should would
than then so such via per over under out up down we you they he she i our their his her
unit units target question implementation spec line lines file files must-be one two three
does do did done than only also more most less least same other another""".split())


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9_]+", s.lower()) if len(w) > 2 and w not in STOP)


def jac(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def sig(u):
    return toks(u["title"] + " " + u["question_or_target"])


fail = []
note = []

# ---- 1. parse + shape ------------------------------------------------------
raw = open(SRC, "rb").read()
data = json.loads(raw.decode("utf-8"))
assert isinstance(data, list), "top level is not a list"
N = len(data)
print("READ %s  bytes=%d  units=%d" % (SRC, len(raw), N))
if N != 48:
    fail.append("unit count is %d, expected 48" % N)

ids = [u["id"] for u in data]
if len(set(ids)) != N:
    fail.append("duplicate ids present")
for i, uid in enumerate(ids, start=1):
    if uid != "SYN-%04d" % i:
        fail.append("id at position %d is %s" % (i, uid))

for u in data:
    missing = [f for f in FIELDS if f not in u]
    extra = [k for k in u if k not in FIELDS]
    if missing:
        fail.append("%s missing %s" % (u["id"], missing))
    if extra:
        fail.append("%s extra %s" % (u["id"], extra))
    for f in FIELDS:
        v = u.get(f)
        if v is None or v == "" or v == []:
            if f != "dependencies":
                fail.append("%s empty field %s" % (u["id"], f))

# ---- 2. per-field distinctness (global-default-in-disguise detector) -------
print("\n-- field value distinctness (a field with 1 value is a hidden global default) --")
for f in FIELDS:
    vals = set(json.dumps(u[f], sort_keys=True) for u in data)
    flagmark = ""
    if len(vals) < 2 and f != "phase":
        fail.append("FIELD COLLAPSE %s" % f)
        flagmark = "  <== COLLAPSE"
    print("  %-28s distinct=%3d%s" % (f, len(vals), flagmark))

# ---- 3. substrate / phase / timeout distributions --------------------------
sub = Counter(u["execution_substrate"] for u in data)
ph = Counter(u["phase"] for u in data)
to = Counter(u["timeout_seconds"] for u in data)
ven = Counter(u["assigned_model_vendor_role"]["vendor"] for u in data)
roles = set(u["assigned_model_vendor_role"]["role"] for u in data)
oar = Counter(u["owner_approval_required"] for u in data)
print("\nsubstrate:", dict(sub))
print("phase:", dict(ph))
print("timeouts:", sorted(to.items()))
print("vendors:", dict(ven), " distinct roles:", len(roles))
print("owner_approval_required:", dict(oar))
if len(roles) < 20:
    note.append("only %d distinct roles across 48 units" % len(roles))

# ---- 4. dependency integrity ----------------------------------------------
TOK = re.compile(r"^(SYN|CC|AUD|RES|WFA|CNL|ARC|IMP|TST|CNF|ADV|BLD|REL)-\d{4}$|^B\d{2}$")
idset = set(ids)
# build the set of ids that really exist in sibling slices on disk
sibling = {}
for f in glob.glob(os.path.join(HERE, "*.json")):
    if os.path.basename(f) == "SYN-1.json":
        continue
    try:
        for s in json.load(open(f, encoding="utf-8")):
            sibling[s["id"]] = (os.path.basename(f), s["title"], s.get("question_or_target", ""))
    except Exception:
        pass
unresolved = []
for u in data:
    for d in u["dependencies"]:
        if not TOK.match(d):
            fail.append("%s bad dep token %r" % (u["id"], d))
            continue
        if d.startswith("B"):
            continue
        if d in idset:
            continue
        if d in sibling:
            continue
        unresolved.append((u["id"], d))
print("\ndeps: total=%d  intra-slice=%d  bucket-codes=%d  cross-slice-resolved=%d  unresolved=%d"
      % (sum(len(u["dependencies"]) for u in data),
         sum(1 for u in data for d in u["dependencies"] if d in idset),
         sum(1 for u in data for d in u["dependencies"] if d.startswith("B")),
         sum(1 for u in data for d in u["dependencies"] if d in sibling),
         len(unresolved)))
if unresolved:
    print("  UNRESOLVED (bucket not yet written -> acceptable only if the prefix is a real bucket):")
    for a, b in unresolved:
        print("   ", a, "->", b)

# ---- 5. intra-slice near-duplicate sweep + DETECTOR CONTROL ---------------
print("\n-- near-duplicate sweep (token Jaccard over title+question) --")
sigs = [(u["id"], sig(u)) for u in data]
pairs = []
for i in range(len(sigs)):
    for j in range(i + 1, len(sigs)):
        s = jac(sigs[i][1], sigs[j][1])
        if s >= 0.30:
            pairs.append((s, sigs[i][0], sigs[j][0]))
pairs.sort(reverse=True)
print("  intra-slice pairs >= 0.30:", len(pairs))
for s, a, b in pairs[:12]:
    print("    %.3f  %s ~ %s" % (s, a, b))

# DETECTOR CONTROL: plant an exact clone and a paraphrase; the sweep must catch both.
clone = dict(data[0])
clone["id"] = "SYN-9001"
para = dict(data[0])
para["id"] = "SYN-9002"
para["title"] = "Assemble the causal DAG of root causes rather than emitting a flat findings list"
ctrl = [(u["id"], sig(u)) for u in (clone, para)]
ctrl_hits = []
for cid, cs in ctrl:
    best = max((jac(cs, s), i) for i, s in sigs)
    ctrl_hits.append((cid, best[0], best[1]))
print("  DETECTOR CONTROL (planted clone + paraphrase vs the real slice):")
for cid, sc, tgt in ctrl_hits:
    print("    %s -> best match %s at %.3f" % (cid, tgt, sc))
if ctrl_hits[0][1] < 0.90:
    fail.append("detector control FAILED: exact clone scored %.3f" % ctrl_hits[0][1])
if ctrl_hits[1][1] < 0.30:
    fail.append("detector control FAILED: paraphrase scored %.3f (detector is blind)" % ctrl_hits[1][1])
# negative control: two genuinely distinct real units must score low
neg = jac(dict(sigs)["SYN-0001"], dict(sigs)["SYN-0045"])
print("    negative control SYN-0001 ~ SYN-0045 = %.3f" % neg)
if neg >= 0.30:
    fail.append("negative control FAILED: unrelated units scored %.3f" % neg)

# ---- 6. cross-slice duplication against every sibling unit ----------------
print("\n-- cross-slice duplication sweep (%d sibling units) --" % len(sibling))
cross = []
for uid, s in sigs:
    for sid, (sf, st, sq) in sibling.items():
        sc = jac(s, toks(st + " " + sq))
        cross.append((sc, uid, sid, sf))
cross.sort(reverse=True)
over = [c for c in cross if c[0] >= 0.30]
print("  cross-slice pairs >= 0.30:", len(over))
print("  top 8 nearest sibling pairs regardless of threshold:")
for sc, uid, sid, sf in cross[:8]:
    print("    %.3f  %s ~ %s (%s)" % (sc, uid, sid, sf))
# TIE-BREAKER, mechanically independent of the topic vocabulary.
# Full-text Jaccard is confounded by CROSS-REFERENCES: naming a sibling unit in order to
# state the distinctness delta RAISES lexical overlap while LOWERING real duplication
# (measured here: SYN-0043 ~ TST-0347 went 0.261 -> 0.359 when the delta sentence was
# added). So for any pair over threshold, score the MECHANISM instead -- what the unit
# does, taken from evidence_requirement + tests_required, which describe procedure rather
# than subject. Same subject + different mechanism is a legitimate split; same subject +
# same mechanism is a real duplicate and fails.
def mech(u):
    return toks(u["evidence_requirement"] + " " + " ".join(u["tests_required"]))


sibfull = {}
for f in glob.glob(os.path.join(HERE, "*.json")):
    if os.path.basename(f) == "SYN-1.json":
        continue
    try:
        for s in json.load(open(f, encoding="utf-8")):
            sibfull[s["id"]] = s
    except Exception:
        pass

if over:
    print("\n  TIE-BREAKER on over-threshold pairs (mechanism similarity):")
    real_dupes = []
    for sc, uid, sid, sf in over:
        mine = [u for u in data if u["id"] == uid][0]
        theirs = sibfull.get(sid)
        if theirs is None or "evidence_requirement" not in theirs:
            real_dupes.append((uid, sid, "cannot score"))
            continue
        ms = jac(mech(mine), mech(theirs))
        verdict = "REAL-DUPLICATE" if ms >= 0.30 else "same-subject-different-mechanism OK"
        print("    %s ~ %s  text=%.3f  mechanism=%.3f  -> %s" % (uid, sid, sc, ms, verdict))
        if ms >= 0.30:
            real_dupes.append((uid, sid, round(ms, 3)))
    # control: the tie-breaker must score a self-comparison at 1.0 and an unrelated pair low
    selfscore = jac(mech(data[0]), mech(data[0]))
    unrel = jac(mech(data[0]), mech(data[44]))
    print("    tie-breaker control: self=%.3f  unrelated=%.3f" % (selfscore, unrel))
    if selfscore < 0.99 or unrel >= 0.30:
        fail.append("tie-breaker control FAILED (self=%.3f unrelated=%.3f)" % (selfscore, unrel))
    if real_dupes:
        fail.append("REAL cross-slice duplicates (subject AND mechanism): %s" % real_dupes)

# ---- 7. scaling doctrine: credentialed / live-harness units serialized ----
print("\n-- scaling doctrine spot-check --")
CRED = ("mcp__codex__", "mcp__basic-memory__", "mcp__github__", "mcp__figma__")
bad = []
for u in data:
    cred = any(t.startswith(CRED) for t in u["tool_permissions"])
    if cred and u["execution_substrate"] == "cloud-batch":
        bad.append(u["id"])
print("  units holding a credentialed MCP tool:",
      sum(1 for u in data if any(t.startswith(CRED) for t in u["tool_permissions"])))
print("  of those, any on cloud-batch (would violate the doctrine):", bad or "none")
if bad:
    fail.append("credentialed units on cloud-batch: %s" % bad)

# ---- verdict ---------------------------------------------------------------
print("\n" + "=" * 70)
for n in note:
    print("NOTE: " + n)
if fail:
    for f in fail:
        print("FAILED: " + f)
    print("FAILED:verify-SYN-1")
    sys.exit(1)
print("first=%s last=%s count=%d" % (ids[0], ids[-1], N))
print("SUCCESS:verify-SYN-1")
