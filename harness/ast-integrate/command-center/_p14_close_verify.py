"""Phase 14: independently re-measure the two Wave-3 items my brief says are OPEN.

D4 -- workflow-id collisions across platform/workflows/**/*.json.
D1 -- the 45-row vendor-identity matrix: how many rows are NOT-COMPUTABLE today.

Detector controls run FIRST and must both fire, else the counts are void.
"""
import collections
import json
import os
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
WF = os.path.join(REPO, "platform", "workflows")
CC = os.path.join(REPO, "command-center")

out = {"probe": "p14-close-verify"}

# ---------------- D4: workflow id uniqueness ----------------
ids = collections.defaultdict(list)
n_files = 0
n_unparsed = 0
for root, dirs, files in os.walk(WF):
    for f in files:
        if not f.endswith(".json"):
            continue
        p = os.path.join(root, f)
        rel = os.path.relpath(p, REPO).replace("\\", "/")
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as exc:
            n_unparsed += 1
            continue
        n_files += 1
        if isinstance(d, dict):
            wid = d.get("workflow_id") or d.get("id")
            if wid:
                ids[wid].append(rel)

dupes = {k: v for k, v in ids.items() if len(v) > 1}

# DETECTOR CONTROL: inject a known duplicate into a COPY of the mapping and prove
# the same grouping logic finds it. A duplicate-finder that cannot find a planted
# duplicate cannot certify zero.
ctl = collections.defaultdict(list, {k: list(v) for k, v in ids.items()})
planted_id = "P14-PLANTED-DUPLICATE-ID"
ctl[planted_id] = ["a/one.json", "b/two.json"]
ctl_dupes = {k: v for k, v in ctl.items() if len(v) > 1}
control_ok = planted_id in ctl_dupes

out["d4"] = {
    "files_parsed": n_files,
    "files_unparseable": n_unparsed,
    "distinct_ids": len(ids),
    "duplicate_groups": len(dupes),
    "duplicates": dupes,
    "detector_control_finds_planted_duplicate": control_ok,
    "verdict": ("CONTROL BROKEN" if not control_ok
                else ("D4 CLOSED - 0 duplicate workflow ids" if not dupes
                      else "D4 OPEN - %d duplicate group(s)" % len(dupes))),
}

# The two specific paths my brief names.
for name in ("fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json",
             "fused.cnc07-arc05.workflow.json"):
    hits = []
    for root, dirs, files in os.walk(WF):
        if name in files:
            hits.append(os.path.relpath(os.path.join(root, name), REPO).replace("\\", "/"))
    out["d4"].setdefault("briefed_paths", {})[name] = hits or "ABSENT"

# ---------------- D1: the 45-row matrix, today ----------------
after = os.path.join(CC, "D1-CLOSE-MATRIX.after.json")
if os.path.isfile(after):
    d = json.load(open(after, encoding="utf-8"))
    rows = d.get("rows") if isinstance(d, dict) else d
    if isinstance(rows, list):
        tally = collections.Counter()
        for r in rows:
            if isinstance(r, dict):
                v = (r.get("verdict") or r.get("result") or r.get("predicate")
                     or r.get("after") or "?")
                tally[str(v)] += 1
        out["d1_after_matrix"] = {
            "source": "command-center/D1-CLOSE-MATRIX.after.json",
            "n_rows": len(rows),
            "verdict_tally": dict(tally),
            "top_level_keys": list(d.keys()) if isinstance(d, dict) else None,
        }
    else:
        out["d1_after_matrix"] = {"shape": "unexpected",
                                  "top_level_keys": list(d.keys()) if isinstance(d, dict) else None}
else:
    out["d1_after_matrix"] = "ABSENT"

print(json.dumps(out, indent=2)[:6000])
json.dump(out, open(os.path.join(CC, "P14-CLOSE-VERIFY.json"), "w", encoding="utf-8"), indent=2)
