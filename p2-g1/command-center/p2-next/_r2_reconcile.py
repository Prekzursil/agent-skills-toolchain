"""ROUND-2: reconcile this lane's TWO instruments before publishing either number.

They disagree, and a self-contradicting pair of my own outputs is a detector failure, not a finding:

  vendor_satisfiability.py --basis committed : 42 rail-blocked / 10 satisfiable
  split_review_gate.py     --basis committed : 41 CROSS_VENDOR / 11 ANY_INDEP
  _r2_tagcensus.py                           : 114 tag occurrences
  split_review_gate.py                       : 132 tag occurrences

Resolve BOTH from the raw text -- never by vote, never by preferring my newer script.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, REPO / f"command-center/p2-next/{name}.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


vs = load("vendor_satisfiability")
sg = load("split_review_gate")

rows = vs.load_units("committed")
blobs = vs.batch_blobs("HEAD", [r["output_path"] for r in rows])
cat = json.loads(vs.batch_blobs("HEAD", [vs.CATALOG_REL])[vs.CATALOG_REL])
by_id = {u["id"]: u for u in cat["work_units"]}


# ---- (1) WHICH UNIT differs between the two splits? -------------------------------------
# BOTH STATES. The PRE-FIX call (3 args -- blocked_on never read) must still disagree on exactly
# one unit; the FIXED call (4 args) must agree on all 52. A reconciliation that only ever showed
# agreement would not prove the fix did anything.
def split_diff(pass_blocked_on: bool):
    out = []
    for r in rows:
        rec = json.loads(blobs[r["output_path"]])
        tags = sg.classification_tags(rec)
        rr = str(by_id[r["id"]].get("reviewer_requirement") or "")
        f = rec.get("failure")
        bo = f.get("blocked_on") if isinstance(f, dict) else ""
        bo = bo if isinstance(bo, str) else ""
        bucket, why = (
            sg.classify(tags, rr, sg.reason_text(rec), bo)
            if pass_blocked_on
            else sg.classify(tags, rr, sg.reason_text(rec))
        )
        mine = "CROSS_VENDOR" if r["verdict"] == vs.BLOCKED_RAIL else "ANY_INDEP"
        if bucket != mine:
            out.append((r["id"], bucket, why, mine, r["rule"], r["blocked_on"][:200]))
    return out


pre, post = split_diff(False), split_diff(True)
diff = pre
print(f"PRE-FIX  (blocked_on NOT read): {len(pre)} disagreement(s)")
for uid, b, why, mine, rule, bo in pre:
    print(f"\n  {uid}: split_review_gate={b} ({why})")
    print(f"           vendor_satisfiability={mine} ({rule})")
    print(f"     blocked_on: {bo}")
    print(
        "     ADJUDICATION: blocked_on is the unit's own operative statement of what it waits for."
    )
print(
    f"\nPOST-FIX (blocked_on read)    : {len(post)} disagreement(s) {[d[0] for d in post]}"
)
print(f"CONTROL fires_prefix={len(pre) == 1} silent_postfix={len(post) == 0}")

# ---- (2) WHERE do the extra tag occurrences come from? ----------------------------------
recursive_nodedupe = Counter()
twofield_dedup = Counter()
for r in rows:
    rec = json.loads(blobs[r["output_path"]])
    for t in sg.classification_tags(rec):
        recursive_nodedupe[t] += 1
    tags = []
    for container in (rec.get("failure") or {}, rec):
        c = container.get("classification") if isinstance(container, dict) else None
        if isinstance(c, list):
            tags += [t for t in c if isinstance(t, str)]
        elif isinstance(c, str):
            tags.append(c)
    for t in sorted(set(tags)):
        twofield_dedup[t] += 1

a, b = sum(recursive_nodedupe.values()), sum(twofield_dedup.values())
print(
    f"\ntag OCCURRENCES, recursive over every `classification` key, NOT deduped : {a}"
)
print(f"tag OCCURRENCES, failure.classification + top level, deduped per unit  : {b}")
print(
    f"difference                                                             : {a - b}"
)

# where exactly does the surplus live?
deep = Counter()
for r in rows:
    rec = json.loads(blobs[r["output_path"]])
    shallow = []
    for container in (rec.get("failure") or {}, rec):
        c = container.get("classification") if isinstance(container, dict) else None
        if isinstance(c, list):
            shallow += [t for t in c if isinstance(t, str)]
    n_all = len(sg.classification_tags(rec))
    if n_all != len(set(shallow)):
        deep[r["id"]] = n_all - len(set(shallow))
print(f"units contributing the surplus: {len(deep)}  e.g. {deep.most_common(5)}")

out = {
    "split_disagreements": [
        {
            "unit": u,
            "split_review_gate": b2,
            "why": w,
            "vendor_satisfiability": m,
            "rule": rl,
            "blocked_on": bo,
            "adjudication": "CROSS_VENDOR -- blocked_on demands a cross-vendor refuter; "
            "split_review_gate never read blocked_on",
        }
        for u, b2, w, m, rl, bo in diff
    ],
    "tag_occurrence_definitions": {
        "recursive_not_deduped": a,
        "failure_plus_toplevel_deduped": b,
        "auditor_worktree_51_units": 113,
        "note": "the occurrence sum is not one number; it is a family of numbers indexed by "
        "scope, dedupe policy and tree. That is the argument against quoting it at all.",
    },
}
(REPO / "command-center/p2-next/R2-RECONCILE.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
print("\nwrote command-center/p2-next/R2-RECONCILE.json")
