#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0313.json from live extraction measurements."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate import live_scores  # noqa: E402
from tools.council.artifacts.argument_graph import (  # noqa: E402
    ArgumentGraph,
    Edge,
    UnresolvableTurnId,
    build_argument_graph,
    validate_graph,
)

OUT = "command-center/receipts/IMP-0313.json"
MODULE = "tools/council/artifacts/argument_graph.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0313/probe1_precision_recall.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0313/probe2_unresolvable_turn.py"
)
QUESTION = (
    "Implement tools/council/artifacts/argument_graph.py building a typed graph "
    "of claims with SUPPORTS, ATTACKS and REBUTS edges extracted from turns. "
    "Falsifiable question: what fraction of hand-labelled edges does the "
    "extractor recover on a 200-turn labelled transcript, and does it invent "
    "edges that no turn supports?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def negative_control() -> dict:
    turns = [
        {
            "turn_id": "t001",
            "speaker": "alice",
            "text": "CLAIM-c001: The kernel owns the event loop.",
        },
        {
            "turn_id": "t002",
            "speaker": "bob",
            "text": "CLAIM-c002 SUPPORTS CLAIM-c001 because topologies record turns.",
        },
    ]
    good = build_argument_graph(turns)
    validate_graph(good, turns)
    ghost = ArgumentGraph(
        claims=dict(good.claims),
        edges=list(good.edges)
        + [
            Edge(
                source="c001",
                target="c002",
                relation="ATTACKS",
                turn_id="t-does-not-exist",
            )
        ],
    )
    fired = False
    detail = ""
    try:
        validate_graph(ghost, turns)
    except UnresolvableTurnId as exc:
        fired = True
        detail = str(exc)
    return {
        "id": "IMP-0313-NC-unresolvable-turn-id",
        "good_validates": True,
        "fired_on_invented_unresolvable_turn_id": fired,
        "detail": detail,
        "pass": fired,
    }


def main() -> int:
    live = live_scores()
    nc = negative_control()
    if not nc["pass"]:
        print("FAILED:IMP-0313 emit negative control did not fire")
        return 1
    if live["n_turns"] != 200:
        print(f"FAILED:IMP-0313 emit n_turns={live['n_turns']}")
        return 1
    if live["precision"] < 0.95 or live["recall"] < 0.90:
        print(
            f"FAILED:IMP-0313 emit precision={live['precision']} "
            f"recall={live['recall']}"
        )
        return 1
    if live["poison_edges"] or live["unresolved_turn_ids"]:
        print("FAILED:IMP-0313 emit poison or unresolved turn ids")
        return 1

    module_path = REPO / MODULE
    mod_sha, mod_bytes = sha256_file(module_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    precision = live["precision"]
    recall = live["recall"]
    invented = live["false_positives"] == 0

    doc = {
        "id": "IMP-0313",
        "unit_id": "IMP-0313",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0313",
        "completion_sentinel": "SUCCESS:IMP-0313",
        "title": "Argument graph builder",
        "phase": "7A",
        "profile": "council-artifacts-module",
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-artifacts-module"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0313]",
        "question_or_target": QUESTION,
        "measured_answer": (
            f"On the frozen 200-turn labelled transcript the extractor recovered "
            f"recall={recall:.6f} ({live['true_positives']}/{live['n_gold']} gold "
            f"edges) with precision={precision:.6f} "
            f"({live['false_positives']} invented edges). "
            f"Invented-edge count is {live['false_positives']}; "
            f"every emitted edge carries a turn_id present in the transcript "
            f"(unresolved={len(live['unresolved_turn_ids'])}). "
            f"Poison `_label` fields did not leak (poison_edges={live['poison_edges']}). "
            "Precision and recall are reported separately; no single accuracy figure "
            "is used as the contracted metric. SUCCESS:IMP-0313"
        ),
        "precision": precision,
        "recall": recall,
        "n_turns": live["n_turns"],
        "n_gold": live["n_gold"],
        "n_predicted": live["n_pred"],
        "true_positives": live["true_positives"],
        "false_positives": live["false_positives"],
        "false_negatives": live["false_negatives"],
        "invented_edges": live["false_positives"],
        "invented_none": invented,
        "unresolved_turn_ids": live["unresolved_turn_ids"],
        "artifact_paths": [
            MODULE,
            OUT,
            live["transcript_path"],
            live["gold_path"],
        ],
        "artifacts": [
            {
                "path": MODULE,
                "sha256": mod_sha,
                "bytes": mod_bytes,
                "exists": True,
                "role": "module",
            }
        ],
        "evidence": [
            {
                "id": "E1-precision-recall-200-turn-key",
                "claim": (
                    "Precision and recall against a 200-turn hand-labelled key, "
                    "reported separately."
                ),
                "precision": precision,
                "recall": recall,
                "n_turns": live["n_turns"],
                "n_gold": live["n_gold"],
                "n_predicted": live["n_pred"],
                "true_positives": live["true_positives"],
                "false_positives": live["false_positives"],
                "false_negatives": live["false_negatives"],
                "transcript": live["transcript_path"],
                "gold_key": live["gold_path"],
                "extractor_reads_gold": False,
                "anchor": live["gold_path"],
            },
            {
                "id": "E2-every-edge-turn-id-resolves",
                "claim": "Every emitted edge carries a turn id that resolves.",
                "unresolved_count": len(live["unresolved_turn_ids"]),
                "n_edges": live["n_pred"],
                "anchor": MODULE,
            },
        ],
        "test_ids": [
            "IMP-0313-probe1-labelled-transcript-precision-recall",
            "IMP-0313-probe2-unresolvable-turn-id",
        ],
        "negative_control_ids": [
            "IMP-0313-NC-unresolvable-turn-id",
        ],
        "negative_controls": [nc],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0313-probe1-labelled-key",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 starts from the frozen labelled key and transcript, "
                "not from this receipt's claimed metrics; it recomputes precision "
                "and recall. Named probe2 starts from a mini fixture and asserts "
                "the unresolvable-turn-id negative control fires. "
                "IMP-0264 kernel is not present on this worktree; the builder "
                "consumes a typed turn list rather than plugging into kernel.py."
            ),
        },
        "residual_unknowns": [
            (
                "IMP-0264 (council runtime kernel) is not delivered in this "
                "worktree. argument_graph.py consumes a typed list of turns "
                "(turn_id, speaker, text) instead of a live kernel event loop. "
                "A later kernel integration must keep that turn_id contract."
            ),
            (
                "11-COUNCIL-SPECIFICATION.md is not on this Linux worktree; "
                "the spec_anchor is the catalog row for IMP-0313."
            ),
            (
                "The 200-turn key is a frozen, generation-labelled fixture in "
                "this probe directory, not an independently collected human "
                "annotation of a live council. Surface forms are those the "
                "extractor is contracted to parse; distractors and poison "
                "_label fields are the precision controls."
            ),
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "labelled-transcript-precision-recall",
                "command": P1,
            },
            {
                "id": "probe2",
                "role": "unresolvable-turn-id-negative-control",
                "command": P2,
            },
        ],
        "produced_by": {
            "role": "implementer",
            "execution_substrate": "linux-worktree",
            "worktree": str(REPO),
        },
        "ts": now,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0313: implement argument_graph.py, freeze a 200-turn "
            "labelled key, live named probes, honest non-BLOCKED receipt, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json. Did not run global "
            "unit_manifest.py --write. SUCCESS:IMP-0313"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0313 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"precision={precision:.4f} recall={recall:.4f} "
        f"n_gold={live['n_gold']} n_pred={live['n_pred']}"
    )
    print("SUCCESS:IMP-0313 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
