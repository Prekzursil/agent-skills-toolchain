#!/usr/bin/env python3
"""CNF-0166 probe1: evidence-integrity receipt structure - four CONFIRMED evidence rows with
anchors, honest snapshot-coverage disclosure (4/1046), observations carry the extractor census,
and the in-scope row enumerates the required per-citation field set.
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
    d = load("command-center/receipts/CNF-0166.json")
    ev = d["evidence"]
    ck("four_evidence_rows", len(ev) == 4)
    ck("rows_confirmed_with_anchors", all(r.get("verdict") == "CONFIRMED" and r.get("anchor") for r in ev))
    blob = json.dumps(d)
    for field in ("url", "http_status", "snapshot_hash", "current_hash", "support_verdict"):
        ck("field_set_enumerated:" + field, field in blob)
    rep = d["report"]
    obs = {o["name"]: o for o in rep.get("observations", [])}
    cov = obs.get("per-citation-snapshot-hash-coverage", {})
    ck("snapshot_coverage_honestly_4_of_1046", str(cov.get("measured")) == "4/1046")
    ck("extractor_census_recorded", int(obs.get("recoverable-distinct-citation-urls", {}).get("measured", 0)) > 1000)
    ck("control_harness_recorded", obs.get("required-control-harness-pass", {}).get("measured") is True)
    ck("unrecoverable_count_honest", int(obs.get("unrecoverable-url-identities", {}).get("measured", -1)) > 1000)
    ck("sentinel_in_artifact", "SUCCESS:CNF-0166" in (REPO / "command-center/receipts/CNF-0166.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0166")

if __name__ == "__main__":
    sys.exit(main())
