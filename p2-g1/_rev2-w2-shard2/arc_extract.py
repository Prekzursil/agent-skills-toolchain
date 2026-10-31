"""Extract reviewer-relevant structure from ARC artifacts (read-only)."""
import json
import os

REPO = r"C:/Users/Prekzursil/p2-g1"
IDS = ["ARC-0012", "ARC-0015", "ARC-0021", "ARC-0048",
       "ARC-0001", "ARC-0013", "ARC-0019", "ARC-0020", "ARC-0047"]
CAT = {u["id"]: u for u in json.load(
    open(os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json"),
         encoding="utf-8"))["work_units"]}

for uid in IDS:
    p = os.path.join(REPO, CAT[uid]["output_path"].replace("/", os.sep))
    doc = json.load(open(p, encoding="utf-8"))
    print("=" * 20, uid, "=" * 20)
    print(" top-level keys:", sorted(doc.keys()))
    for k in ("title", "question", "question_or_target", "scope", "targets",
              "verdict", "overall_verdict", "state", "status", "answer",
              "headline_answer"):
        if k in doc:
            v = json.dumps(doc[k], ensure_ascii=False)
            print(" %s: %s" % (k, v[:400]))
    # enumerated lists that look like failure modes / findings / risks
    for k, v in doc.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            labels = set()
            for row in v[:200]:
                if isinstance(row, dict):
                    for lk in ("id", "name", "class", "mode", "title", "kind"):
                        if lk in row:
                            labels.add(str(row[lk])[:60])
            if labels:
                print(" list[%s] n=%d labels(~%d): %s" % (
                    k, len(v), len(labels), sorted(labels)[:12]))
    # seeded classes references
    txt = json.dumps(doc)
    for needle in ("47", "seeded", "seed"):
        if needle in txt:
            idx = txt.find(needle)
            print(" mention[%s]: ...%s..." % (needle, txt[max(0, idx - 80):idx + 120]))
    print()
