"""Independent read-back verifier for TST-2.json.

Deliberately does NOT import the generator. Reads the file off disk, re-derives
every count, and runs a near-duplicate detector with a PLANTED-MUTANT control so
a "0 near-duplicates" verdict is not a silent detector failure.
"""

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "TST-2.json")

REQUIRED = [
    "id", "title", "phase", "question_or_target", "inputs", "dependencies",
    "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
    "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
    "tests_required", "reviewer_requirement", "completion_sentinel",
    "retry_policy", "failure_classification", "owner_approval_required",
]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8",
          "9", "10", "11", "12", "13", "14", "15", "16"}
SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}

STOP = set("""a an the and or of to in on for by with that this is are be as it its
into from when does do not no than then which what where must pass requires require
run runs test tests unit units case cases each every any all one two three same
against after before during over under while at any_of""".split())


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP)


def jac(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def main():
    raw = io.open(PATH, encoding="utf-8", newline="").read()
    crlf = raw.count("\r\n")
    units = json.loads(raw)
    fails = []

    print("PARSE            : OK, type=%s" % type(units).__name__)
    print("UNIT_COUNT       : %d" % len(units))
    print("BYTES            : %d" % len(raw.encode("utf-8")))
    print("CRLF_PAIRS       : %d (0 expected: LF file)" % crlf)

    ids = [u.get("id") for u in units]
    print("IDS_FIRST_LAST   : %s .. %s" % (ids[0], ids[-1]))
    if len(set(ids)) != len(ids):
        fails.append("duplicate ids")
    exp = ["TST-%04d" % i for i in range(129, 129 + len(units))]
    print("IDS_SEQUENTIAL   : %s" % (ids == exp))
    if ids != exp:
        fails.append("ids not sequential from TST-0129")

    # field completeness
    missing = {}
    empty = {}
    for u in units:
        for f in REQUIRED:
            if f not in u:
                missing.setdefault(f, []).append(u.get("id"))
            else:
                v = u[f]
                if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
                    if f != "owner_approval_required":
                        empty.setdefault(f, []).append(u.get("id"))
        extra = set(u.keys()) - set(REQUIRED)
        if extra:
            fails.append("%s has extra fields %s" % (u.get("id"), sorted(extra)))
    print("MISSING_FIELDS   : %s" % (missing or "none"))
    print("EMPTY_FIELDS     : %s" % (empty or "none"))
    if missing:
        fails.append("missing fields")
    if empty:
        fails.append("empty fields")

    # value-domain checks
    bad_phase = [u["id"] for u in units if u["phase"] not in PHASES]
    bad_sub = [u["id"] for u in units if u["execution_substrate"] not in SUBSTRATES]
    bad_sent = [u["id"] for u in units if u["completion_sentinel"] != "SUCCESS:" + u["id"]]
    bad_out = [u["id"] for u in units
               if u["output_path"] != "command-center/receipts/%s.json" % u["id"]]
    bad_to = [u["id"] for u in units if not isinstance(u["timeout_seconds"], int)
              or u["timeout_seconds"] < 300]
    bad_who = [u["id"] for u in units
               if sorted(u["assigned_model_vendor_role"].keys()) != ["model", "role", "vendor"]
               or not all(u["assigned_model_vendor_role"].values())]
    bad_oa = [u["id"] for u in units if not isinstance(u["owner_approval_required"], bool)]
    for label, lst in [("phase", bad_phase), ("substrate", bad_sub), ("sentinel", bad_sent),
                       ("output_path", bad_out), ("timeout", bad_to), ("assignment", bad_who),
                       ("owner_approval", bad_oa)]:
        print("BAD_%-13s: %s" % (label.upper(), lst or "none"))
        if lst:
            fails.append("bad " + label)

    # tests_required must be a non-empty list of non-empty strings
    bad_tests = [u["id"] for u in units
                 if not isinstance(u["tests_required"], list) or len(u["tests_required"]) < 1
                 or any((not isinstance(t, str)) or len(t) < 20 for t in u["tests_required"])]
    print("BAD_TESTS        : %s" % (bad_tests or "none"))
    if bad_tests:
        fails.append("bad tests_required")

    # distributions
    def dist(key, get):
        d = {}
        for u in units:
            d[get(u)] = d.get(get(u), 0) + 1
        print("%-17s: %s" % (key, sorted(d.items(), key=lambda kv: -kv[1])))

    dist("DIST_SUBSTRATE", lambda u: u["execution_substrate"])
    dist("DIST_PHASE", lambda u: u["phase"])
    dist("DIST_VENDOR", lambda u: u["assigned_model_vendor_role"]["vendor"])
    dist("DIST_ROLE", lambda u: u["assigned_model_vendor_role"]["role"])
    dist("DIST_TIMEOUT", lambda u: u["timeout_seconds"])
    print("OWNER_APPROVAL   : %d of %d -> %s"
          % (sum(1 for u in units if u["owner_approval_required"]), len(units),
             [u["id"] for u in units if u["owner_approval_required"]]))

    # dependency sanity: intra-slice deps must exist
    idset = set(ids)
    baddep = []
    for u in units:
        for dep in u["dependencies"]:
            if dep.startswith("TST-") and dep not in idset:
                baddep.append((u["id"], dep))
            if dep.startswith("TST-") and dep >= u["id"]:
                baddep.append((u["id"], dep + " (forward/self dep)"))
    print("BAD_DEPS         : %s" % (baddep or "none"))
    if baddep:
        fails.append("bad dependencies")

    # --- near-duplicate detector, with a PLANTED-MUTANT control -------------
    sigs = [(u["id"], toks(u["title"] + " " + u["question_or_target"])) for u in units]

    # control 1: an exact clone of unit 0 must be caught
    clone = ("CONTROL-CLONE", set(sigs[0][1]))
    # control 2: a paraphrase (drop 25% of tokens) must be caught
    keep = sorted(sigs[1][1])
    para = ("CONTROL-PARAPHRASE", set(keep[: int(len(keep) * 0.75)]))
    ctl = [(clone[0], jac(clone[1], sigs[0][1])), (para[0], jac(para[1], sigs[1][1]))]
    print("DETECTOR_CONTROL : %s (both must be >= 0.60)"
          % [(n, round(v, 3)) for n, v in ctl])
    if any(v < 0.60 for _, v in ctl):
        fails.append("near-duplicate detector failed its own control")

    pairs = []
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            s = jac(sigs[i][1], sigs[j][1])
            if s >= 0.45:
                pairs.append((round(s, 3), sigs[i][0], sigs[j][0]))
    pairs.sort(reverse=True)
    print("NEARDUP_>=0.45   : %d  %s" % (len(pairs), pairs[:12]))
    top = sorted(
        [(round(jac(sigs[i][1], sigs[j][1]), 3), sigs[i][0], sigs[j][0])
         for i in range(len(sigs)) for j in range(i + 1, len(sigs))],
        reverse=True)[:8]
    print("TOP8_SIMILAR     : %s" % top)
    if pairs:
        fails.append("near-duplicates at or above 0.45")

    print("")
    print("VERDICT          : %s" % ("FAILED: " + "; ".join(fails) if fails else "SUCCESS"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
