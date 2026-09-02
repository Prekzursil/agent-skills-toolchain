#!/usr/bin/env python3
"""Write the original certification record (adjudicator-only scores).

The confirmer (probe1) must not read this file. Confirmation uses held-out
seeds and a second substrate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fusion_core as fc  # noqa: E402

OUT = Path(__file__).resolve().parent / "adjudicator" / "certification.json"


def certify() -> dict:
    wids = [fc.FUSION, fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C]
    rows = fc.run_matrix(fc.CERT_SEEDS, [fc.SUBSTRATE_INPROCESS], wids)
    summaries = [
        fc.summarize_condition(rows, seed, fc.SUBSTRATE_INPROCESS)
        for seed in fc.CERT_SEEDS
    ]
    # Drop bulky per-case lists from the cert envelope; keep them under scores.
    per_seed = []
    for s in summaries:
        per_seed.append(
            {
                "seed": s["seed"],
                "substrate": s["substrate"],
                "mean_f1": s["mean_f1"],
                "mean_delta_vs_best_source": s["mean_delta_vs_best_source"],
                "delta_ci95": s["delta_ci95"],
                "fusion_beats_each_source_mean": s["fusion_beats_each_source_mean"],
                "ci_excludes_zero_or_negative": s["ci_excludes_zero_or_negative"],
                "weak_source_loses": s["weak_source_loses"],
                "n_cases": s["n_cases"],
                "per_case": s["per_case"],
            }
        )
    doc = {
        "record_kind": "original-certification",
        "unit_id": "CNF-0175",
        "adjudicator_only": True,
        "confirmer_must_not_read": True,
        "fusion_id": fc.FUSION,
        "source_ids": [fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C],
        "stage_counts": fc.WORKFLOW_STAGE_COUNTS,
        "metric": "f1",
        "win_is_not_stage_count": True,
        "seeds": list(fc.CERT_SEEDS),
        "substrate": fc.SUBSTRATE_INPROCESS,
        "n_cases": len(fc.matched_cases()),
        "claimed_win": all(
            s["fusion_beats_each_source_mean"] and s["ci_excludes_zero_or_negative"]
            for s in summaries
        ),
        "scores": per_seed,
    }
    return doc


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = certify()
    raw = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    OUT.write_text(raw, encoding="utf-8")
    digest = fc.sha256_bytes(raw.encode("utf-8"))
    print(f"wrote {OUT.relative_to(fc.REPO).as_posix()} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
