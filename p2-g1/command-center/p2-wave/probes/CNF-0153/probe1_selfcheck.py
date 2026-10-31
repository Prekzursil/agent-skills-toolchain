#!/usr/bin/env python3
"""CNF-0153 probe1: gate-report coherence - the gate row must honestly declare whether its
stored green is still a control today, the known-vulnerable detector fixture must carry the
full advisory census, and filed advisories must carry severity + affected artifact.
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
    d = load("command-center/receipts/CNF-0153.json")
    gates = d["gates"]
    ck("gate_rows_present", len(gates) >= 1)
    g = gates[0]
    ck("gate_declares_liveness", g.get("live_query") is True)
    ck("gate_honestly_dates_itself", g.get("still_a_control_today") is False and bool(g.get("still_a_control_today_note")))
    dc = d.get("detector_control", {}).get("known_vulnerable", {})
    ck("detector_fixture_declares_census",
       dc.get("package") == "lodash" and dc.get("version") == "4.17.11"
       and dc.get("n_advisories") == 7 and len(dc.get("advisory_ids", [])) == 7)
    fa = d.get("filed_advisories", [])
    ck("advisory_filed_with_severity_and_target",
       len(fa) >= 1 and bool(fa[0].get("severity")) and bool(fa[0].get("affected_artifact"))
       and "package-lock.json" in json.dumps(fa[0].get("affected_artifact")))
    ck("sentinel_in_artifact", "SUCCESS:CNF-0153" in (REPO / "command-center/receipts/CNF-0153.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0153")

if __name__ == "__main__":
    sys.exit(main())
