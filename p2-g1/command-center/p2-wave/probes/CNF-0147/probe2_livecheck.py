#!/usr/bin/env python3
"""CNF-0147 probe2: recompute the whole delta from the four recorded runs (green-with-network
vs red-without per test id) and diff against the recorded delta; record the live availability
of an egress-blocking primitive on this host. Emitted by shard8-w2 resume builder 2026-10-25."""
import json, shutil, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []
FACTS = {}

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "facts": FACTS, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0147.json")
    runs = d["runs"]
    open_runs = [r for r in runs if r["egress"] == "open"]
    blocked_runs = [r for r in runs if r["egress"] == "blocked"]
    cold = [r for r in runs if r.get("cache") == "cold"]
    test_ids = [x["id"] for x in runs[0]["results"]]
    ck("consistent_test_ids_across_runs", all([x["id"] for x in r["results"]] == test_ids for r in runs))

    def rowmap(r):
        return {x["id"]: x["ok"] for x in r["results"]}
    oc = rowmap([r for r in cold if r["egress"] == "open"][0])
    bc = rowmap([r for r in cold if r["egress"] == "blocked"][0])
    warm_open = rowmap([r for r in runs if r.get("cache") == "warm" and r["egress"] == "open"][0])
    warm_blocked = rowmap([r for r in runs if r.get("cache") == "warm" and r["egress"] == "blocked"][0])
    recorded = {r["test_id"]: r for r in d["delta"]}
    recomputed_ids = sorted(t for t in oc if oc[t] and not bc[t])
    ck("delta_ids_recomputed_from_cold_pair", recomputed_ids == sorted(recorded))
    full = all(
        recorded[t]["green_with_network"] == oc[t]
        and recorded[t]["red_without"] == (not bc[t])
        and recorded[t]["blocked_warm_ok"] == warm_blocked[t]
        and recorded[t]["open_warm_ok"] == warm_open[t]
        for t in recorded
    )
    ck("delta_rows_cellwise_recomputed", full)

    cold_open = [r for r in cold if r["egress"] == "open"][0]
    cold_blocked = [r for r in cold if r["egress"] == "blocked"][0]
    ck("cold_cache_delta_16", cold_open["fail_count"] == 0 and cold_blocked["fail_count"] == 16)


    FACTS["egress_block_primitive_available_today"] = shutil.which("unshare") is not None
    ck("block_method_declared", "unshare" in json.dumps(d["block_control"].get("method", "")).lower()
       or bool(d["block_control"].get("method")))
    return finish("probe2_livecheck", "CNF-0147")

if __name__ == "__main__":
    sys.exit(main())
