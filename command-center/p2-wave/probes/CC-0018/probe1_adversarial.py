#!/usr/bin/env python3
"""CC-0018 probe1: executed adversarial anti-repetition run with before/after ranks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import claim_rank as cr  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent


def main() -> int:
    base = {
        "schema_version": 1,
        "schema_status": "PROVISIONAL",
        "superseded_by_unit": "ARC-0085",
        "claim_id": "ADV-BASE",
        "canonical_mechanism": "stale-premise-ground-truth",
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [{"anchor": "docs://stale-premise.md", "probe": "agent-read"}],
        "confidence": "likely",
        "verification_status": "UNVERIFIED",
        "implementation_impact": "medium — carried forward as ground truth",
        "settling_probe": "re-read docs://stale-premise.md",
    }
    background = [
        {
            "schema_version": 1,
            "schema_status": "PROVISIONAL",
            "superseded_by_unit": "ARC-0085",
            "claim_id": "BG-STRONG",
            "canonical_mechanism": "background-strong-independent",
            "duplicate_of": [],
            "supports": [],
            "contradicts": [],
            "source_lineage": [
                {"anchor": "probes://strong-a", "probe": "command"},
                {"anchor": "probes://strong-b", "probe": "file-read"},
            ],
            "confidence": "almost-certain",
            "verification_status": "CONFIRMED",
            "implementation_impact": "high — decision-blocking",
            "settling_probe": "pytest tools/command-center/tests/test_claim_rank.py -q",
        },
        {
            "schema_version": 1,
            "schema_status": "PROVISIONAL",
            "superseded_by_unit": "ARC-0085",
            "claim_id": "BG-WEAK",
            "canonical_mechanism": "background-weak-single-source",
            "duplicate_of": [],
            "supports": [],
            "contradicts": [],
            "source_lineage": [{"anchor": "notes://weak.txt", "probe": "skim"}],
            "confidence": "uncertain",
            "verification_status": "NOT-CHECKED",
            "implementation_impact": "low — cosmetic",
            "settling_probe": "manual skim notes://weak.txt",
        },
    ]
    report = cr.adversarial_repetition_run(
        base, n_values=[1, 3, 10, 25], background=background
    )
    # Explicit before/after ranks artifact required by evidence_requirement.
    artifact = {
        "unit": "CC-0018",
        "probe": "adversarial-repetition",
        "ok": report["ok"],
        "success_invented": False,
        "before_ranks": report["before"],
        "after_ranks": report["after"],
        "series": report["series"],
        "score_rose": report["score_rose"],
        "rank_improved": report["rank_improved"],
        "property": report["property"],
        "printed_summary": (
            f"before n={report['before']['n_agents']} "
            f"rank={report['before']['rank']} score={report['before']['score']}; "
            f"after n={report['after']['n_agents']} "
            f"rank={report['after']['rank']} score={report['after']['score']}; "
            f"score_rose={report['score_rose']} rank_improved={report['rank_improved']}"
        ),
    }
    out_json = OUT_DIR / "adversarial-before-after-ranks.json"
    out_raw = OUT_DIR / "adversarial-before-after-ranks.raw.txt"
    out_json.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_raw.write_text(artifact["printed_summary"] + "\n" + json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Also keep the CLI-shaped copy used by the packer.
    (OUT_DIR / "adversarial-run.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(artifact["printed_summary"])
    print(json.dumps({"ok": artifact["ok"], "path": str(out_json.relative_to(REPO))}))
    return 0 if artifact["ok"] and not artifact["score_rose"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
