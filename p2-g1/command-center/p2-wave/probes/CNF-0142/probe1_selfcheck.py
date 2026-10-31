#!/usr/bin/env python3
"""CNF-0142 probe1: disagreement-matrix arithmetic - partition sums, direction splits,
accuracy recomputation, dangerous-error share, census algebra, re-injection records.
Emitted by shard8-w2 resume builder 2026-10-25. Self-contained; stdlib only."""
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
    d = load("command-center/receipts/CNF-0142.json")
    m = d["disagreement_matrix"]
    n = m["n"]
    ag = m["agree"]["ids"]
    un = m["under_grade"]
    ov = m["over_grade"]
    un_ids, ov_ids = un["ids"], ov["ids"]
    ck("partition_sums_to_n", len(ag) + len(un_ids) + len(ov_ids) == n)
    ck("sample_ids_unique", len(set(ag + un_ids + ov_ids)) == n)
    ck("n_is_12", n == 12)
    ck("accuracy_recomputed", abs(m["accuracy"] - len(ag) / n) < 1e-9)
    ck("counts_match_id_lists", m["agree"]["count"] == len(ag) and un["count"] == len(un_ids) and ov["count"] == len(ov_ids))
    # direction splits: by_transition must partition the id list in each direction
    for blk, ids in ((un, un_ids), (ov, ov_ids)):
        trans_ids = [i for lst in blk["by_transition"].values() for i in lst]
        ck("by_transition_covers_ids", sorted(trans_ids) == sorted(ids))
        rc = {c["claim_id"]: c["clause"] for c in blk.get("rubric_clauses", [])}
        ck("rubric_clause_per_id", sorted(rc) == sorted(ids))
    ds = m["dangerous_error_share"]
    ck("dangerous_share_recomputed", abs(ds - len(un_ids) / (len(un_ids) + len(ov_ids))) < 1e-9)
    ck("dangerous_share_is_undergrade_dominant", ds >= 0.5)
    cb, ca = d.get("census_before", []), d.get("census_after", [])
    rj = d.get("census_reinjections", [])
    rj_ids = [r["claim_id"] for r in rj]
    ck("reinject_in_census_after", all(i in ca for i in rj_ids))
    ck("census_after_superset_of_before", set(cb).issubset(set(ca)))
    ck("reinject_all_undergrade", all(r.get("direction") == "under-grade" for r in rj))
    ck("reinject_cite_rubric_clause", all(r.get("rubric_clause") and r.get("rubric_citation") for r in rj))
    ck("accuracy_only_rejected_flag_present", "accuracy_only_rejected" in m)
    ck("completion_sentinel_in_artifact", "SUCCESS:CNF-0142" in (REPO / "command-center/receipts/CNF-0142.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0142")

if __name__ == "__main__":
    sys.exit(main())
