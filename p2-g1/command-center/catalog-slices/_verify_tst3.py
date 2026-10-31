"""Verification for TST-3.json. Read-only: reads the artifact back off disk and
never rewrites it.

Four checks, in this order:
  1. STRUCTURE  - parse from disk, count, id sequence, 19 fields, enum domains.
  2. DETECTOR CONTROL - plant exact-rename / paraphrase / full-rewrite mutants
     against real TST-3 units and report which classes the lexical Jaccard
     detector FIRES on. A clean corpus reading is worthless without this: a
     detector silent in both states measures nothing.
  3. CROSS-SLICE (json)  - TST-3 vs every sibling slice JSON present on disk.
  4. CROSS-SLICE (tst-2) - TST-2.json does not exist yet, so compare against the
     string constants of its GENERATOR via ast.parse (no execution, no writes).
     This is a mechanically different probe than (3) and is reported separately.
"""
import ast
import json
import math
import os
import re
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
THRESH = 0.55

STOP = set(("the a an and or of to in for that this with must be is are on by not it its as at "
            "from into then than which what when where unit units work spec target question "
            "implementation council test tests every each must-be").split())


def toks(t):
    return {w for w in re.findall(r"[a-z0-9_.-]{3,}", t.lower()) if w not in STOP}


def jac(a, b):
    ta, tb = toks(a), toks(b)
    return len(ta & tb) / max(1, len(ta | tb))


def text(u):
    return u["title"] + " " + u["question_or_target"]


# ------------------------------------------------------------------ 1. STRUCTURE
path = os.path.join(HERE, "TST-3.json")
raw = open(path, encoding="utf-8").read()
units = json.loads(raw)

KEYS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
        "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
        "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
        "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
        "failure_classification", "owner_approval_required"]
SUBS = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9",
          "10", "11", "12", "13", "14", "15", "16"}

ids = [u["id"] for u in units]
expected = ["TST-%04d" % n for n in range(257, 257 + len(units))]
problems = []
if ids != expected:
    problems.append("id sequence mismatch")
for u in units:
    if list(u.keys()) != KEYS:
        problems.append("%s field drift: %s" % (u["id"], set(u.keys()) ^ set(KEYS)))
    if u["phase"] not in PHASES:
        problems.append("%s bad phase %s" % (u["id"], u["phase"]))
    if u["execution_substrate"] not in SUBS:
        problems.append("%s bad substrate" % u["id"])
    for f in ("title", "question_or_target", "evidence_requirement", "reviewer_requirement",
              "retry_policy", "output_path", "output_schema", "completion_sentinel"):
        if not isinstance(u[f], str) or len(u[f].strip()) < 8:
            problems.append("%s thin field %s" % (u["id"], f))
    for f in ("inputs", "dependencies", "tool_permissions", "tests_required",
              "failure_classification"):
        if not isinstance(u[f], list):
            problems.append("%s %s not a list" % (u["id"], f))

print("1. STRUCTURE")
print("   file bytes            : %d" % len(raw.encode("utf-8")))
print("   units parsed off disk : %d" % len(units))
print("   first / last id       : %s / %s" % (ids[0], ids[-1]))
print("   unique ids            : %d" % len(set(ids)))
print("   19-field conformance  : %s" % ("PASS" if not problems else "FAIL"))
for p in problems[:10]:
    print("     - " + p)

phases = {}
subs = {}
for u in units:
    phases[u["phase"]] = phases.get(u["phase"], 0) + 1
    subs[u["execution_substrate"]] = subs.get(u["execution_substrate"], 0) + 1
print("   phases                : %s" % dict(sorted(phases.items())))
print("   substrates            : %s" % dict(sorted(subs.items())))
print("   owner_approval=true   : %d (%s)"
      % (sum(1 for u in units if u["owner_approval_required"]),
         ", ".join(u["id"] for u in units if u["owner_approval_required"])))
print("   timeout range         : %d..%d s"
      % (min(u["timeout_seconds"] for u in units), max(u["timeout_seconds"] for u in units)))

# --------------------------------------------------------- 2. DETECTOR CONTROL
by_id = {u["id"]: u for u in units}

# Mutant 1: EXACT RENAME of TST-0262 (title replaced, body byte-identical).
m1 = ("A different heading for the same job " + by_id["TST-0262"]["question_or_target"])
# Mutant 2: PARAPHRASE of TST-0287 (same mechanism, reworded, some vocab retained).
# NOTE: an earlier revision of this file compared m2 against TST-0290 and m3 against
# TST-0332 - different units entirely - and duly reported SILENT. That is the
# compare-two-different-files detector shape, not a finding about the detector.
m2 = ("Score how well the panel confidence matches reality. Build the pipeline that resolves each "
      "forecast against the outcome that later occurred and grade it with Brier and logarithmic "
      "scoring plus a reliability plot. Being right often is not the same as being calibrated, and "
      "a confidence report that is never resolved against outcomes is ornamental.")
# Mutant 3: FULL REWRITE of TST-0327 (same mechanism, vocabulary deliberately swapped).
m3 = ("Stop believing a suite that never went red. For each registered group of checks, look up "
      "whether the deliberate breakage it claims to own has ever actually been observed to trip "
      "it, and count a group as protected only when that trip was recorded. A breakage that is "
      "described but never executed is the same as none at all.")

controls = [("exact-rename", "TST-0262", m1),
            ("paraphrase", "TST-0287", m2),
            ("full-rewrite", "TST-0327", m3)]

print()
print("2. DETECTOR CONTROL (lexical Jaccard, threshold %.2f)" % THRESH)
fired = []
for name, tid, mutant in controls:
    s = jac(text(by_id[tid]), mutant)
    verdict = "FIRES" if s >= THRESH else "SILENT"
    fired.append((name, verdict))
    print("   %-13s vs %s : %.3f -> %s" % (name, tid, s, verdict))

pairs = sorted(((jac(text(a), text(b)), a["id"], b["id"])
                for a, b in combinations(units, 2)), reverse=True)
print("   clean corpus max              : %.3f -> %s (%s ~ %s)"
      % (pairs[0][0], "FIRES" if pairs[0][0] >= THRESH else "SILENT (expected)",
         pairs[0][1], pairs[0][2]))
print("   pairs >= %.2f                  : %d" % (THRESH, sum(1 for p in pairs if p[0] >= THRESH)))
print("   SCOPE: this detector is LEXICAL. Any class marked SILENT above is a class the clean")
print("          %.3f reading does NOT rule out." % pairs[0][0])

# ------------------------------------------- 2b. SECOND, INDEPENDENT DETECTOR
# Detector 1 above is unweighted Jaccard over title+question_or_target and is
# proven SILENT on paraphrase. A second signal must be mechanically different,
# not the same probe re-run: this one uses a DIFFERENT FIELD SET (the whole unit
# record incl. tests_required and evidence_requirement) and DIFFERENT WEIGHTING
# (idf-weighted cosine), so shared boilerplate is discounted and rare, distinctive
# tokens dominate. Two units that are the same mechanism reworded still share
# their rare tokens; that is the class detector 1 cannot see.


def fulltext(u):
    return " ".join([u["title"], u["question_or_target"], u["evidence_requirement"],
                     " ".join(u["tests_required"])])


docs = {u["id"]: toks(fulltext(u)) for u in units}
N = len(docs)
df = {}
for tset in docs.values():
    for w in tset:
        df[w] = df.get(w, 0) + 1
idf = {w: math.log(N / (1 + c)) + 1.0 for w, c in df.items()}


def cos_idf(ta, tb):
    inter = ta & tb
    if not inter:
        return 0.0
    num = sum(idf.get(w, 1.0) ** 2 for w in inter)
    na = math.sqrt(sum(idf.get(w, 1.0) ** 2 for w in ta))
    nb = math.sqrt(sum(idf.get(w, 1.0) ** 2 for w in tb))
    return num / (na * nb) if na and nb else 0.0


T2 = 0.55
print()
print("2b. SECOND DETECTOR (idf-weighted cosine over the FULL record, threshold %.2f)" % T2)
for name, tid, mutant in controls:
    s = cos_idf(docs[tid], toks(mutant))
    print("   %-13s vs %s : %.3f -> %s" % (name, tid, s, "FIRES" if s >= T2 else "SILENT"))
p2 = sorted(((cos_idf(docs[a["id"]], docs[b["id"]]), a["id"], b["id"])
             for a, b in combinations(units, 2)), reverse=True)
print("   clean corpus max              : %.3f -> %s (%s ~ %s)"
      % (p2[0][0], "FIRES" if p2[0][0] >= T2 else "SILENT (expected)", p2[0][1], p2[0][2]))
print("   pairs >= %.2f                  : %d" % (T2, sum(1 for p in p2 if p[0] >= T2)))
print("   top 5 closest pairs under detector 2:")
for s, x, y in p2[:5]:
    print("      %.3f  %s ~ %s" % (s, x, y))

# --------------------------------------------- 2c. PARAPHRASE SEPARATION BAND
# Neither detector FIRES at 0.55 on a paraphrase, so a threshold pass proves
# nothing about that class. What CAN be measured without a threshold: where does
# a known paraphrase actually SCORE, versus the highest score any real pair in
# the slice reaches? If every planted paraphrase lands clearly above the observed
# clean maximum, then a paraphrase pair hiding inside the slice would have
# surfaced at the top of the ranking. Three planted paraphrases, not one, so the
# floor is a band rather than a single point.
PARA = {
    # paraphrase of TST-0287 (calibration report scoring) - reused from m2
    "TST-0287": m2,
    # paraphrase of TST-0308 (Goodhart probe)
    "TST-0308": (
        "Catch a score that climbs while the thing it stands in for gets worse. Pair each headline "
        "figure with a separate verdict on the same runs that is not derived from the figure, and "
        "watch how tightly the two track each other as the system is tuned. When that relationship "
        "weakens over successive rounds of tuning, the figure has stopped describing the world and "
        "started being the objective, and the platform should escalate rather than applaud."),
    # paraphrase of TST-0344 (order-dependence detection)
    "TST-0344": (
        "Find checks that only succeed because a sibling ran ahead of them. Shuffle the execution "
        "sequence over many permutations, and whenever something breaks, narrow it down to the "
        "smallest ordered couple that reproduces the break, reporting each as leaked shared state "
        "rather than as an intermittent wobble. This is a different disease from seed sensitivity "
        "or intermittency and needs a different repair, usually a fixture mutating something "
        "global."),
}
print()
print("2c. PARAPHRASE SEPARATION BAND (no threshold; compares scores, not pass/fail)")
band = []
for tid, mut in PARA.items():
    s1 = jac(text(by_id[tid]), mut)
    s2 = cos_idf(docs[tid], toks(mut))
    band.append(s2)
    print("   paraphrase of %s : jaccard=%.3f  idf-cosine=%.3f" % (tid, s1, s2))
print("   planted paraphrase idf-cosine range : %.3f .. %.3f" % (min(band), max(band)))
print("   highest REAL pair in the slice      : %.3f (%s ~ %s)" % (p2[0][0], p2[0][1], p2[0][2]))
print("   separated                           : %s"
      % ("YES - every planted paraphrase outscores every real pair"
         if min(band) > p2[0][0] else
         "NO - a real pair reaches into the paraphrase band; inspect it by hand"))

# ------------------------------------- 2d. AUTHOR-NOMINATED CLOSE PAIRS
# The detectors rank by VOCABULARY. Two units can be the same mechanism with
# little shared vocabulary, which is exactly the class 2c failed to separate.
# So the author nominates the pairs believed closest in MECHANISM and they are
# scored explicitly. A nominated pair scoring near the corpus max is a merge
# candidate; a nominated pair scoring low means the detector cannot see it and
# the adjudication is human, which is stated rather than hidden.
NOMINATED = [
    ("TST-0266", "TST-0282", "both validate a runtime score against human labels"),
    ("TST-0265", "TST-0266", "both attack idea duplication in the brainstorm"),
    ("TST-0258", "TST-0259", "both detect a panel behaving as one voice"),
    ("TST-0306", "TST-0307", "both detect benchmark gaming"),
    ("TST-0306", "TST-0308", "symptom (shadow gap) vs proxy decay"),
    ("TST-0336", "TST-0343", "both concern nondeterministic test outcomes"),
    ("TST-0343", "TST-0344", "seed sensitivity vs order dependence"),
    ("TST-0327", "TST-0328", "negative-control census vs both-states fixture"),
    ("TST-0329", "TST-0330", "predicate conformance vs predicate differential"),
    ("TST-0348", "TST-0349", "vacuous assertions vs over-mocking"),
    ("TST-0338", "TST-0350", "coverage NOT-CHECKED vs empty-collection fail-closed"),
    ("TST-0311", "TST-0324", "loop keep-gate vs release-gate condition 8"),
]
print()
print("2d. AUTHOR-NOMINATED CLOSE PAIRS (mechanism-level suspicion, scored)")
worst_nom = 0.0
for x, y, why in NOMINATED:
    s1 = jac(text(by_id[x]), text(by_id[y]))
    s2 = cos_idf(docs[x], docs[y])
    worst_nom = max(worst_nom, s2)
    print("   %s ~ %s  jac=%.3f idf=%.3f  (%s)" % (x, y, s1, s2, why))
print("   max over nominated pairs : %.3f" % worst_nom)
print("   corpus max (all pairs)   : %.3f" % p2[0][0])
print("   NOTE: the nominated set is judgement; it bounds nothing on pairs not nominated.")

# ------------------------------------------------------- 3. CROSS-SLICE (json)
print()
print("3. CROSS-SLICE vs sibling slice JSON on disk")
mine = [(u["id"], text(u)) for u in units]
for fn in sorted(os.listdir(HERE)):
    if not fn.endswith(".json") or fn == "TST-3.json":
        continue
    try:
        other = json.loads(open(os.path.join(HERE, fn), encoding="utf-8").read())
    except Exception as exc:                                    # noqa: BLE001
        print("   %-14s UNREADABLE (%s)" % (fn, type(exc).__name__))
        continue
    if not isinstance(other, list) or not other or "title" not in other[0]:
        print("   %-14s skipped (not a unit array)" % fn)
        continue
    best = (0.0, None, None)
    for oid, otext in ((o["id"], text(o)) for o in other):
        for mid, mtext in mine:
            s = jac(mtext, otext)
            if s > best[0]:
                best = (s, mid, oid)
    print("   %-14s n=%-4d max=%.3f (%s ~ %s) -> %s"
          % (fn, len(other), best[0], best[1], best[2],
             "FIRES" if best[0] >= THRESH else "ok"))

# ------------------------------------------------- 4. CROSS-SLICE vs TST-2 gen
print()
print("4. CROSS-SLICE vs TST-2 (generator source, ast.parse - not executed)")
gen2 = os.path.join(HERE, "_gen_TST_2.py")
if not os.path.exists(gen2):
    print("   _gen_TST_2.py ABSENT -> NOT-CHECKED")
else:
    tree = ast.parse(open(gen2, encoding="utf-8").read())
    consts = [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) > 60]
    print("   string constants >60 chars extracted: %d" % len(consts))
    best = (0.0, None, None)
    for i, c in enumerate(consts):
        for mid, mtext in mine:
            s = jac(mtext, c)
            if s > best[0]:
                best = (s, mid, i)
    print("   max TST-3 unit vs TST-2 constant   : %.3f (%s ~ const#%s) -> %s"
          % (best[0], best[1], best[2], "FIRES" if best[0] >= THRESH else "ok"))
    if best[2] is not None:
        print("   closest TST-2 constant: %s" % consts[best[2]][:160].replace("\n", " "))
    print("   CAVEAT: TST-2.json does not exist, so this compares against generator SOURCE")
    print("           strings, not emitted units. Titles that the generator composes at runtime")
    print("           are invisible to this probe. TST-1 has no artifact at all -> NOT-CHECKED.")
