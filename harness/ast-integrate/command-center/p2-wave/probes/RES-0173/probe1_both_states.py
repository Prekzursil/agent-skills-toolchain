#!/usr/bin/env python3
"""Probe 1 — both-states taxonomy + per-class recall for the three named methods.

Fails unless:
  * always-merge is a collapser and exact-string is a string comparator
  * mechanism_key is both-states-correct AND merges the planted rewrite
  * lexical Jaccard is both-states-correct on paraphrase vs distinction
    and misses the rewrite (lexical blind spot)
  * the live artifact, if present, reports the same headline
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402

ART = REPO / "command-center/research/deep-research-design/RES-0173-mechanism-level-claim-dedup.json"
UNIT = "RES-0173"


def main() -> int:
    report = E.evaluate()
    E.assert_invariants(report)
    named = report["named_methods"]
    ctrl = report["controls"]
    print(f"probe=probe1_both_states unit={UNIT}")
    print(
        "THRESHOLDS jaccard="
        f"{report['jaccard_threshold']} cosine={report['cosine_threshold']} "
        f"embedding_kind={report['embedding_kind']} "
        f"neural={report['neural_sentence_embedding']}"
    )
    print("TAXONOMY_CONTROLS always_merge=collapser exact_string=string_comparator")
    print(
        "TAXONOMY_NAMED "
        f"lexical_jaccard={named['lexical_jaccard']['taxonomy']} "
        f"embedding_cosine={named['embedding_cosine']['taxonomy']} "
        f"mechanism_key={named['mechanism_key']['taxonomy']}"
    )
    print("PER_CLASS_RECALL")
    for mid in ("lexical_jaccard", "embedding_cosine", "mechanism_key"):
        for cls, rec in sorted(named[mid]["per_class"].items()):
            print(
                f"RECALL method={mid} class={cls} planted={rec['planted']} "
                f"merged={rec['merged']} recall={rec['recall']}"
            )
    rewrite = next(r for r in report["pair_rows"] if r["class"] == "full_rewrite")
    print(
        "REWRITE_BLINDSPOT jaccard="
        f"{rewrite['jaccard']} cosine={rewrite['cosine']} "
        f"jaccard_merge={rewrite['lexical_jaccard_merge']} "
        f"cosine_merge={rewrite['embedding_cosine_merge']} "
        f"key_merge={rewrite['mechanism_key_merge']}"
    )
    print(
        "BOTH_STATES mechanism_key_pass="
        f"{named['mechanism_key']['both_states_pass']} "
        f"jaccard_pass={named['lexical_jaccard']['both_states_pass']} "
        f"controls_collapser={ctrl['always_merge']['taxonomy']} "
        f"controls_string={ctrl['exact_string']['taxonomy']}"
    )
    print(f"HEADLINE_METHOD {report['headline_method']}")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            raise AssertionError(f"artifact self-declared {doc.get('state')}")
        if "SUCCESS:RES-0173" not in json.dumps(doc, ensure_ascii=True):
            raise AssertionError("artifact missing SUCCESS:RES-0173")
        if doc.get("headline_method") != "mechanism_key":
            raise AssertionError("artifact headline_method mismatch")
        baked = doc.get("named_method_taxonomy") or {}
        for mid, want in (
            ("lexical_jaccard", "correct"),
            ("mechanism_key", "correct"),
        ):
            if baked.get(mid) != want:
                raise AssertionError(f"artifact taxonomy {mid}={baked.get(mid)}")
    print("SUCCESS:RES-0173-probe1 both-states taxonomy and per-class recall")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED:RES-0173-probe1 {exc}", file=sys.stderr)
        raise SystemExit(1)
