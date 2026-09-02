#!/usr/bin/env python3
"""Author the 21-phase / 46-edge source. Run once to write the JSON source.

Edges are authored from spec prose by this unit, not derived from the
catalog item graph. Each edge carries a reason. CONTESTED-1 is 1→2.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "sources" / "phase-graph-authored.json"

PHASES = [
    ("0", "Foundation / command-center standing up", "B01"),
    ("1", "Claim-record contract", "B02"),
    ("2", "Research program (blocked on claim-record home)", "B03"),
    ("2A", "Research slice A (enumeration / registry)", "B04"),
    ("2B", "Research slice B (pairing / fusion)", "B05"),
    ("2C", "Research slice C (council envelope)", "B06"),
    ("3", "Architecture selection", "B07"),
    ("4", "Formalization / schema lock", "B07"),
    ("5", "Implementation-prep", "B08"),
    ("6", "Workflow-design", "B08"),
    ("7", "Integration core", "B09"),
    ("7A", "Integration add-on", "B09"),
    ("8", "Verification tooling", "B10"),
    ("9", "Adversarial / contest tracks", "B10"),
    ("10", "Synthesis", "B11"),
    ("11", "Coverage audit", "B11"),
    ("12", "Remaining delivery", "B12"),
    ("13", "Remaining audit close", "B12"),
    ("14", "Architecture diagrams", "B13"),
    ("15", "Program close-out", "B13"),
    ("16", "Unfunded remainder (no allocation bucket)", None),
]

# 7*158 + 6*157 = 2048
BUCKETS = [
    ("B01", "0", 158),
    ("B02", "1", 157),
    ("B03", "2", 158),
    ("B04", "2A", 157),
    ("B05", "2B", 158),
    ("B06", "2C", 157),
    ("B07", "3+4", 158),
    ("B08", "5+6", 157),
    ("B09", "7+7A", 158),
    ("B10", "8+9", 157),
    ("B11", "10+11", 158),
    ("B12", "12+13", 157),
    ("B13", "14+15", 158),
]

# Spine (10) + chords (16) + fan-out (20) = 46
EDGES: list[tuple[str, str, str, bool, str]] = [
    # spine
    ("0", "1", "HARD", False, "Foundation must exist before the claim-record contract is authored."),
    (
        "1",
        "2",
        "CONTESTED",
        True,
        "CONTESTED-1: 1→2 is HARD only while the claim-record schema still lives in Phase 4; CC-0017 pulling that schema to Phase 1 is the change that would make this edge SOFT. Authored from spec prose, not from catalog item edges.",
    ),
    ("2", "3", "HARD", False, "Research outputs are the inputs to architecture selection."),
    ("3", "4", "HARD", False, "The chosen architecture bounds what formalization may lock."),
    ("4", "7", "HARD", False, "Formal contracts are the gate into integration."),
    ("7", "7A", "HARD", False, "Integration core precedes the integration add-on."),
    ("7A", "10", "HARD", False, "An integrated system is the input to synthesis."),
    ("10", "11", "HARD", False, "Synthesis inventory precedes the coverage audit."),
    ("11", "14", "HARD", False, "The coverage map is an input to architecture diagrams."),
    ("14", "15", "HARD", False, "Diagrams and synthesis close into program close-out."),
    # chords that shorten, never lengthen, the spine
    ("0", "2", "SOFT", False, "Foundation tables are readable by research without waiting on claim-record."),
    ("0", "3", "SOFT", False, "Architecture may inspect foundation artifacts while research is still running."),
    ("1", "3", "SOFT", False, "A provisional claim-record sketch informs architecture before research lands."),
    ("1", "4", "SOFT", False, "Claim-record field names leak into formalization even before Phase 2 unblocks."),
    ("2", "4", "SOFT", False, "Research findings may skip architecture and land as formalization notes."),
    ("2", "7", "SOFT", False, "Late research may file integration issues without a new architecture pass."),
    ("3", "7", "SOFT", False, "Architecture decisions can enter integration in parallel with formalization."),
    ("3", "7A", "SOFT", False, "Architecture residuals feed the integration add-on directly."),
    ("4", "7A", "SOFT", False, "Locked schemas are consumed by the integration add-on as well as the core."),
    ("4", "10", "SOFT", False, "Formalization text is a synthesis source, not only an integration gate."),
    ("7", "10", "SOFT", False, "Integration core notes may enter synthesis without waiting on 7A."),
    ("7", "11", "SOFT", False, "Integration holes are coverage-audit inputs."),
    ("7A", "11", "SOFT", False, "Add-on holes are coverage-audit inputs."),
    ("10", "14", "SOFT", False, "Synthesis drafts feed diagrams without a coverage-audit wait."),
    ("10", "15", "SOFT", False, "Synthesis close-out language is reusable as program close-out language."),
    ("11", "15", "SOFT", False, "Coverage gaps may be named at close-out without a new diagram pass."),
    # fan-out to concurrent slices (sinks: they do not rejoin the spine)
    ("0", "2A", "HARD", False, "Slice A enumeration requires the foundation registry to exist."),
    ("1", "2A", "SOFT", False, "Claim-record identifiers are useful to slice A but not a start-blocker."),
    ("2", "2A", "SOFT", False, "The research program coordinates slice A without absorbing it into the spine."),
    ("0", "2B", "HARD", False, "Slice B pairing requires foundation identity rules."),
    ("1", "2B", "SOFT", False, "Claim-record identity helps slice B pairing but is not a start-blocker."),
    ("2", "2B", "SOFT", False, "The research program coordinates slice B as a concurrent track."),
    ("0", "2C", "HARD", False, "Slice C council envelope requires foundation namespace allocation."),
    ("1", "2C", "SOFT", False, "Claim-record fields inform the council envelope without gating it."),
    ("3", "5", "HARD", False, "Implementation-prep consumes the selected architecture."),
    ("4", "5", "HARD", False, "Implementation-prep consumes locked schemas."),
    ("3", "6", "HARD", False, "Workflow-design consumes the selected architecture."),
    ("4", "6", "HARD", False, "Workflow-design consumes locked schemas."),
    ("7", "8", "SOFT", False, "Verification tooling may start from integration-core observations."),
    ("7A", "8", "SOFT", False, "Verification tooling also consumes add-on observations."),
    ("7", "9", "SOFT", False, "Adversarial tracks may start from integration-core observations."),
    ("7A", "9", "SOFT", False, "Adversarial tracks also consume add-on observations."),
    ("10", "12", "HARD", False, "Remaining delivery starts from the synthesis inventory."),
    ("11", "13", "HARD", False, "Remaining audit close starts from the coverage map."),
    ("11", "16", "SOFT", False, "Unfunded Phase 16 is named from the coverage audit so it cannot vanish."),
    ("14", "16", "SOFT", False, "Diagrams must still point at the unfunded remainder rather than dropping it."),
]


def preconditions() -> list[dict]:
    # 21 rows, 0 TRUE, 7 NOT-CHECKED, 14 FALSE — matching CC-0015's measured input.
    not_checked = {"8", "9", "12", "13", "14", "15", "16"}
    rows = []
    for pid, title, _bucket in PHASES:
        if pid in not_checked:
            verdict = "NOT-CHECKED"
            note = "No settling probe has been run for this phase precondition (CC-0015 residue)."
        else:
            verdict = "FALSE"
            note = "Measured FALSE on this worktree: the phase's standing-up artifacts are not all present."
        rows.append(
            {
                "phase": pid,
                "title": title,
                "verdict": verdict,
                "note": note,
            }
        )
    return rows


def main() -> None:
    assert len(EDGES) == 46, len(EDGES)
    assert len(PHASES) == 21, len(PHASES)
    bucket_sum = sum(b[2] for b in BUCKETS)
    assert bucket_sum == 2048, bucket_sum
    phases = []
    for pid, title, bucket in PHASES:
        phases.append(
            {
                "id": pid,
                "title": title,
                "allocation_bucket": bucket,
            }
        )
    edges = []
    for i, (src, dst, kind, contested, reason) in enumerate(EDGES, 1):
        edges.append(
            {
                "id": f"E{i:02d}",
                "from": src,
                "to": dst,
                "kind": kind,
                "contested": contested,
                "contested_id": "CONTESTED-1" if contested else None,
                "reason": reason,
                "author": "CC-0016-single-agent",
                "provenance": "authored-from-spec-prose",
            }
        )
    doc = {
        "author": "CC-0016-single-agent",
        "declared_critical_path": ["0", "1", "2", "3", "4", "7", "7A", "10", "11", "14", "15"],
        "description": (
            "Authored phase-level dependency graph. Edges are not derived from "
            "WORK-UNIT-CATALOG.json. Regeneration writes PHASE-GRAPH.json."
        ),
        "allocation_buckets": [
            {
                "id": bid,
                "covers_phases": covers,
                "planned_units": n,
            }
            for bid, covers, n in BUCKETS
        ],
        "edges": edges,
        "phases": phases,
        "program_preconditions": preconditions(),
        "schema_version": 1,
        "unit": "CC-0016",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} phases={len(phases)} edges={len(edges)} bucket_sum={bucket_sum}")


if __name__ == "__main__":
    main()
