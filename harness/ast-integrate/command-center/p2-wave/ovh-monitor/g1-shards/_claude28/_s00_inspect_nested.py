#!/usr/bin/env python3
"""Inspect nested locations of probe-asserted fields. Not a measurement."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")

SPECS = [
    ("AUD-0010", "command-center/audit/AUD-0010-repo-weight-baseline.json",
     ["headline", "packed_bytes", "owner_repos", "named_probes"]),
    ("AUD-0052", "command-center/audit/AUD-0052-test-order-dependence.json",
     ["census", "seeds", "lab_orders_differ"]),
    ("AUD-0090", "command-center/audit/AUD-0090-static-analysis-baseline.json",
     ["report_kind", "observations"]),
    ("CNF-0029", "command-center/confirmation/CNF-0029-change-surface.json",
     ["branches"]),
    ("CNF-0145", "command-center/receipts/CNF-0145.json",
     ["sha256_sets", "controls"]),
    ("CNL-0002", "command-center/design/council/CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md",
     ["decision"]),
    ("CNL-0118", "command-center/design/council/CNL-0118-role-enforcement-and-participant-replacement-simulation.md",
     ["measured_results", "ticks"]),
    ("IMP-0200", "command-center/receipts/IMP-0200.json",
     ["pairwise_matrix", "tournament", "pairs"]),
    ("RES-0028", "command-center/research/RES-0028.json",
     ["ranking_algorithm", "claims", "tests"]),
    ("RES-0089", "command-center/research/RES-0089.json",
     ["detector_table", "reviewer", "applied_result", "PARTITION"]),
    ("RES-0144", "command-center/research/evidence-quality/RES-0144-two-axis-source-quality-rubric.json",
     ["measurements", "sample_size", "calibration"]),
    ("RES-0165", "command-center/research/deep-research-design/RES-0165-researcher-count-diminishing-returns.json",
     ["measurements", "flatten", "landscape_n"]),
    ("WFA-0025", "command-center/wfa/WFA-0025-sweep-academic-protocols.json",
     ["protocols", "implementing_candidate_id", "implemented_on_estate"]),
    ("WFA-0153", "command-center/foundry/WFA-0153-close-the-unresolved-nodes-in-the-466-node-provenanc.json",
     ["settlement", "survivors", "unresolved_count"]),
    ("IMP-0400", "command-center/receipts/IMP-0400.json",
     ["replay", "metrics", "paired_rows"]),
    ("SYN-0041", "command-center/synthesis/SYN-0041.final-report.json",
     ["items", "label_counts", "manifest_gate"]),
]


def walk(obj, prefix=""):
    found = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            found[path] = type(v).__name__
            if isinstance(v, (dict, list)) and prefix.count(".") < 4:
                found.update(walk(v, path))
    elif isinstance(obj, list) and obj and prefix.count(".") < 3:
        if isinstance(obj[0], dict):
            found.update(walk(obj[0], prefix + "[0]"))
    return found


rows = []
for uid, rel, needles in SPECS:
    art = REPO / rel
    doc = json.loads(art.read_text(encoding="utf-8"))
    paths = walk(doc)
    hits = {n: [p for p in paths if n in p][:8] for n in needles}
    rows.append(
        {
            "id": uid,
            "top": sorted(doc.keys())[:40],
            "reviewer": (doc.get("reviewer") or {}).get("reviewer_id") if isinstance(doc.get("reviewer"), dict) else None,
            "legacy": sorted((doc.get("extensions") or {}).get("legacy_root", {}) .keys())[:30]
            if isinstance(doc.get("extensions"), dict)
            else [],
            "hits": hits,
        }
    )

out = REPO / "command-center/p2-wave/ovh-monitor/g1-shards/_claude28/_s00_nested.out.json"
out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
for r in rows:
    print(f"\n== {r['id']} reviewer={r['reviewer']} ==")
    print(" top", r["top"][:20])
    if r["legacy"]:
        print(" legacy", r["legacy"][:15])
    for n, ps in r["hits"].items():
        print(f"  {n}: {ps[:5]}")
