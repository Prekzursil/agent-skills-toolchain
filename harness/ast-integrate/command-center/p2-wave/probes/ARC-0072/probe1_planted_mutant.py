#!/usr/bin/env python3
"""Probe 1: planted renamed copy of a live design ranks first on BOTH measures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from compare import build_analysis  # noqa: E402


def main() -> int:
    analysis = build_analysis()
    mutant = analysis["planted_mutant"]
    vs = mutant["vs_donor"]
    ok_rank = mutant["both_measures_rank_donor_first"]
    ok_dup = mutant["both_measures_flag_duplicate"]
    print(
        f"donor={mutant['donor']} mutant={mutant['mutant_id']} "
        f"jaccard={vs['jaccard']} cosine={vs['cosine']} class={vs['class']}"
    )
    print(
        f"jaccard_rank_1={mutant['jaccard_rank_1']} "
        f"cosine_rank_1={mutant['cosine_rank_1']} "
        f"jaccard_ranking={mutant['jaccard_ranking']}"
    )
    print(
        f"shared_mechanisms={vs['shared_mechanism_count']} "
        f"mutant_statements={mutant['mutant_statement_count']} "
        f"donor_statements={mutant['donor_statement_count']}"
    )
    if not ok_rank:
        print("FAILED:ARC-0072-probe1 renamed copy did not rank first on both measures")
        return 1
    if not ok_dup:
        print("FAILED:ARC-0072-probe1 renamed copy was not classified DUPLICATE by BOTH measures")
        return 1
    if vs["jaccard"] < 0.85 or vs["cosine"] < 0.85:
        print("FAILED:ARC-0072-probe1 renamed copy scores too low to be a near-copy")
        return 1
    # Artifact, if present, must record the same ranking.
    art = Path("command-center/phase3/ARCH-SIMILARITY.json")
    repo = HERE.parents[3]
    path = repo / art
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        rec = (doc.get("planted_mutant") or {})
        if rec.get("jaccard_rank_1") != mutant["donor"]:
            print("FAILED:ARC-0072-probe1 artifact jaccard_rank_1 mismatch")
            return 1
        if rec.get("cosine_rank_1") != mutant["donor"]:
            print("FAILED:ARC-0072-probe1 artifact cosine_rank_1 mismatch")
            return 1
        print("artifact_agrees=true")
    print("SUCCESS:ARC-0072-probe1 planted-mutant both-measures rank-1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
