"""Verifier for IMP-3.json. Reads the file back OFF DISK - never trusts the generator.

Checks:
  1. parses, is a list, count
  2. id format, uniqueness, contiguity from IMP-0257
  3. all 19 mandated field names present on every unit, no extra keys
  4. enumerated vocabularies (phase, execution_substrate) respected
  5. intra-slice near-duplicate scan on question_or_target + title (token Jaccard)
  6. cross-slice near-duplicate scan against every sibling *.json in this directory
  7. detector control: a planted duplicate pair MUST be caught by the scanner before
     any "0 duplicates" verdict is believed (single-signal-verification rule 3b)
  8. dependency references resolve (intra-slice ids or declared bucket codes)
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MINE = os.path.join(HERE, "IMP-3.json")

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9", "10",
          "11", "12", "13", "14", "15", "16"}
SUBS = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
BUCKETS = {"B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11",
           "B12", "B13"}

STOP = set("the a an of to and or for in on with by that this is are be it its as at from "
           "does do can any every no not it's implement so plus into per over under "
           "falsifiable question rather than must not".split())


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9_]+", s.lower()) if w not in STOP and len(w) > 2)


def jac(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


fails = []
warns = []

raw = io.open(MINE, encoding="utf-8").read()
data = json.loads(raw)
assert isinstance(data, list), "top level is not a list"
N = len(data)
print("COUNT_ON_DISK %d" % N)
print("BYTES %d" % len(raw))

# 2. ids
ids = [u.get("id") for u in data]
if len(set(ids)) != N:
    fails.append("duplicate ids")
for i, uid in enumerate(ids):
    want = "IMP-%04d" % (257 + i)
    if uid != want:
        fails.append("id at index %d is %s, expected %s" % (i, uid, want))
        break
print("IDS_FIRST %s  IDS_LAST %s" % (ids[0], ids[-1]))

# 3. fields
for u in data:
    missing = [f for f in FIELDS if f not in u]
    extra = [k for k in u if k not in FIELDS]
    if missing:
        fails.append("%s missing %s" % (u.get("id"), missing))
    if extra:
        fails.append("%s extra keys %s" % (u.get("id"), extra))
    for f in ("inputs", "dependencies", "tool_permissions", "tests_required",
              "failure_classification"):
        if not isinstance(u.get(f), list) or not u.get(f):
            fails.append("%s field %s not a non-empty list" % (u.get("id"), f))
    if not isinstance(u.get("owner_approval_required"), bool):
        fails.append("%s owner_approval_required not bool" % u.get("id"))
    if not isinstance(u.get("timeout_seconds"), int):
        fails.append("%s timeout not int" % u.get("id"))
    if u.get("completion_sentinel") != "SUCCESS:" + u.get("id", ""):
        fails.append("%s sentinel mismatch" % u.get("id"))
    if u.get("phase") not in PHASES:
        fails.append("%s bad phase %r" % (u.get("id"), u.get("phase")))
    if u.get("execution_substrate") not in SUBS:
        fails.append("%s bad substrate %r" % (u.get("id"), u.get("execution_substrate")))
    q = u.get("question_or_target", "")
    if "?" not in q:
        fails.append("%s question_or_target has no interrogative" % u.get("id"))
    if len(q) < 120:
        warns.append("%s question_or_target short (%d chars)" % (u.get("id"), len(q)))
    if not any(t.lower().startswith("negative control") or "negative control" in t.lower()
               or "control" in t.lower() or "mutation" in t.lower()
               for t in u.get("tests_required", [])):
        fails.append("%s has no negative control / mutation test" % u.get("id"))

# phase histogram + substrate histogram
ph = {}
sb = {}
oa = 0
for u in data:
    ph[u["phase"]] = ph.get(u["phase"], 0) + 1
    sb[u["execution_substrate"]] = sb.get(u["execution_substrate"], 0) + 1
    if u["owner_approval_required"]:
        oa += 1
print("PHASES %s" % sorted(ph.items()))
print("SUBSTRATES %s" % sorted(sb.items()))
print("OWNER_APPROVAL_TRUE %d" % oa)
print("DISTINCT_TIMEOUTS %s" % sorted(set(u["timeout_seconds"] for u in data)))
print("DISTINCT_RETRY %d" % len(set(u["retry_policy"] for u in data)))
print("DISTINCT_REVIEWER %d" % len(set(u["reviewer_requirement"] for u in data)))
print("DISTINCT_OUTPUT_SCHEMA %d" % len(set(u["output_schema"] for u in data)))
print("DISTINCT_MODELS %d" % len(set(json.dumps(u["assigned_model_vendor_role"], sort_keys=True)
                                     for u in data)))

# 8. dependencies resolve - intra-slice ids, declared bucket codes, or a SIBLING slice id
# that is proven present on disk (never assumed).
sibling_ids = {}
for fn in sorted(os.listdir(HERE)):
    if not fn.endswith(".json") or fn == "IMP-3.json":
        continue
    try:
        o = json.loads(io.open(os.path.join(HERE, fn), encoding="utf-8").read())
    except Exception:
        continue
    if isinstance(o, dict):
        o = o.get("items") or o.get("work_units") or []
    for it in o:
        if isinstance(it, dict) and it.get("id"):
            sibling_ids[it["id"]] = fn
idset = set(ids)
xrefs = {}
for u in data:
    for d in u["dependencies"]:
        if d in idset or d in BUCKETS:
            continue
        if d in sibling_ids:
            xrefs[d] = sibling_ids[d]
            continue
        fails.append("%s dependency %r unresolved (not intra-slice, not a bucket, not found in "
                     "any sibling slice on disk)" % (u["id"], d))
print("CROSS_SLICE_DEPS_RESOLVED %s" % sorted(xrefs.items()))

# 7. DETECTOR CONTROL first - prove the scanner catches a planted duplicate.
probe = [dict(data[0]), dict(data[0])]
probe[1]["id"] = "IMP-9999"
pt = [toks(x["title"] + " " + x["question_or_target"]) for x in probe]
control_hit = jac(pt[0], pt[1])
print("DETECTOR_CONTROL planted_identical_pair_jaccard=%.3f (must be >=0.90)" % control_hit)
if control_hit < 0.90:
    fails.append("DETECTOR BROKEN: planted identical pair scored %.3f" % control_hit)

# also a known-DISTINCT control so the scanner is not constant-firing
d_ctrl = jac(toks(data[0]["title"] + " " + data[0]["question_or_target"]),
             toks(data[-1]["title"] + " " + data[-1]["question_or_target"]))
print("DETECTOR_CONTROL known_distinct_pair_jaccard=%.3f (must be <0.50)" % d_ctrl)
if d_ctrl >= 0.50:
    fails.append("DETECTOR BROKEN: known-distinct pair scored %.3f" % d_ctrl)

# 5. intra-slice near-duplicate scan
tk = [toks(u["title"] + " " + u["question_or_target"]) for u in data]
pairs = []
for i in range(N):
    for j in range(i + 1, N):
        s = jac(tk[i], tk[j])
        if s >= 0.45:
            pairs.append((round(s, 3), ids[i], ids[j], data[i]["title"], data[j]["title"]))
pairs.sort(reverse=True)
print("INTRA_NEARDUP_PAIRS_ge_0.45 %d" % len(pairs))
for p in pairs[:12]:
    print("   %.3f %s | %s || %s || %s" % p)
top = max((jac(tk[i], tk[j]) for i in range(N) for j in range(i + 1, N)), default=0)
print("INTRA_MAX_PAIR_JACCARD %.3f" % top)

# 6. cross-slice scan
mine_txt = [(u["id"], u["title"], toks(u["title"] + " " + u.get("question_or_target", "")))
            for u in data]
for fn in sorted(os.listdir(HERE)):
    if not fn.endswith(".json") or fn == "IMP-3.json":
        continue
    try:
        other = json.loads(io.open(os.path.join(HERE, fn), encoding="utf-8").read())
    except Exception as exc:
        print("CROSS %s UNREADABLE %s" % (fn, exc))
        continue
    if isinstance(other, dict):
        other = other.get("items") or other.get("work_units") or []
    ot = []
    for o in other:
        if not isinstance(o, dict):
            continue
        t = o.get("title", "")
        q = o.get("question_or_target") or o.get("target") or ""
        ot.append((o.get("id"), t, toks(t + " " + q)))
    hits = []
    for mid, mt, mv in mine_txt:
        for oid, ot_, ov in ot:
            s = jac(mv, ov)
            if s >= 0.45:
                hits.append((round(s, 3), mid, oid, mt, ot_))
    hits.sort(reverse=True)
    print("CROSS %s n=%d overlaps_ge_0.45=%d  max=%.3f" % (
        fn, len(ot), len(hits),
        max([h[0] for h in hits]) if hits else 0.0))
    for h in hits[:6]:
        print("     %.3f %s vs %s | %s || %s" % h)

print("")
print("WARNINGS %d" % len(warns))
for w in warns[:10]:
    print("  warn: %s" % w)
print("FAILURES %d" % len(fails))
for f in fails[:25]:
    print("  FAIL: %s" % f)
sys.exit(1 if fails else 0)
