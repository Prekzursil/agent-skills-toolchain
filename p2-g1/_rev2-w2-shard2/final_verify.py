"""Final verification sweep - wave 2 shard 2.
For all 12 units: re-parse receipt, admission (C1-C4), gate A (12 conditions),
artifact presence/parse/sha-vs-manifest, untouched-receipt integrity.
Writes final_verify_out.json + console table.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, r"C:/Users/Prekzursil/p2-g1/platform/lib")
import receipt_schema_gate as gate  # noqa: E402

REPO = r"C:/Users/Prekzursil/p2-g1"
IDS = ["ADV-0124", "ADV-0127", "ADV-0128", "ARC-0001", "ARC-0012", "ARC-0013",
       "ARC-0015", "ARC-0019", "ARC-0020", "ARC-0021", "ARC-0047", "ARC-0048"]
CLOSED = ["ADV-0124", "ADV-0128", "ARC-0012", "ARC-0015", "ARC-0021", "ARC-0048"]

out = {}
for uid in IDS:
    r = {"unit_id": uid}
    rec_path = os.path.join(REPO, "command-center", "receipts", uid + ".json")
    raw = open(rec_path, "rb").read()
    rec = json.loads(raw.decode("utf-8"))
    r["state"] = rec.get("state")
    r["reviewer"] = "%s/%s" % ((rec.get("reviewer") or {}).get("verdict"),
                               (rec.get("reviewer") or {}).get("independent"))

    errs = gate.validate_receipt(rec)
    r["admission_errors"] = len(errs)
    ga = gate.evaluate_gate_a(rec, repo_root=REPO)
    r["gate_a_complete"] = bool(ga.complete)
    r["gate_a_marker"] = ga.marker()
    r["gate_a_blocking"] = ["c%s=%s" % (c.n, c.outcome) for c in ga.blocking_conditions]

    art = json.load(open(os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json"),
                         encoding="utf-8"))
    cat = {u["id"]: u for u in art["work_units"]}[uid]
    p = os.path.join(REPO, cat["output_path"].replace("/", os.sep))
    rawart = open(p, "rb").read()
    live = hashlib.sha256(rawart.replace(b"\r\n", b"\n")).hexdigest()
    man = json.load(open(os.path.join(REPO, "command-center", "p2-wave", "probes", uid,
                                      "UNIT-ARTIFACT-MANIFEST.json"), encoding="utf-8"))
    prim = [x for x in man["artifacts"] if x.get("role") == "primary"][0]
    r["artifact_ok"] = (os.path.getsize(p) > 0 and prim["sha256"] == live
                        and prim["bytes"] == len(rawart.replace(b"\r\n", b"\n")))
    b = os.path.join(REPO, "_rev2-w2-shard2", "pre-closure-backup", uid + ".json")
    r["receipt_unchanged_vs_backup"] = (
        hashlib.sha256(raw).hexdigest()
        == hashlib.sha256(open(b, "rb").read()).hexdigest())

    if uid in CLOSED:
        r["receipt_unchanged_vs_backup"] = False  # expected: closure wrote it
        rc = rec.get("extensions", {}).get("reviewer_closure") or {}
        r["closure_reviewer_id"] = rc.get("reviewer_id")
        r["method_refinements_recorded"] = bool(
            rc.get("builder_evidence_method_label_refinements"))
    out[uid] = r

with open(os.path.join(REPO, "_rev2-w2-shard2", "final_verify_out.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)

for uid in IDS:
    r = out[uid]
    print("%s: state=%s rev=%s admit_err=%d gateA_complete=%s marker=%s art_ok=%s%s"
          % (uid, r["state"], r["reviewer"], r["admission_errors"],
             r["gate_a_complete"], r["gate_a_marker"][:40], r["artifact_ok"],
             ("" if r["gate_a_complete"] else " blocking=" + ",".join(r["gate_a_blocking"]))))
