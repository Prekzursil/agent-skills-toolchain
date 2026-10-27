#!/usr/bin/env python3
"""WFA-0002 probe1: live closure re-run on the fixture corpus.

Regenerates the corpus with make_fixtures (idempotent), re-runs the closure
engine with two independent instruments (A filesystem / B head-index), and
asserts the receipt closure_after reproduces: added=28 corrected=12,
66 edges, unresolved=0, rate=1.0, drift 8 live-only + 8 repo-only, no
fabrication rejected. Schema gate: local ProbeReport stand-in enforced;
pack ProbeReport delta reported (the receipt declared the pack absent on
its build worktree).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
import closure  # noqa: E402

RECEIPT = REPO / "command-center" / "wfa" / "WFA-0002-provenance-closure.json"
PACK = REPO / "command-center" / "wfa" / "schema" / "wfa-schema-pack.json"
LOCAL_SCHEMA = PROBE_DIR / "probe_report.schema.json"
SENTINEL = "SUCCESS:WFA-0002-probe1"


def fail(msg):
    print("FAILED:WFA-0002-probe1 " + msg)
    return 1


def main():
    subprocess.run([sys.executable, "-B", str(PROBE_DIR / "make_fixtures.py")],
                   capture_output=True, text=True, timeout=120)
    result = closure.run_closure()
    after = result["closure_after"]
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    ra_after = receipt["closure_after"]
    checks = [
        ("added-28", after["added"] == ra_after["added"] == 28),
        ("corrected-12", after["corrected"] == ra_after["corrected"] == 12),
        ("edges-66", after["provenance_edges_total"] == ra_after["provenance_edges_total"] == 66),
        ("unresolved-0", after["provenance_edges_unresolved"] == ra_after["provenance_edges_unresolved"] == 0),
        ("rate-1.0", after["provenance_resolution_rate"] == ra_after["provenance_resolution_rate"] == 1.0),
        ("no-fabrication", after["rejected_fabrication"] == [] == ra_after["rejected_fabrication"]),
        ("registry-additions-28", len(result["registry_additions"]) == len(receipt["registry_additions"]) == 28),
        ("every-add-has-anchor", all(a["provenance"]["anchor_path"] and a["provenance"]["sha256"]
                                     for a in result["registry_additions"])),
        ("drift-8-live-only", len([d for d in result["drift_findings"] if d["drift"] == "live-only"]) == 8),
        ("drift-8-repo-only", len([d for d in result["drift_findings"] if d["drift"] == "repo-only"]) == 8),
        ("graph-not-live-graph", json.loads((closure.FIX / "graph.json").read_text(encoding="utf-8"))["not_the_live_466_node_graph"] is True),
        ("receipt-runs-its-own-measure", "SUCCESS:delivered" in json.dumps(receipt["evidence"])),
    ]
    closure.verify_closure(result)  # raises on any red
    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")

    # Schema gates: local stand-in enforced; pack delta reported, not hidden.
    import jsonschema
    artifact = receipt
    local_schema = json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))
    local_errors = sorted(jsonschema.Draft202012Validator(local_schema).iter_errors(artifact),
                          key=lambda e: e.json_path)
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    pack_report = pack["$defs"]["ProbeReport"]
    pack_errors = sorted(jsonschema.Draft202012Validator(pack_report).iter_errors(artifact),
                         key=lambda e: e.json_path)
    print("  schema local-standin errors:", len(local_errors))
    for e in local_errors[:5]:
        print("    local:", e.json_path, e.message[:120])
    print("  schema pack-ProbeReport delta (receipt declared pack absent at build):",
          len(pack_errors), "missing-required:", [e.message[:60] for e in pack_errors
                                                   if e.validator == "required"])
    if local_errors:
        return fail("local schema errors")
    print(json.dumps({
        "probe": "probe1-resolution-closure", "unit_id": "WFA-0002", "pass": True,
        "closure_after": after,
        "provenance_resolution_rate": 1.0, "provenance_edges_unresolved": 0,
        "drift_findings": len(result["drift_findings"]),
    }))
    print(SENTINEL + " fixture closure re-run reproduces the receipt: 40 refs, 66 edges, rate 1.0, 0 unresolved, 28 anchored adds, 12 corrections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
