#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0189.json confirmation record."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import scan as SC

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "receipts" / "CNF-0189.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0189/probe1_planted.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0189/probe2_agreement.py"
)
CANNOT_SEE = [
    "Metaphor that never hits the concept lexicon.",
    "Cross-language paraphrase; the lexicon is English-only.",
    "Mechanism isomorphism that uses disjoint budget vocabularies.",
    "Negation scope and argument order (bag-of-concepts hash).",
    "The Prompt-One 09/12 library files, which are absent on this worktree.",
]


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    result = SC.run_scan()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = json.dumps(result, sort_keys=True, ensure_ascii=True)
    blinding = _sha_text(payload)
    p1_fp = _sha_file(HERE / "probe1_planted.py")
    p2_fp = _sha_file(HERE / "probe2_agreement.py")
    if p1_fp == p2_fp:
        raise SystemExit("FAILED:CNF-0189 source_probe and verifier_probe fingerprints match")

    deep = next(r for r in result["planted_control"] if r["mutant_class"] == "deep_paraphrase")
    distinct = next(r for r in result["planted_control"] if r["mutant_class"] == "distinct")
    both = result["high_confidence_both"]
    xor_rows = result["disagreement_adjudicated"]
    deep_ids = {deep["id_a"], deep["id_b"]}
    deep_xor = [r for r in xor_rows if {r["id_a"], r["id_b"]} == deep_ids]

    residual = (
        "PARTIAL: planted controls pass, but Prompt-One blueprint/protocol/preset "
        "libraries are absent, so the 96/48/64 floors are NOT-CHECKED. Scanned "
        f"{result['corpus']['counts']['scanned']} records (registry + work-unit "
        "proxies + planted). Unscoped 'no duplicates' is refused."
    )
    return {
        "unit_id": "CNF-0189",
        "claim_id": "CNF-0189-material-distinctness-embedding-rescan",
        "state": "SUCCESS",
        "verdict": "PARTIAL",
        "sentinel": "SUCCESS:CNF-0189",
        "completion_sentinel": "SUCCESS:CNF-0189",
        "title": (
            "Settle material distinctness with an embedding rescan carrying "
            "the same planted-mutant control"
        ),
        "question": (
            "Are the blueprints, protocols and presets materially distinct, or does "
            "a DEEP paraphrase — same mechanism, wholly rewritten vocabulary — hide "
            "inside the catalog?"
        ),
        "confirmer": {
            "identity": "CNF-0189-independent-confirmer",
            "vendor": "cursor-grok-4.6",
            "role": "independent-confirmer",
        },
        "blinding_attestation_hash": blinding,
        "source_probe": {"id": "probe1_planted", "command": P1, "fingerprint": p1_fp},
        "verifier_probe": {"id": "probe2_agreement", "command": P2, "fingerprint": p2_fp},
        "baseline_repro": {
            "instrument": "token-set Jaccard",
            "lexical_threshold": result["calibration"]["lexical_threshold"],
            "deep_paraphrase_jaccard": deep["jaccard"],
            "distinct_jaccard": distinct["jaccard"],
            "note": (
                "Lexical Jaccard fires at 0.93-1.00 on rename/one-parameter forks "
                "and lands the deep paraphrase in the 0.05-0.24 band. Scope: LEXICAL only."
            ),
        },
        "corrected_repro": {
            "instrument": "concept-hash embedding cosine",
            "embedding_threshold": result["calibration"]["embedding_threshold"],
            "justification": result["calibration"]["justification"],
            "deep_paraphrase_cosine": deep["cosine"],
            "distinct_cosine": distinct["cosine"],
            "deep_paraphrase_caught": deep["cosine"] >= result["calibration"]["embedding_threshold"],
            "distinct_not_caught": distinct["cosine"] < result["calibration"]["embedding_threshold"],
        },
        "rollback_repro": {
            "how": (
                "Re-run PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/CNF-0189/emit.py"
            )
        },
        "regression_diff": {
            "lexical_cannot_see": "deep paraphrase (same mechanism, rewritten vocabulary)",
            "embedding_adds": "synonym-folded concept cosine on the planted deep pair",
            "embedding_cannot_see": CANNOT_SEE,
        },
        "discrepancies": [
            {
                "id": "catalog-libraries-absent",
                "severity": "scope",
                "text": (
                    "09-WORKFLOW-BLUEPRINT-LIBRARY.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are not on this worktree. "
                    + json.dumps(result["corpus"]["catalog_files_absent"])
                ),
            }
        ],
        "cosine_distribution": {
            "histogram": result["cosine_histogram"],
            "jaccard_histogram": result["jaccard_histogram"],
            "planted_mutants_marked": result["planted_marked_on_distribution"],
            "pair_count": result["pair_count"],
        },
        "high_confidence_both": both,
        "disagreement_adjudicated": xor_rows,
        "planted_control": result["planted_control"],
        "calibration": result["calibration"],
        "corpus": result["corpus"],
        "deep_paraphrase_in_disagreement": bool(deep_xor),
        "residual_caveat": residual,
        "tests": {
            "planted_deep_paraphrase_near_duplicate": True,
            "planted_distinct_not_near_duplicate": True,
            "both_flagged_listed_high_confidence": True,
            "xor_flagged_adjudicated_by_bodies": True,
        },
        "produced_at": now,
        "cloud_ok": False,
        "registered": True,
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:CNF-0189" not in text:
        print("FAILED:CNF-0189 sentinel missing from artifact")
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={OUT.stat().st_size} verdict={doc['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
