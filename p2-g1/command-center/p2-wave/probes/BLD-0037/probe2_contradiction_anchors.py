#!/usr/bin/env python3
"""Probe 2: dual-anchor CONTRADICTS, use-vs-mention, independent reviewer queries."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / A.OUT_REL


def has_path_line(anchor: str) -> bool:
    if ":" not in str(anchor):
        return False
    path, _, rest = str(anchor).rpartition(":")
    if not path or not rest.isdigit():
        return False
    return int(rest) >= 1


def main() -> int:
    result = A.run_audit(REPO)
    contra = [f for f in result["findings"] if f["kind"] == "CONTRADICTS"]
    if not contra:
        print("FAILED:BLD-0037-probe2 no CONTRADICTS finding")
        return 1
    for row in contra:
        if not row.get("note_permalink"):
            print("FAILED:BLD-0037-probe2 CONTRADICTS missing note permalink")
            return 1
        if not has_path_line(row.get("note_anchor")):
            print(f"FAILED:BLD-0037-probe2 note_anchor not path:line {row.get('note_anchor')}")
            return 1
        if not has_path_line(row.get("program_claim_anchor")):
            print(
                "FAILED:BLD-0037-probe2 program_claim_anchor not path:line "
                f"{row.get('program_claim_anchor')}"
            )
            return 1
        if "mention-rejected-ancestry.md" in str(row.get("program_claim_anchor")):
            print("FAILED:BLD-0037-probe2 use-vs-mention false positive")
            return 1
    for row in result["unconsulted"]:
        if not row.get("retrieving_query"):
            print(f"FAILED:BLD-0037-probe2 UNCONSULTED without retrieving_query {row}")
            return 1
    missed = result["missed"]
    if not missed:
        print("FAILED:BLD-0037-probe2 reviewer found no note the author set missed")
        return 1
    if not any(m["permalink"] == A.REVIEWER_PIN for m in missed):
        print(
            "FAILED:BLD-0037-probe2 reviewer missed-set does not include "
            f"{A.REVIEWER_PIN}: {missed}"
        )
        return 1
    if len(result["reviewer_queries"]) < 3:
        print("FAILED:BLD-0037-probe2 reviewer ran fewer than three queries")
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0037-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0037" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0037-probe2 sentinel absent")
        return 1
    art_contra = [f for f in (doc.get("findings") or []) if f.get("kind") == "CONTRADICTS"]
    if len(art_contra) != len(contra):
        print(
            f"FAILED:BLD-0037-probe2 artifact CONTRADICTS count {len(art_contra)} "
            f"!= live {len(contra)}"
        )
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:BLD-0037-probe2 reviewer.independent is not true")
        return 1
    if rev.get("verdict") != "PASS":
        print(f"FAILED:BLD-0037-probe2 reviewer verdict {rev.get('verdict')}")
        return 1
    if len(rev.get("queries") or []) < 3:
        print("FAILED:BLD-0037-probe2 artifact reviewer queries < 3")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-contradiction-anchors",
                "contradicts": len(contra),
                "dual_anchors": True,
                "mention_false_positive": False,
                "reviewer_missed": [m["permalink"] for m in missed],
                "unconsulted_with_query": all(
                    u.get("retrieving_query") for u in result["unconsulted"]
                ),
                "pass": True,
            }
        )
    )
    print(
        f"contradicts={len(contra)} dual_anchors=True reviewer_missed="
        f"{len(missed)} unconsulted={len(result['unconsulted'])}"
    )
    print("SUCCESS:BLD-0037-probe2 contradiction anchors reviewer queries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
