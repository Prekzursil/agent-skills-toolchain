#!/usr/bin/env python3
"""CNF-0089 probe1: truth-table census - five 2-atom expressions x 9 Kleene assignments
plus one atom expression x 3 (48 rows total), zero sampled, every row observed.
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
    d = load("command-center/confirmation/CNF-0089-stopping-truth-table.json")
    tt = d["truth_tables"]
    ck("six_tables", len(tt) == 6)
    ok = True
    total = 0
    for t in tt:
        n = t["expected_row_count"]
        ok &= (n == t["observed_row_count"] == len(t["rows"]))
        ok &= t["mismatches"] == 0 and t["conforms"] is True
        ok &= t["all_rows_observed"] is True and t["sampled"] is False
        vals = set()
        for r in t["rows"]:
            vals.update(r["assignment"].values())
        ok &= vals == {"F", "U", "T"}
        total += n
    ck("census_full_conforming_48", ok and total == 48)
    rc = d["row_census"]
    ck("row_census_48_unsampled", rc.get("observed") == 48 and rc.get("expected") == 48 and rc.get("sampled") is False)
    a = d["answers"]
    need = {"any_and_behaves_as_or_under_partial_evidence", "never_true_expression_never_stops", "runtime_stops_exactly_when_expression_true"}
    ck("answers_flags_present", need.issubset(set(a)))
    ck("and_not_or_under_partial", a.get("any_and_behaves_as_or_under_partial_evidence") is False)
    ck("never_true_control_recorded", d.get("never_true_control", {}).get("never_stopped") is True)
    ck("mutant_control_recorded", any(nc.get("fired_on_bad_state") and nc.get("silent_on_good_state") for nc in d.get("negative_controls", [])))
    ck("completion_sentinel_in_artifact", "SUCCESS:CNF-0089" in (REPO / "command-center/confirmation/CNF-0089-stopping-truth-table.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0089")

if __name__ == "__main__":
    sys.exit(main())
