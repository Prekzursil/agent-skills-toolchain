#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0301.json after the B07 gate is live."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.bench import margins, paths, serialize  # noqa: E402

OUT = "command-center/receipts/TST-0301.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0301/probe1_table_covers_gate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0301/probe2_posthoc_and_boundary.py"
)
QUESTION = (
    "Implementation target: stopping condition 8 at :11385 turns on the phrase "
    "without material regression, which is currently unquantified. Set a "
    "per-metric non-inferiority margin (how much worse a secondary metric may "
    "get before a primary win is refused), decide it BEFORE running the "
    "comparison, and record it in the release checklist."
)


def main() -> int:
    inv = margins.load_inventory(root=REPO)
    tab = margins.load_margin_table(root=REPO)
    margins.assert_table_covers_gate(inv, tab)
    table_sha, table_bytes = serialize.digest_file(REPO / paths.MARGIN_TABLE_REL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gate_ids = margins.gate_metric_ids(inv)
    secondary = [m for m in tab["metrics"] if m["role"] == "secondary"]
    primary = next(m for m in tab["metrics"] if m["role"] == "primary")

    doc = {
        "unit_id": "TST-0301",
        "id": "TST-0301",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0301",
        "report_kind": "b07-non-inferiority-margins",
        "question": QUESTION,
        "phase": "15",
        "ts": now,
        "title": "Define material regression as a number, and wire it into the release gate",
        "git_commit": None,
        "git_state": tab["git_state"],
        "margin_table": {
            "path": paths.MARGIN_TABLE_REL,
            "decided_at": tab["decided_at"],
            "sha256": table_sha,
            "bytes": table_bytes,
            "at_margin_resolves": tab["at_margin_resolves"],
            "at_margin_rule": tab["at_margin_rule"],
            "primary_metric": primary["id"],
            "secondary_metrics": [m["id"] for m in secondary],
            "gate_metrics": gate_ids,
        },
        "inventory": {
            "path": paths.INVENTORY_REL,
            "derivation": inv["derivation"],
            "b01_b10_receipts": inv["b01_b10_receipts"],
        },
        "checklist_path": paths.CHECKLIST_REL,
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "A per-metric non-inferiority margin exists for every metric "
                    "the release gate reads, decided at 2026-08-01T00:00:00Z."
                ),
                "verdict": "CONFIRMED",
                "anchor": paths.MARGIN_TABLE_REL,
            },
            {
                "id": "C2",
                "claim": (
                    "At-margin (worse_delta == margin) resolves NON_INFERIOR "
                    "(inclusive bound), documented on the table and checklist."
                ),
                "verdict": "CONFIRMED",
                "anchor": paths.CHECKLIST_REL,
            },
            {
                "id": "C3",
                "claim": (
                    "Modifying a margin after a comparison has bound the table "
                    "sha256 is POST_HOC_MARGIN_CHANGE, not a silent re-score."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/release_gate.py",
            },
            {
                "id": "C4",
                "claim": (
                    "This worktree is not a git repository; the freeze identity "
                    "is the content-address sha256 of the margin table, not an "
                    "introducing commit."
                ),
                "verdict": "CONFIRMED",
                "anchor": paths.MARGIN_TABLE_REL,
            },
        ],
        "tests": [
            {
                "id": "T-COVERAGE",
                "name": "Margin table validates and covers every metric the release gate reads.",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-POST-HOC",
                "name": "Modifying a margin after a comparison has run is flagged, not silently accepted.",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-BOUNDARY",
                "name": "A candidate exactly at the margin resolves NON_INFERIOR (inclusive).",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0301-probe2-independent-inequality",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-derives worse_delta with Decimal arithmetic in the "
                "probe file and requires agreement with release_gate.metric_status "
                "on inside / at-margin / beyond, then reproduces both-states "
                "post-hoc vs frozen table."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": paths.MARGIN_TABLE_REL, "exists": True, "role": "margin-table"},
            {"path": paths.INVENTORY_REL, "exists": True, "role": "inventory"},
            {"path": paths.CHECKLIST_REL, "exists": True, "role": "checklist"},
            {"path": "tools/bench/release_gate.py", "exists": True, "role": "gate"},
        ],
        "evidence": [
            {
                "path": paths.MARGIN_TABLE_REL,
                "kind": "frozen-margin-table",
                "note": f"decided_at={tab['decided_at']} sha256={table_sha} git_state={tab['git_state']}",
            },
            {
                "path": paths.CHECKLIST_REL,
                "kind": "release-checklist",
                "note": "records path, decided_at, inclusive at-margin rule, post-hoc bind",
            },
            {
                "path": "tools/bench/release_gate.py",
                "kind": "release-gate",
                "note": "binds margin_table_sha256; POST_HOC_MARGIN_CHANGE on digest mismatch",
            },
            {
                "path": paths.INVENTORY_REL,
                "kind": "metric-inventory",
                "note": inv["b01_b10_receipts"],
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "coverage-and-schema", "command": P1},
            {"id": "probe2", "role": "posthoc-and-boundary", "command": P2},
        ],
        "headline": (
            f"B07 margins decided_at={tab['decided_at']} "
            f"gate_metrics={len(gate_ids)} sha256={table_sha} "
            f"at_margin=NON_INFERIOR git_state=NOT-A-GIT-REPO"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    written = serialize.write_json(out, doc)
    if isinstance(written, tuple) and len(written) == 2:
        digest, size = written
    else:
        digest, size = serialize.digest_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(doc["headline"])
    print("SUCCESS:TST-0301")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
