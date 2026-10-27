"""Verifier for AUD-1.json. Reads the file OFF DISK. Includes a planted-mutant control for the
near-duplicate detector so a 'zero duplicates' verdict is not a silent detector failure."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "AUD-1.json")

MANDATORY = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
             "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
             "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
             "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
             "failure_classification", "owner_approval_required"]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9", "10", "11",
          "12", "13", "14", "15", "16"}
SUBS = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}

raw = open(P, encoding="utf-8").read()
units = json.loads(raw)
fail = []
print("parsed_ok=True  units_on_disk=%d  bytes=%d" % (len(units), len(raw)))

# 1 - field completeness, per unit, no reliance on any global defaults block
for un in units:
    for f in MANDATORY:
        if f not in un:
            fail.append("%s MISSING FIELD %s" % (un.get("id"), f))
        else:
            v = un[f]
            if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
                if f != "owner_approval_required":
                    fail.append("%s EMPTY FIELD %s" % (un["id"], f))
    if not isinstance(un.get("owner_approval_required"), bool):
        fail.append("%s owner_approval_required not bool" % un["id"])
    if un.get("phase") not in PHASES:
        fail.append("%s bad phase %r" % (un["id"], un.get("phase")))
    if un.get("execution_substrate") not in SUBS:
        fail.append("%s bad substrate %r" % (un["id"], un.get("execution_substrate")))
    if not isinstance(un.get("timeout_seconds"), int) or un["timeout_seconds"] <= 0:
        fail.append("%s bad timeout" % un["id"])
    a = un.get("assigned_model_vendor_role")
    if not (isinstance(a, dict) and {"model", "vendor", "role"} <= set(a)):
        fail.append("%s assignment not {model,vendor,role}" % un["id"])

# 2 - id format / uniqueness / sequence
ids = [u["id"] for u in units]
if len(set(ids)) != len(ids):
    fail.append("DUPLICATE IDS")
exp = ["AUD-%04d" % i for i in range(1, len(units) + 1)]
if ids != exp:
    fail.append("IDS NOT SEQUENTIAL FROM 1: first mismatch %s" %
                next((i for i, (x, y) in enumerate(zip(ids, exp)) if x != y), "n/a"))

# 3 - dependency integrity
known = set(ids) | {"B%02d" % n for n in range(1, 14)}
for un in units:
    for d in un["dependencies"]:
        if d not in known:
            fail.append("%s unknown dependency %s" % (un["id"], d))
    if un["id"] in un["dependencies"]:
        fail.append("%s self-dependency" % un["id"])

# 4 - question_or_target must be a question or an imperative target, never a bare topic
for un in units:
    t = un["question_or_target"].strip()
    if "?" not in t and not re.match(r"^(Write|Create|Run|Execute|Extract|Map|Verify|Capture|"
                                     r"Build|Produce|Measure|Enumerate)\b", t):
        fail.append("%s question_or_target is not a question or imperative target" % un["id"])

# 5 - substrate doctrine check. IMPORTANT: scope the detector to the OPERATIONAL fields
#     (inputs + evidence_requirement = what the unit READS and RUNS), never to
#     question_or_target, which merely DESCRIBES what is being looked for. Scanning the
#     question field produced a use-vs-mention false positive on the package-content unit
#     (it searches a build output for credentials; it does not use one).
LIVE = re.compile(r"PowerShell|pwsh7|Git Bash|git-bash|process table|scheduled task|cockpit|"
                  r"credential-file|credential reads|~/\.claude|~/\.agents|live harness|"
                  r"clean or sandboxed Windows user profile", re.I)
subs_viol = []
for un in units:
    operational = " ".join(un["inputs"]) + " " + un["evidence_requirement"]
    if LIVE.search(operational) and un["execution_substrate"] != "local-serialized":
        subs_viol.append(un["id"])
        fail.append("%s substrate=%s but its OPERATIONAL fields name a live/Windows/credentialed "
                    "probe" % (un["id"], un["execution_substrate"]))
# detector control for check 5: it must FIRE on a planted violation and be SILENT on a clean unit.
# The planted mutant must be a unit that ACTUALLY names a live/Windows probe - planting on a
# unit that legitimately does not match tests nothing (this control failed that way once).
planted = dict(next(u for u in units
                    if LIVE.search(" ".join(u["inputs"]) + " " + u["evidence_requirement"])))
planted["execution_substrate"] = "cloud-batch"
fires = bool(LIVE.search(" ".join(planted["inputs"]) + " " + planted["evidence_requirement"])) \
    and planted["execution_substrate"] != "local-serialized"
print("   (planted mutant = %s, flipped local-serialized -> cloud-batch)" % planted["id"])
clean = next(u for u in units if u["execution_substrate"] == "local-parallel")
silent = not (LIVE.search(" ".join(clean["inputs"]) + " " + clean["evidence_requirement"])
              and clean["execution_substrate"] != "local-serialized")
print("SUBSTRATE DETECTOR CONTROL: fires_on_planted=%s silent_on_clean(%s)=%s -> %s"
      % (fires, clean["id"], silent, "PASS" if (fires and silent) else "FAIL"))
if not (fires and silent):
    fail.append("SUBSTRATE DETECTOR CONTROL FAILED - a clean substrate verdict is meaningless")

# 5b - executor/reviewer vendor independence: an openai-executed unit may not have a
#      Codex-only reviewer, because that reviewer shares the executor's blind spots
for un in units:
    if un["assigned_model_vendor_role"]["vendor"] == "openai" and \
            "cross-vendor Codex reviewer who re-runs" in un["reviewer_requirement"]:
        fail.append("%s executed by openai but reviewed by a Codex-only reviewer" % un["id"])

# 6 - NEAR-DUPLICATE DETECTOR, with a planted-mutant control (detector control, honesty rule 6)
STOP = set("the a an of to and or for is are in on by that which with each every this it its not "
           "what does do so as at from than then their there be been was were will would can "
           "must may per any all one two both".split())


def toks(u):
    s = (u["title"] + " " + u["question_or_target"]).lower()
    return {w for w in re.findall(r"[a-z0-9]{3,}", s) if w not in STOP}


def jac(x, y):
    return len(x & y) / len(x | y) if (x | y) else 0.0


T = [toks(u) for u in units]
pairs = []
for i in range(len(units)):
    for j in range(i + 1, len(units)):
        s = jac(T[i], T[j])
        if s >= 0.40:
            pairs.append((round(s, 3), units[i]["id"], units[j]["id"],
                          units[i]["title"][:52], units[j]["title"][:52]))
pairs.sort(reverse=True)

# control: plant an exact clone and a reworded clone of unit 1; the detector MUST fire on both.
clone_exact = toks(units[0])
reworded = dict(units[0])
reworded["title"] = units[0]["title"].replace("inventory", "census").replace("Branch", "Ref")
reworded["question_or_target"] = units[0]["question_or_target"].replace("branch", "ref")
ctrl_exact = jac(clone_exact, T[0])
ctrl_reword = jac(toks(reworded), T[0])
# negative control: two units known to be about different lanes must score low
neg = jac(T[0], T[len(units) - 1])
ctrl_ok = ctrl_exact >= 0.99 and ctrl_reword >= 0.60 and neg < 0.40
print("DETECTOR CONTROL: exact_clone=%.3f (need >=0.99)  reworded_clone=%.3f (need >=0.60)  "
      "cross_lane_negative=%.3f (need <0.40)  -> %s"
      % (ctrl_exact, ctrl_reword, neg, "PASS" if ctrl_ok else "FAIL"))
if not ctrl_ok:
    fail.append("DEDUP DETECTOR CONTROL FAILED - a zero-duplicate verdict would be meaningless")

print("near-duplicate pairs at Jaccard >= 0.40: %d" % len(pairs))
for p in pairs[:15]:
    print("   ", p)
top = sorted((jac(T[i], T[j]), units[i]["id"], units[j]["id"])
             for i in range(len(units)) for j in range(i + 1, len(units)))[-3:]
print("highest 3 similarities overall:", [(round(s, 3), a, b) for s, a, b in top])

# 7 - distribution reporting (proves fields are per-unit, not a single global default)
def dist(key, get):
    from collections import Counter
    c = Counter(get(u) for u in units)
    return dict(c)


print("phase:", dist("phase", lambda u: u["phase"]))
print("substrate:", dist("sub", lambda u: u["execution_substrate"]))
print("timeout distinct values:", sorted({u["timeout_seconds"] for u in units}))
print("assignment distinct:", sorted({"%s/%s/%s" % (u["assigned_model_vendor_role"]["model"],
                                                    u["assigned_model_vendor_role"]["vendor"],
                                                    u["assigned_model_vendor_role"]["role"])
                                      for u in units}))
print("output_schema distinct:", len({u["output_schema"] for u in units}))
print("tool_permission sets distinct:", len({tuple(u["tool_permissions"]) for u in units}))
print("reviewer distinct:", len({u["reviewer_requirement"] for u in units}))
print("retry distinct:", len({u["retry_policy"] for u in units}))
print("evidence_requirement distinct:", len({u["evidence_requirement"] for u in units}))
print("tests_required distinct:", len({tuple(u["tests_required"]) for u in units}))
print("owner_approval_required True count:", sum(1 for u in units if u["owner_approval_required"]))
print("output_path distinct:", len({u["output_path"] for u in units}))

print()
if fail:
    print("FAILED:AUD-1of1  %d violations" % len(fail))
    for f in fail:
        print("  -", f)
    sys.exit(1)
print("SUCCESS:AUD-1of1 units=%d first=%s last=%s" % (len(units), ids[0], ids[-1]))
