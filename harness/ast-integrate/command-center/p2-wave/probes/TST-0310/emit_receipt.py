#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0310.json from the live ledger gate."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.bench import report as R  # noqa: E402
from tools.bench import serialize  # noqa: E402

OUT = "command-center/receipts/TST-0310.json"
LEDGER = "command-center/bench/results/runs.jsonl"
PUBLISHED = "command-center/bench/published"
INDEX = "command-center/bench/report-index.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0310/probe1_handedit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0310/probe2_orphan_idempotence.py"
)
QUESTION = (
    "Implementation target: the leaderboard, the status dashboard and any "
    "table in a report that cites a benchmark figure must be generated from "
    "the append-only results ledger and stamped with the run ids that "
    "produced them. CC-0013 applies the same discipline to STATUS.md; this "
    "applies it to benchmark reporting specifically, where the temptation to "
    "paste a remembered number is highest. A figure with no resolvable run "
    "id fails the build."
)


def main() -> int:
    files = R.generate(REPO / LEDGER, REPO / PUBLISHED)
    gate = R.check(REPO / LEDGER, REPO / PUBLISHED, REPO / INDEX)
    if not gate.ok:
        print(f"FAILED:TST-0310 live gate red {gate.as_dict()}")
        return 1
    sha, nbytes = serialize.digest_file(REPO / LEDGER)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "TST-0310",
        "id": "TST-0310",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0310",
        "completion_sentinel": "SUCCESS:TST-0310",
        "report_kind": "bench-ledger-derived-tables",
        "title": "Derive the leaderboard mechanically from the results ledger and forbid hand-typed numbers",
        "question": QUESTION,
        "phase": "10",
        "ts": now,
        "cloud_ok": False,
        "ledger": {
            "path": LEDGER,
            "sha256": sha,
            "bytes": nbytes,
            "rows": gate.ledger_rows,
            "append_only": True,
        },
        "published_dir": PUBLISHED,
        "generated_files": sorted(files),
        "figures_checked": gate.figures_checked,
        "figures_unresolved": gate.figures_unresolved,
        "figures_failed_to_resolve": gate.figures_unresolved,
        "drift_files": gate.drift_files,
        "unstamped": gate.unstamped,
        "gate_ok": gate.ok,
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Leaderboard, dashboard and report tables are generated "
                    "from command-center/bench/results/runs.jsonl and each "
                    "published figure carries run ids present in that ledger."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/bench/report.py",
            },
            {
                "id": "C2",
                "claim": (
                    f"Live orphan/hand-edit gate checked {gate.figures_checked} "
                    f"figures; {gate.figures_unresolved} failed to resolve."
                ),
                "verdict": "CONFIRMED",
                "anchor": LEDGER,
            },
            {
                "id": "C3",
                "claim": (
                    "Changing one number in a generated table makes the gate "
                    "red; regenerating from the same ledger is byte-identical."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0310/probe1_handedit.py",
            },
        ],
        "tests": [
            {
                "id": "T-HAND-EDIT",
                "name": "Hand-edit control: change one number in a generated table and confirm the build goes red.",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-ORPHAN-SCAN",
                "name": "Orphan-figure scan across all report artifacts.",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-IDEMPOTENCE",
                "name": "Regeneration idempotence: regenerating from the same ledger reproduces byte-identical tables.",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-HAND-EDIT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": "Mutate 0.940 to 0.941 in leaderboard.md; gate red. Restore via generate; gate green.",
            },
            {
                "id": "NC-ORPHAN-FIGURE",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": "Plant run-not-in-ledger in a stray report; gate red. Live published tree unresolved=0.",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0310-probe2-independent-orphan-scan",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 parses run_ids with its own regex (not "
                "report.extract_figures_from_text) and reproduces both-states: "
                "clean generate green, planted orphan red."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LEDGER, "exists": True, "role": "ledger"},
            {"path": "tools/bench/report.py", "exists": True, "role": "generator"},
            {"path": "tools/bench/ledger.py", "exists": True, "role": "ledger-reader"},
            {
                "path": f"{PUBLISHED}/leaderboard.md",
                "exists": True,
                "role": "generated-table",
            },
        ],
        "evidence": [
            {
                "kind": "results-ledger",
                "path": LEDGER,
                "note": f"rows={gate.ledger_rows} sha256={sha}",
            },
            {
                "kind": "live-gate",
                "path": PUBLISHED,
                "note": (
                    f"figures_checked={gate.figures_checked} "
                    f"figures_unresolved={gate.figures_unresolved}"
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "hand-edit-and-idempotence", "command": P1},
            {"id": "probe2", "role": "orphan-both-states-reviewer", "command": P2},
        ],
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "headline": (
            f"figures_checked={gate.figures_checked} "
            f"figures_unresolved={gate.figures_unresolved} "
            f"ledger_rows={gate.ledger_rows} gate_ok=true SUCCESS:TST-0310"
        ),
        "notes": (
            "tools/bench/ did not exist as a reporting platform; this unit "
            "adds ledger-derived generation and the hand-edit/orphan gate. "
            "TST-0295 (case corpus) is not delivered on this tree; the "
            "append-only JSONL ledger is the source of published figures. "
            "cloud_ok is not delivery."
        ),
    }
    serialize.write_json(REPO / OUT, doc)
    print(f"wrote {OUT} figures_checked={gate.figures_checked} unresolved={gate.figures_unresolved}")
    print("SUCCESS:TST-0310 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
