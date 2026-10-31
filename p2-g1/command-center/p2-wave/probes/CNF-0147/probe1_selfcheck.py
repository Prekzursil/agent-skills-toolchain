#!/usr/bin/env python3
"""CNF-0147 probe1: egress-block delta report self-consistency - run arithmetic, block-control
liveness (the blocker itself MUST have failed the control fetch), delta-row shape.
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
    d = load("command-center/receipts/CNF-0147.json")
    bc = d["block_control"]
    ck("block_control_pass_true", bc.get("pass") is True)
    ck("blocked_fetch_failed_live", bc.get("blocked_ok") is False and bool(bc.get("blocked_error")))
    ck("unblocked_fetch_ok", bc.get("unblocked_ok") is True)
    ck("block_method_recorded", bool(bc.get("method")))
    runs = d["runs"]
    ck("four_runs_open_and_blocked", len(runs) == 4
       and sorted(r["egress"] for r in runs) == ["blocked", "blocked", "open", "open"])
    ok = True
    for r in runs:
        ok &= (r["pass_count"] + r["fail_count"] == len(r["results"]))
        ok &= (r["pass_count"] == sum(1 for x in r["results"] if x["ok"]))
    ck("run_counts_match_results", ok)
    ck("twenty_tests_per_run", all(len(r["results"]) == 20 for r in runs))
    delta = d["delta"]
    ck("delta_rows_are_network_failures", len(delta) == 16
       and all(r["red_without"] for r in delta)
       and all(r["green_with_network"] for r in delta))
    ck("every_delta_row_carries_attempt_evidence",
       all(r.get("connection_attempts") for r in delta)
       and all(a.get("error") for r in delta for a in r["connection_attempts"]))
    ck("sentinel_in_artifact", "SUCCESS:CNF-0147" in (REPO / "command-center/receipts/CNF-0147.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0147")

if __name__ == "__main__":
    sys.exit(main())
