#!/usr/bin/env python3
"""CNF-0163 probe1: anchor-class census coherence - class counts recomputed from the class
lists must equal the declared counts, the four classes must sum to claims_harvested, and the
git-history premise (absent) must still hold live. Emitted by shard8-w2 resume builder."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0163.json")
    counts = d["counts"]
    classes = d["classes"]
    recomputed = {k: len(v) for k, v in classes.items()}
    ck("counts_recomputed_from_class_lists", recomputed == counts)
    total = sum(counts.values())
    ck("classes_sum_to_claims_harvested", total == d["claims_harvested"] == 1671)
    ck("no_false_resolves_without_git", counts["resolved"] == 0)
    ck("drift_distinct_from_missing", counts["drifted"] == 0 and counts["missing-at-revision"] == 510)
    mar = classes["missing-at-revision"]
    ck("missing_rows_declare_blob_unavailable", all(r.get("blob_available") is False for r in mar[:50]))
    ck("git_history_absent_live", not (REPO / ".git").exists())
    ck("artifact_records_history_absence", d.get("estate_git_history_present") is False)
    ck("sentinel_in_artifact", "SUCCESS:CNF-0163" in (REPO / "command-center/receipts/CNF-0163.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0163")

if __name__ == "__main__":
    sys.exit(main())
