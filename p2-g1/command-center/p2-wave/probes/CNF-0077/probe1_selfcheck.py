#!/usr/bin/env python3
"""CNF-0077 probe1: artifact self-consistency (classification counts, floor arithmetic, member paths).
Emitted by shard8-w2 resume builder 2026-10-25. Self-contained; stdlib only.
Live re-verification of the delivered artifact; exit 0 iff every check passes."""
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
    d = load("command-center/confirmation/CNF-0077-blueprint-executability.json")
    rows = d["blueprints"]
    counts = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    ck("classification_counts_recomputed", counts == d["classification_counts"])
    ck("counts_are_12_load_error_102_failure", counts.get("load-error") == 12 and counts.get("failure") == 102)
    exec_rows = [r for r in rows if r.get("exit_code") == 0 and r["classification"] == "success"]
    ck("measured_executable_count_zero", len(exec_rows) == 0 and d["measured_executable_count"] == 0)
    ck("catalog_claim_is_108", d["catalog_claim"] == 108)
    ck("floor_arithmetic_honest_false", d["meets_floor"] == (d["measured_executable_count"] >= d["declared_floor"]) and d["meets_floor"] is False)
    lp = d["live_member_paths"]
    missing = [p for p in lp if not (REPO / p).is_file()]
    ck("live_member_paths_103_present", len(lp) == 103 and not missing)
    for sr in d["scanned_roots"]:
        exists = (REPO / sr["path"]).exists()
        if exists != sr["exists"]:
            ck("scanned_root_matches_disk:" + sr["path"], False)
    ck("scanned_roots_match_disk_today", True)
    ck("completion_sentinel_in_artifact", "SUCCESS:CNF-0077" in (REPO / "command-center/confirmation/CNF-0077-blueprint-executability.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0077")

if __name__ == "__main__":
    sys.exit(main())
