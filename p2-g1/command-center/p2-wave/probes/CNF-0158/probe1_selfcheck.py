#!/usr/bin/env python3
"""CNF-0158 probe1: abstraction-leak register verdicts coherent - six leaks, every verdict in
the permitted set, no row confirmed merely by reading the register (REPRODUCED rows must carry
observed divergence evidence), both-vendor discrimination present.
Emitted by shard8-w2 resume builder 2026-10-25."""
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
    d = load("command-center/receipts/CNF-0158.json")
    leaks = d["leaks"]
    ck("six_leak_rows", len(leaks) == 6)
    allowed = {"REPRODUCED", "FIXED", "NEVER-REAL"}
    ck("verdicts_in_permitted_set", all(r.get("verdict") in allowed for r in leaks))
    ck("register_status_carried", all(bool(r.get("register_claimed_status")) for r in leaks))
    repro = [r for r in leaks if r["verdict"] == "REPRODUCED"]
    ck("reproduced_rows_carry_divergence_evidence",
       all(r.get("observed_divergence") and any(str(v).strip() for v in r["observed_divergence"].values()) for r in repro))
    ck("reproduced_rows_cite_own_leak_id_in_commands",
       all(r["leak_id"] in json.dumps(r.get("reproduction_commands", {})) for r in repro))
    both = [r for r in leaks if isinstance(r.get("vendor_verdicts"), dict) and len(r["vendor_verdicts"]) >= 2]
    ck("cross_vendor_discrimination_present", len(both) >= 1
       and any(len({vv.get("verdict") for vv in r["vendor_verdicts"].values()}) >= 2 for r in both))
    tests = d.get("tests", [])
    ck("probe_rows_all_pass", bool(tests) and all(t.get("result") == "PASS" for t in tests))
    ck("sentinel_in_artifact", "SUCCESS:CNF-0158" in (REPO / "command-center/receipts/CNF-0158.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0158")

if __name__ == "__main__":
    sys.exit(main())
