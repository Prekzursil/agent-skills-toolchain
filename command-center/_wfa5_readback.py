"""build/wfa-5 : read the emitted registry back off disk and verify it.

Checks (all mechanical):
  1. the file parses and is a JSON array; count it
  2. ids and names are unique; ids are contiguous WFC-0129..WFC-0160
  3. every classification is in the 15-term spec vocabulary
  4. every provenance.primary_anchor re-resolves: the file exists AND the cited line exists
     (the cited line text is printed for the first few so a reader can spot-check)
  5. every record carries the required spec fields, non-empty
  6. no id or name collides with a sibling registry (workflow-candidates-1..4)
  7. NEGATIVE CONTROL: a deliberately corrupted copy must FAIL checks 3, 4 and 5
"""

import copy
import glob
import json
import os
import sys

REG = "C:/Users/Prekzursil/source/ast-integrate/platform/registry"
OUT = os.path.join(REG, "workflow-candidates-5.json")

VOCAB = {
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
}
REQUIRED = [
    "id",
    "name",
    "provenance",
    "license",
    "maintenance_state",
    "task_fit",
    "tools",
    "failure_behaviour",
    "benchmark_evidence",
    "classification",
    "classification_basis",
    "distinctness",
]
# these two MAY be legitimately empty (a candidate with no declared roles / no stop rule is
# itself a finding the spec asks for) but an empty list MUST carry an explicit NONE-FOUND
# statement naming the detector, so silence can never pass as a measurement
EMPTY_ALLOWED_WITH_STATEMENT = {
    "roles": "roles_measurement",
    "stop_rules": "stop_rules_measurement",
    "stages": "stage_source",
}


def check(records, label):
    errs = []
    if not isinstance(records, list):
        return ["not a JSON array"]
    ids = [r.get("id") for r in records]
    names = [r.get("name") for r in records]
    if len(set(ids)) != len(ids):
        errs.append("duplicate ids")
    if len(set(names)) != len(names):
        errs.append("duplicate names")
    expect = ["WFC-%04d" % i for i in range(129, 161)]
    if label == "live" and ids != expect:
        errs.append("ids are not exactly WFC-0129..WFC-0160 in order")
    for r in records:
        rid = r.get("id")
        if r.get("classification") not in VOCAB:
            errs.append(
                "%s: classification %r not in the 15-term vocabulary"
                % (rid, r.get("classification"))
            )
        for k in REQUIRED:
            v = r.get(k)
            if v in (None, "", [], {}):
                errs.append("%s: required field %s is empty" % (rid, k))
        for k, stmt in EMPTY_ALLOWED_WITH_STATEMENT.items():
            if k not in r:
                errs.append("%s: field %s is absent entirely" % (rid, k))
                continue
            if not r.get(k) and "NONE FOUND" not in str(r.get(stmt, "")):
                errs.append(
                    "%s: %s is empty and %s does not state NONE FOUND with its detector"
                    % (rid, k, stmt)
                )
        anchor = (r.get("provenance") or {}).get("primary_anchor") or ""
        p, _, ln = anchor.rpartition(":")
        if not p or not ln.isdigit():
            errs.append(
                "%s: provenance.primary_anchor is not path:line -> %r" % (rid, anchor)
            )
            continue
        if not os.path.isfile(p):
            errs.append("%s: anchor file does not exist -> %s" % (rid, p))
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        if int(ln) < 1 or int(ln) > len(lines):
            errs.append(
                "%s: anchor line %s out of range (file has %d lines)"
                % (rid, ln, len(lines))
            )
    return errs


with open(OUT, encoding="utf-8") as fh:
    raw = fh.read()
records = json.loads(raw)
print("file            :", OUT)
print("bytes on disk   :", len(raw))
print("array length    :", len(records))
print("ids             :", records[0]["id"], "..", records[-1]["id"])

errs = check(records, "live")
print("LIVE violations :", len(errs))
for e in errs[:10]:
    print("   ", e)

print()
print("anchor spot-check (re-opened from disk):")
for r in records[:3] + records[-2:]:
    anchor = r["provenance"]["primary_anchor"]
    p, _, ln = anchor.rpartition(":")
    with open(p, encoding="utf-8", errors="replace") as fh:
        line = fh.read().splitlines()[int(ln) - 1]
    print(
        "   %-11s %s -> %s"
        % (r["id"], anchor.replace("C:/Users/Prekzursil", "~"), line.strip()[:70])
    )

# ---- 6. sibling collision check ----
sib_ids, sib_names = set(), set()
for p in sorted(glob.glob(os.path.join(REG, "workflow-candidates-*.json"))):
    if p.endswith("workflow-candidates-5.json"):
        continue
    try:
        arr = json.load(open(p, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print("sibling unparseable:", p, exc)
        continue
    if isinstance(arr, list):
        for x in arr:
            if isinstance(x, dict):
                sib_ids.add(str(x.get("id")))
                sib_names.add(str(x.get("name")))
print()
print(
    "sibling registries read:",
    len(glob.glob(os.path.join(REG, "workflow-candidates-*.json"))) - 1,
)
print(
    "id collisions with siblings   :", sorted(set(r["id"] for r in records) & sib_ids)
)
print(
    "name collisions with siblings :",
    sorted(set(r["name"] for r in records) & sib_names),
)

# ---- 7. NEGATIVE CONTROL (both-states test) ----
bad = copy.deepcopy(records)
bad[0]["classification"] = "SHIP-IT"
bad[1]["provenance"]["primary_anchor"] = "C:/nope/does-not-exist.md:1"
bad[2]["provenance"]["primary_anchor"] = (
    bad[2]["provenance"]["primary_anchor"].rpartition(":")[0] + ":999999"
)
bad[3]["license"] = {}
bad[4]["stages"] = []
bad[4]["stage_source"] = (
    "measured from the SKILL.md itself"  # empty list, no NONE FOUND
)
bad_errs = check(bad, "mutated")
kinds = {
    "bad-vocabulary": any("not in the 15-term" in e for e in bad_errs),
    "absent-anchor-file": any("does not exist" in e for e in bad_errs),
    "anchor-line-out-of-range": any("out of range" in e for e in bad_errs),
    "empty-required-field": any(
        "required field license is empty" in e for e in bad_errs
    ),
    "empty-list-without-none-found": any(
        "stages is empty and stage_source does not state NONE FOUND" in e
        for e in bad_errs
    ),
}
print()
print("NEGATIVE CONTROL violations:", len(bad_errs), kinds)
ok = not errs and all(kinds.values()) and len(records) == 32
print()
print(
    (
        "SUCCESS:build/wfa-5 registry=%d candidates, 0 violations, %d/%d mutation classes caught"
        % (len(records), sum(1 for v in kinds.values() if v), len(kinds))
    )
    if ok
    else "FAILED:build/wfa-5 see violations above"
)
sys.exit(0 if ok else 1)
