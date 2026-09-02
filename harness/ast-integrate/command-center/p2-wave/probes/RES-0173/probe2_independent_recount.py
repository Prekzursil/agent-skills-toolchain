#!/usr/bin/env python3
"""Probe 2 — independent cluster recount from the planted fixture.

Does not import evaluate.py. Re-derives merge decisions with:
  * no-stoplist Counter Jaccard
  * sha256(action|object) key identity
  * union-find clusters over those hashes

A split against probe 1 is resolved from the fixture labels, never by vote.
Neural / Codex vendor reproduction is NOT-CHECKED (no such runtime here).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402

ART = REPO / "command-center/research/deep-research-design/RES-0173-mechanism-level-claim-dedup.json"
UNIT = "RES-0173"


def main() -> int:
    bundle = R.recount()
    R.assert_invariants(bundle)
    print(f"probe=probe2_independent_recount unit={UNIT}")
    tax = bundle["taxonomy"]
    print(
        "RECOUNT_TAXONOMY "
        f"jaccard_nostop={tax['lexical_jaccard_nostop']} "
        f"key_hash={tax['mechanism_key_hash']} "
        f"union_find={tax['union_find_cluster']} "
        f"always_merge={tax['always_merge']} "
        f"exact_string={tax['exact_string']}"
    )
    print(
        "HEADLINE_COUNT unique_mechanism_key_hashes="
        f"{bundle['unique_mechanism_key_hashes']} "
        "want=3 (parents A,B,C; mutants of A share A's hash)"
    )
    rew = next(r for r in bundle["pair_rows"] if r["class"] == "full_rewrite")
    print(
        "REWRITE_RECOUNT jaccard_nostop="
        f"{rew['jaccard_nostop']} jaccard_merge={rew['jaccard_merge']} "
        f"cluster_merge={rew['cluster_merge']} "
        f"char3_cosine={rew['char3_cosine']}"
    )
    print(
        "BOTH_STATES paraphrases_merged="
        f"{bundle['paraphrases_merged_by_jaccard_and_key']} "
        f"distinctions_split={bundle['distinctions_split_by_jaccard_and_key']} "
        f"rewrite_clustered={bundle['rewrite_same_cluster_not_jaccard']}"
    )
    print(
        "CROSS_VENDOR_CODEX status=NOT-CHECKED reason="
        "no Codex/OpenAI runtime in this session; split counts would be "
        "resolved from the planted fixture, never by vote"
    )
    print(f"NEURAL_EMBEDDING {bundle['neural_sentence_embedding']}")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unique_mechanism_keys") != bundle["unique_mechanism_key_hashes"]:
            raise AssertionError(
                "artifact unique_mechanism_keys "
                f"{doc.get('unique_mechanism_keys')} != recount "
                f"{bundle['unique_mechanism_key_hashes']}"
            )
        if doc.get("headline_method") != "mechanism_key":
            raise AssertionError("artifact headline_method mismatch on recount")
        if "SUCCESS:RES-0173" not in json.dumps(doc, ensure_ascii=True):
            raise AssertionError("artifact missing SUCCESS:RES-0173")
    print("SUCCESS:RES-0173-probe2 independent cluster recount")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED:RES-0173-probe2 {exc}", file=sys.stderr)
        raise SystemExit(1)
