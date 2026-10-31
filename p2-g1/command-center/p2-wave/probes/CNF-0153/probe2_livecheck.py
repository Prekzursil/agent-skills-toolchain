#!/usr/bin/env python3
"""CNF-0153 probe2: TODAY re-verification. Re-queries the live OSV advisory database for the
detector-control package (lodash@4.17.11) and asserts every advisory the artifact recorded is
still surfaced live; then checks the detector fixture lockfile on disk when present. The
artifact claims a detector control, not a today-green; this probe re-proves the control live.
Emitted by shard8-w2 resume builder 2026-10-25."""
import json, sys, urllib.request
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
    d = load("command-center/receipts/CNF-0153.json")
    dc = d["detector_control"]["known_vulnerable"]
    pkg, ver = dc["package"], dc["version"]
    recorded_ids = set(dc["advisory_ids"])

    live_ids = set()
    net_ok = False
    try:
        req = urllib.request.Request(
            "https://api.osv.dev/v1/query",
            data=json.dumps({"package": {"name": pkg, "ecosystem": "npm"}, "version": ver}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            vulns = json.load(resp).get("vulns", [])
        live_ids = {v.get("id") for v in vulns}
        for v in vulns:
            for alias in v.get("aliases", []) or []:
                live_ids.add(alias)
        net_ok = True
    except Exception as e:
        FACTS["network_error"] = "%s: %s" % (type(e).__name__, str(e)[:160])

    FACTS["network_reached"] = net_ok
    FACTS["live_advisory_count"] = len(live_ids)
    FACTS["live_advisory_ids"] = sorted(live for live in live_ids if live)
    ck("osv_live_query_reached", net_ok)
    ck("detector_control_still_vulnerable_today", net_ok and len(live_ids) >= dc["n_advisories"])
    missing = sorted(recorded_ids - live_ids)
    FACTS["recorded_ids_missing_live_today"] = missing
    ck("all_recorded_advisories_still_surfaced_today", net_ok and not missing)

    fixture = Path(__file__).parent / "known-vulnerable" / "package-lock.json"
    FACTS["fixture_lockfile_present"] = fixture.is_file()
    if fixture.is_file():
        lock = json.loads(fixture.read_text(encoding="utf-8"))
        blob = json.dumps(lock)
        ck("fixture_lockfile_carries_vulnerable_pin", (pkg + "@") in blob or '"%s"' % pkg in blob)
    ck("sentinel_in_artifact", "SUCCESS:CNF-0153" in (REPO / "command-center/receipts/CNF-0153.json").read_text(encoding="utf-8"))
    return finish("probe2_livecheck", "CNF-0153")

if __name__ == "__main__":
    sys.exit(main())
